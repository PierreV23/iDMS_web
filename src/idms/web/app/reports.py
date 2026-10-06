#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  8 11:01:32 2020

@author: wierinve
"""

import io
import json
from flask import Blueprint, render_template, send_file, jsonify, current_app, request
from flask_login import current_user, login_required
from irods.models import Collection, CollectionMeta, Resource
from irods.column import Criterion
from idms.web.app.projects import get_projectlist
from idms.web.app.utils.datafield import datafield, Datatypes
from idms.web.app.utils.datafieldregistry import datafield_registry

from idms.common.irods.irods_sessions import irods_manager

RESOURCES_OMIT = ('demoResc', 'bundleResc')

bp = Blueprint('reports', __name__, url_prefix='/reports')

def collection_size(coll, resource, timeout=86400):
    with irods_manager.session(current_user) as irods_session:
        size_attr = 'sys::collection_size::{}'.format(resource)
        query = irods_session.query(CollectionMeta.value).filter(
            Criterion('=', Collection.name, coll)).filter(
                Criterion('=', CollectionMeta.name, size_attr))
        size = 0
        for q in query:
            size += int(round(float((q[CollectionMeta.value]))))
    return size

def projectdata_in_resource(project, resource):
    # Find all collections with a specific projectid
    with irods_manager.session(current_user) as irods_session:
        query = irods_session.query(Collection.name).filter(
                Criterion('=', CollectionMeta.name, 'projectID')).filter(
                Criterion('=', CollectionMeta.value, project))
        usage = 0
        for coll in query:
            usage += collection_size(coll[Collection.name], resource)
            
    return usage

@bp.route('_irods_sessionreport')
def irods_sessionreport():
    return jsonify(irods_manager.reportdata())

@bp.route('/irodssessions')
def irodssessions():
    """Create a report of active iRODS Sessions

    Returns:
        rendered template
    """    
    columns = [
        { "field": "Environment", "title": "Environment", "sortable": True },
        { "field": "User", "title": "User", "sortable": True },
        { "field": "State", "title": "State", "sortable": True },
        { "field": "Timestamp", "title": "Last use", "sortable": True },        
    ]
    return render_template('report_irodssessions.html', columns=columns)

@bp.route('/_download')
def download_report():
    projectlist, resources = get_space_usage()
    output = io.StringIO()
    output.write('"id","name"')
    for r in resources:
        output.write(',"{}"'.format(r))
    output.write(',"total"\n')
    for project in projectlist:
        output.write('{id},{name}'.format(**project))
        for r in resources:
            output.write(',{}'.format(int(project[r])))
        output.write(',{}\n'.format(int(project['total'])))
    mem = io.BytesIO()
    mem.write(output.getvalue().encode('utf-8'))
    # seeking was necessary. Python 3.5.2, Flask 0.12.2
    mem.seek(0)
    output.close()
    return send_file(mem, download_name='diskspace_report.csv',
                     as_attachment=True)
        
    

def get_space_usage():

    #load projects
    projectinfo = get_projectlist()
          
    #query resources
    with irods_manager.session(current_user) as irods_session:
        query = irods_session.query(Resource.name)
        resources = [ r[Resource.name] for r in query if not r[Resource.name] in RESOURCES_OMIT ]
        # query projects
        query =  irods_session.query(CollectionMeta.value).filter(
            Criterion('=', CollectionMeta.name, 'projectID'))
        projects=[ r[CollectionMeta.value] for r in query]
        projects.sort()
        # create projectlist
        projectlist = []
        for p in projects:
            projectdata = {'id': p}
            projectdata['name'] = projectinfo.get(p, {'name': p, 'description': ''})['description']      
            total = 0
            for r in resources:
                projectdata[r] = datafield('usage', projectdata_in_resource(p, r), Datatypes.BYTES)
                total += int(projectdata[r])
            projectdata['total'] = datafield('total', total, Datatypes.BYTES)
            projectlist.append(projectdata)
    return projectlist, resources


@bp.route('/space')
@login_required
def space_report():
    if not current_user.is_admin:
        return('<tr><td colspan=3>Access denied</td></tr>')
    projectlist, resources = get_space_usage()
    return render_template('report_space.html', projectlist=projectlist, 
                           resources=resources)

@bp.route("plugins")
def plugin_report():
    if current_app.config.get('DISABLE_PLUGINS'):
        return render_template('generic_message.html', 
            title='Plugin Report',
            menuname='plugins',
            message = 'Plugins are disabled in the configuration'
        )
    
    plugins_data = []
    if current_app.plugin_manager and hasattr(current_app.plugin_manager, "loaded_plugins"):
        for plugin_name, plugin_inst in current_app.plugin_manager.loaded_plugins.items():
            plugins_data.append({
                "id": plugin_name,
                "name": getattr(plugin_inst, "name", plugin_name),
                "description": getattr(plugin_inst, "description", "No description provided"),
                "enabled": getattr(plugin_inst, "enabled", True),
                "optional": getattr(plugin_inst, "optional", True),
                "menus": getattr(plugin_inst, "registered_menus", []),
                "mappings": getattr(plugin_inst, "registered_mappings", []),
                "handlers": getattr(plugin_inst, "registered_handlers", []),
                "actionpages": getattr(plugin_inst, "registered_action_pages", []),
                "datafields": getattr(plugin_inst, "registered_datafields", []),
            })

    return render_template("plugin_state.html", plugins=plugins_data)

@bp.route('sys_report_data')
def system_report_data():
    category = request.args.get('category')
    data = []
    columns = []
    if category == '#attributes':
        attr_dict = { 
            attribute: {
                'attribute': attribute, 
                'datatype': datatype, 
                'plugin':'system'
            } 
            for attribute, datatype in datafield_registry.known_attributes.items()
        }
            
        for plugin_inst in current_app.plugin_manager.loaded_plugins.values():
            for attribute, datatype in plugin_inst.registered_datafields.items():
                attr_dict[attribute] = {
                    'attribute': attribute,
                    'datatype': datatype,
                    'plugin': plugin_inst.name
                }

        data = list(attr_dict.values())

        columns = [
            { "field": "attribute", "title": "Attribute", "sortable": True },
            { "field": "datatype", "title": "Datatype", "sortable": True },
            { "field": "plugin", "title": "Plugin", "sortable": True }
        ]
        
    elif category == '#viewers':
        for plugin_inst in current_app.plugin_manager.loaded_plugins.values():
            for handler in plugin_inst.registered_handlers:
                data.append({
                    "name": handler['name'],
                    "handler": handler['handler'].__name__,
                    "plugin": plugin_inst.name
                })
                
        columns = [
            { "field": "name", "title": "Datatype", "sortable": True },
            { "field": "handler", "title": "Handler", "sortable": True },
            { "field": "plugin", "title": "Plugin", "sortable": True }
        ]        
        
    table_data = {
        'columnsJSON': json.dumps(columns),
        'dataJSON': json.dumps(data),
        'id': 'known_attributes'
    }
    return render_template('bootstraptable.html', data=table_data)

@bp.route('system')
def system_report():
    return render_template("system_report.html")