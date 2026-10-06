#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov 19 09:05:26 2019

@author: wierinve
"""

import json
from flask import flash, Blueprint, render_template, redirect, request, url_for
from flask_login import current_user, login_required
from irods.models import Collection, CollectionMeta
from idms.web.app.utils.datafield import datafield, Datatypes
from .utils import cached_iqry
from idms.common.constants.attribute_names import ATTR_METADATA_PREFIX, ATTR_SCHEMA_IN_USE, ATTR_REFERENCE_SUFFIX
from idms.web.app.components.contacts_manager import refdata_permissions
from .utils.projectdb_api import rest_call
from datetime import datetime
from os import path

bp = Blueprint('reference', __name__, url_prefix='/reference')

reference_change_allowed = [ 'description', 'synchronize_command', 'synchronization_frequency', 'repository', 'tag', 'is_active', 'execution_environment']

def get_referencelist():
    referencelist_raw, status_code = rest_call('GET', 'reference')
    referencelist = {}
    if status_code == 200:
        #which kind of categories do we have?
        categories = sorted(set(map(lambda r:r.get("category") or "unknown", referencelist_raw)))

        for category in categories:
            refsets_in_category = [r for r in referencelist_raw if (r.get("category") or "unknown")  ==category]

            for reference in refsets_in_category:
                reference["status"] = "WARNING"  #default state
                reference["days_since_update_str"] = "N/A"
                if reference["importer_state"]:
                    ts_last_updated = reference["importer_state"]["last_updated"]
                    #print(f"last update: {ts_last_updated}")
                    ts_now = datetime.now().timestamp()
                    if ts_last_updated > 0:
                        delta_last_updated = ts_now - ts_last_updated
                        reference["status"] = "OK"
                        if delta_last_updated > (4* reference["synchronization_frequency"]):
                            reference["status"] = "WARNING"
                        days_since_update = int(delta_last_updated / (24*60*60))
                        reference["days_since_update"] = days_since_update
                        reference["days_since_update_str"] = "< 1 day"
                        if days_since_update > 0:
                            reference["days_since_update_str"] = f"{days_since_update} days"
                    if reference["importer_state"]["error_count"] > 0:
                        reference["status"] = "ERROR"

                referencelist.setdefault( category, {})
                referencelist[category][ reference['name'] ] = reference 

    return referencelist


@bp.route('/')
@login_required
def show_reference_datasets():
    """
    Return a web page with a list of all reference datasets

    url params:
        reference_dataset: switch to reference_datasets page and show <reference_dataset>
        process: swicth to processes page and show <processid> 
    """
    refdata_coll = current_user.refdata_coll 
    if not refdata_coll:
        flash('Reference data collection is not configured. Contact your administrator', 'error')
            
    reference_dataset = request.args.get('reference_dataset', '')
    reference_dataset_list = get_referencelist()
    return render_template('referencedatasets.html', referencedatasets=reference_dataset_list, reference_dataset=reference_dataset)

@bp.route('/details')
@login_required
def show_reference_details():
    """
    Shows page with reference dataset settings
    """
    reference_id = request.args.get('name', '', type=str)

    all_references_raw, result = rest_call('GET', 'references')
    all_references = [ reference['name'] for reference in all_references_raw]

    reference_details_raw, result = rest_call('GET', 'reference/{}'.format(reference_id))
    reference_details = {}
    for attr in ['description', 'id', 'name', 'creation_date',  'owner',  'execution_environment', 'synchronize_command', 'precheck_command', 'repository', 'tag', 'is_active']:
        val = reference_details_raw.get(attr, '')
        if val == None:
            val = ''
        reference_details[attr] = val
    for attr in ['synchronization_frequency']:
        val = reference_details_raw.get(attr, 0)
        if val == None:
            val = 0
        reference_details[attr] = val

    reference_versions = [] 

    import_state_raw, result = rest_call('GET', 'reference/{}/importer_state'.format(reference_id))
    import_state = {}
    for attr in [  "current_version",  "id",  "last_task", "last_task_pid",   "last_task_message",  "referenceid", 'error_count', 'dataset_id']:
        import_state[attr] = import_state_raw.get(attr, '')
    for attr in [  "last_synchronized",  "last_updated", 'last_prechecked', 'last_task_changed' ]:
        import_state[attr] = import_state_raw.get(attr, 0)
        if import_state[ attr ] != 0:
            import_state[ f'{attr}_iso' ] = datetime.fromtimestamp(import_state[attr]).strftime("%d-%m-%Y %H:%M:%S")
        else:
            import_state[ f'{attr}_iso' ] = "---"

    available_tags, r = rest_call('GET', f'reference/{reference_id}/tags')
    if r != 200:
        available_tags = []
    
    # Set prefix for metadata
    metadata_prefix = ATTR_METADATA_PREFIX
    
    collection = f"/{current_user.irods_zone}/{current_user.refdata_coll}/{reference_details['name']}"

    return render_template('reference_details.html', 
                           RD=reference_details, 
                           all_references=all_references, 
                           reference_versions=reference_versions, 
                           import_state=import_state,
                           available_tags=available_tags,
                           collection=collection,
                           prefix=ATTR_METADATA_PREFIX,
                           attribute_type=ATTR_SCHEMA_IN_USE + ATTR_REFERENCE_SUFFIX)


@bp.route('/activate_reference', methods=['GET', 'POST'])
@login_required
def activate_reference():
    requestdata = request.args.to_dict()
    reference = requestdata.get('reference')
    data = { 'is_active': 1 }
    response, result = rest_call('PUT', 'reference/{}'.format(reference), data=data)
    if result != 200:
        flash(response.get('message', f'Error: {result}'), 'error')
        location=f'reference_dataset={reference}'
    else:
        location = f'reference_dataset={reference}'

    return redirect(f'{url_for("reference.show_reference_datasets")}?{location}')

@bp.route('/deactivate_reference', methods=['GET', 'POST'])
@login_required
def deactivate_reference():
    requestdata = request.args.to_dict()
    reference = requestdata.get('reference')
    data = { 'is_active': 0 }
    response, result = rest_call('PUT', 'reference/{}'.format(reference), data=data)
    if result != 200:
        flash(response.get('message', f'Error: {result}'), 'error')
        location=f'reference_dataset={reference}'
    else:
        location = f'reference_dataset={reference}'

    return redirect(f'{url_for("reference.show_reference_datasets")}?{location}')


@bp.route('/update_reference', methods=['GET', 'POST'])
@login_required
def update_reference_settings():
    """
    Called when changing reference dataset settings from the web interface
    The request contains an <action> variable that specifiec the kind of update
    that is requested
    """

    requestdata = request.form.to_dict()
    location = ''
    reference = requestdata.get('reference')
    action = requestdata.get('action')

    if action == 'update_reference':
        data = {}
        for attr in reference_change_allowed:
            if attr in requestdata:
                data[attr] = requestdata[attr]

        response, result = rest_call('PUT', 'reference/{}'.format(reference), data=data)
        if result != 200:
            flash(response.get('message', f'Unknown error: {result}'), 'error')
        else:
            flash( 'update successful', 'info')
        location=f'reference_dataset={reference}'
    elif action == 'add_reference':
        category = requestdata.get('reference_category')
        response, result = rest_call('POST', 'reference', data={'name': reference, 
                                                                'category': category,
                                                                'owner': current_user.username, 
                                                                'is_active': 0})
        if result == 201:
            flash( 'creation successful', 'info')
            location = f'reference_dataset={reference}'
        else:            
            flash(response.get('message', 'Unknown error'), 'error')
            location='page=reference'
    elif action == 'remove_reference':
        response, result = rest_call('DELETE', 'reference/{}'.format(reference))
        location='page=reference'

    return redirect(f'{url_for("reference.show_reference_datasets")}?{location}')


@bp.route('/changeVersionName', methods=['GET', 'POST'])
@login_required
def change_version_name():
    requestdata = request.values.to_dict()
    reference_id = requestdata.get( 'reference_id')
    version_id = requestdata.get( 'version_id' )
    new_name = requestdata.get( 'new_name')
    response, result = rest_call('PUT', f'reference/{reference_id}/versions/{version_id}', data={'version_name': new_name})
    return (response, result)


@bp.route('/resetErrorCount')
@login_required
def reset_error_counter():
    requestdata = request.values.to_dict()
    reference_id = requestdata.get( 'reference_id')
    response, result = rest_call('PATCH', f'reference/{reference_id}/importer_state', data={'error_count': 0})
    return (response, result)


@bp.route('/versions')
@login_required
def versions_table():
    reference_id = request.args.get('id', '', type=str)
    refdb_name = request.args.get('project', '', type=str)
    #in bio_rest we need to fix the api from reference_id to reference.id! 
    response, result = rest_call('GET', f'reference/{reference_id}/versions' )

    if result != 200:         
        flash(response.get('message', 'Unknown error'), 'error')
        location='page=reference'

    #format more nicely
    db_versions = [
                 {
                    'reference_id': reference_id,
                    'version_id': v['id'],
                    'is_valid': v['is_valid'],
                    'version': v['version'],
                    'creation_date': v['creation_date'],   
                    'dataset_id': v['dataset_id'],
                    'version_name': v['version_name']
                 }
                 for v in response ]

    #additionally get the collections
    refdata_coll = current_user.refdata_coll 

    q1 = cached_iqry.qcollchildren( f"/{current_user.irods_zone}/{refdata_coll}/{refdb_name}")
    version_colls = { path.basename(c[Collection.name]): 
                        {
                            "irods_path": c[Collection.name],
                            "irods_display_path": f"<span class='path-change' data-path='{c[Collection.name]}'>{path.basename(c[Collection.name])}</span>" ,
                            'irods_create_time': datafield('create_time', c[Collection.create_time], Datatypes.TIMESTAMP).htmlstring,
                            'irods_owner_name': c[Collection.owner_name]
                        } 
                    for c in q1 }
    
    #and their metadata
    REFDATA_META = ( 'reference_dataset', 'sys::data::type', 'sys::dataset_id'  )
    for key, items in version_colls.items():
        q2 = cached_iqry.qcollmeta(items["irods_path"])
        meta_of_c = { m[CollectionMeta.name]: m[CollectionMeta.value] for m in q2  if m[CollectionMeta.name].startswith( REFDATA_META ) }
        version_colls[key]["irods_metadata"] = meta_of_c


    def add_irods_data(db_version):
        key = str(db_version["version"]) #this is the basename of the irods collection
        if key in version_colls:
            return db_version | version_colls[key]
        return db_version

    data_ext = list(map( add_irods_data, db_versions))

    options = {
        'download_btn': False,
        'view_btn': False,
        'delete_btn': False
    }
    return render_template('versions_table.html', data=json.dumps(data_ext), display_field=None, options=options)



@bp.route('/import_state')
@login_required
def import_state():
    reference_id = request.args.get('name', '', type=str)

    path=f"/{current_user.irods_zone}/projects/refdata/{reference_id}"
    return render_template('colltable.html', path=path, display_field=None)


@bp.route('contactmanager', methods=['GET'])
def contactmanager():
    objectname = request.args.get('object')
    objecttype = request.args.get('objecttype')
    # can_modify will be used to hide/show the add/delete buttons
    # if we are not sure, set it to true
    # the rest service will enforce permissions anyway
    can_modify = True
    permissions = None 
    if objecttype == 'refdata':
        permissions = refdata_permissions(objectname)
        can_modify = permissions.get('managers', True)

    contacts, result = rest_call('GET', 'reference/{}/contacts'.format(objectname))
    
    return render_template('contactmanager.html', object=objectname, objecttype=objecttype, contacts=contacts, can_modify=can_modify, project_permissions=permissions)
