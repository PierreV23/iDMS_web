#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Apr 15 10:46:50 2020

@author: wierinve
"""
import json
import os
import time
import irods.exception
from flask import Blueprint, render_template, redirect, jsonify, request, url_for, current_app
from flask_login import current_user, login_required
from irods.meta import iRODSMeta
from irods.models import Collection, CollectionMeta, DataObject, Resource, DataObjectMeta, RuleExec
from irods.column import Criterion
from irods.query import SpecificQuery
from idms.common.irods.irods_helper import getmetaitem, get_or_set_uid
from idms.web.app.utils.datafield import datafield, Datatypes
from idms.common.irods.irods_sessions import irods_manager
from idms.web.app.config.displayfields import RESOURCE_PROPS
from idms.web.app.utils.auth import auth_endpoint
from idms.common.constants.attribute_names import (
    ATTR_LOCK, ATTR_CONSISTENCY_PREFIX, 
    ATTR_COLLSIZE, ATTR_COLLSIZE_TIME,
    ATTR_ARCHIVE_LASTCHECK, ATTR_ARCHIVE_LASTRUN,
    ATTR_ARCHIVE_STATUS, ATTR_ARCHIVE_STATUSMSG,
    ATTR_ARCHIVE_STATE, ATTR_ARCHIVE_DESIREDSTATE,
    ATTR_ARCHIVE_TARFILE, ATTR_ARCHIVE_MANIFESTFILE
)
from idms.common.constants.constants import (
    DATA_REPL_STATUS, ACTIVE_RUNSHEET_STATES
)
from idms.web.app.utils import cached_iqry
from .utils import flaskcache
from idms.web.app.accounting_page import *

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/_issues')
def query_issues():
    if not current_user.is_admin:
        return('<tr><td colspan=3>Access denied</td></tr>')
    data = ''
    with irods_manager.session(current_user) as session:
        query = SpecificQuery(session, alias='checksums_differ')
        for result in query:
            base, name = os.path.split(result[0])
            data = '{}<tr><td colspan=5><a href="{}?path={}">{}</a></td></tr>'.format(data, url_for("collbrowser.collbrowser"), base, result[0])
            q = session.query(DataObject.path,
                                DataObject.resource_name,
                                DataObject.size,
                                DataObject.checksum).filter(
                Criterion('=', Collection.name, base)).filter(
                Criterion('=', DataObject.name, name))
            for objfile in q:
                data = '{}<tr><td></td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(data,
                                                                objfile[DataObject.path],
                                                                objfile[DataObject.resource_name],
                                                                objfile[DataObject.size],
                                                                objfile[DataObject.checksum])
    return data

@bp.route('/_consistency')
def data_consistency():
    # Handy to have the resource hosts in the table:
    with irods_manager.session(current_user) as session:
        query = session.query(Resource)
        resources = { r[Resource.name]: r[Resource.location] for r in query }
        query = session.query(Collection.name, CollectionMeta.name, CollectionMeta.value).filter(
            Criterion('like', CollectionMeta.name, 'sys::consistency::%::errors'))
        results = [
            { 'collection': r[Collection.name],
            'collink'   : datafield('collection', r[Collection.name], Datatypes.IRODS_COLLECTION).htmlstring,
            'resource'  : r[CollectionMeta.name].split('::')[2],
            'location'  : resources.get(r[CollectionMeta.name].split('::')[2], 'UNKNOWN'),
            'issues'    : r[CollectionMeta.value]
            } for r in query ]
    return jsonify(results)

@bp.route('/_replstate')
def data_replstate():
    """Get objects that have a replication state other than GOOD_REPLICA
    """
    with irods_manager.session(current_user) as session:
        results = []
        for value in ('0', '2', '3', '4'):
            query = session.query(Collection.name, DataObject.name, DataObject.replica_number).filter(
                Criterion('=', DataObject.replica_status, value)
            )
            results += [
                { 'path': os.path.join(r[Collection.name], r[DataObject.name]),
                  'replica': r[DataObject.replica_number],
                  'replstate': value,
                  'replstate_name': DATA_REPL_STATUS.get(value, 'UNKNOWN_VALUE')
                } for r in query
            ]
    return jsonify(results)

@bp.route('/_condetails', methods=["GET"])
def consistency_details():
    collection = request.args.get('collection')
    resource = request.args.get('resource')
    attr = f'sys::consistency::{resource}'
    criteria = [
        Criterion('=', Collection.name, collection),
        Criterion('like', Collection.name, f'{collection}/%')
    ]

    data = []
    if collection:
        for criterium in criteria:
            with irods_manager.session(current_user) as session:
                q = session.query(Collection.name, DataObject.name, DataObject.path, DataObject.replica_number, DataObjectMeta).filter(criterium).filter(
                    Criterion('like', DataObjectMeta.name, f'{attr}%')).filter(
                    Criterion('=', DataObject.resource_name, resource)
                    )
                for r in q:
                    # Try to add only replicas that have the error
                    attr_split = r[DataObjectMeta.name].split('::')
                    if len(attr_split) == 4:
                        replica_number = int(attr_split[3])
                        if r[DataObject.replica_number] != replica_number:
                            continue
                        data.append({
                            'dataobject': os.path.relpath(os.path.join(r[Collection.name], r[DataObject.name]), start=collection),
                            'path': r[DataObject.path],
                            'error': r[DataObjectMeta.value],
                            'replica_number': r[DataObject.replica_number]
                        })

    columns = [
        { "field": "dataobject", "title": "DataObject", "sortable": True },
        { "field": "path", "title": "Path", "sortable": True },
        { "field": "replica_number", "title": "Replica number", "sortable": True },
        { "field": "error", "title": "Error", "sortable": False }
    ]
    data = {
        'columnsJSON': json.dumps(columns),
        'dataJSON': json.dumps(data),
        'id': collection.replace('/', '_')
    }
    return render_template('bootstraptable.html', data=data)

@bp.route('/issues')
@login_required
def issues():
    return render_template('issues.html')

@bp.route('/messages')
@login_required
def messages():
    return render_template('messages.html')


@bp.route('/_aract', methods=['POST'])
def archive_action():
    requestdata = request.form.to_dict()
    action = requestdata.get('action')
    collection = requestdata.get('collection')
    with irods_manager.session(current_user) as session:
        try:
            collobj = session.collections.get(collection)
        except irods.exception.CollectionDoesNotExist:
            return jsonify({'message': 'Collection does not exist'})
        if action == 'remove_archive':
            state =  getmetaitem(collobj, ATTR_ARCHIVE_STATE)
            if state is None:
                return jsonify({'message': 'Cannot modify collection with unknown state'})
            if state.count('1')<2: # Dont remove archive if no other copy is present
                return jsonify({'message': 'Cannot remove last data copy in collection'})
            for attr in (ATTR_ARCHIVE_TARFILE, ATTR_ARCHIVE_MANIFESTFILE):
                filename = getmetaitem(collobj, attr)
                if filename and cached_iqry.qpathobjecttype(filename) == 'dataobject':
                    session.data_objects.unlink(filename)
                    collobj.metadata.remove(iRODSMeta(attr, filename))
        if action in ('clear_status', 'remove_archive') :
            for attr in (ATTR_ARCHIVE_STATUS, ATTR_ARCHIVE_STATUSMSG, ATTR_ARCHIVE_LASTCHECK):
                val = getmetaitem(collobj, attr)
                if val:
                    collobj.metadata.remove(iRODSMeta(attr, val))
    return jsonify({'status':'ok'})

@bp.route('_archissue', methods=['GET'])
@auth_endpoint
def archive_issues():
    # Get issue collections
    with irods_manager.session(current_user) as session:
        query = session.query(Collection.name, CollectionMeta.value).filter(
            Criterion('=', CollectionMeta.name, ATTR_ARCHIVE_STATUS)).filter(
            Criterion('!=', CollectionMeta.value, 'OK'))
        items = []
        for result in query:
            statusmsg = ""
            coll = session.collections.get(result[Collection.name])
            statusmsg = getmetaitem(coll, ATTR_ARCHIVE_STATUSMSG, default="")
            allow_remove = False
            state = getmetaitem(coll, ATTR_ARCHIVE_STATE)
            if state and state.count('1')>1:
                allow_remove = True
            items.append({
                'collection': datafield('Collection', result[Collection.name], Datatypes.IRODS_COLLECTION),
                'status': result[CollectionMeta.value],
                'statusmsg': statusmsg,
                'allow_remove': allow_remove
            })
    return render_template('archive_issues.html', items=items)


@bp.route('/queues')
@login_required
def admin():
    if not current_user.is_admin:
        return render_template('denied.html')
    queues = {}
    with irods_manager.session(current_user) as session:
        for q in ACTIVE_RUNSHEET_STATES:
            enabled = True
            path = f'/{current_user.irods_zone}/system/runsheet'
            metaquery = session.query(CollectionMeta.value).filter(
                Criterion('=', Collection.name, path)).filter(
                Criterion('=', CollectionMeta.name, f'sys::enable::{q}'))
            for meta in metaquery:
                enabled = meta[CollectionMeta.value] == 'true'
            if q == 'incoming':
                items = session.query(DataObject.id).filter(\
                    Criterion('=', Collection.name, '/rivmZone/system/runsheet/processing')).filter(\
                    Criterion('=', DataObjectMeta.name, 'sys::runsheet::state')).filter(\
                    Criterion('=', DataObjectMeta.value, q)).count(DataObject.id)
                count  = items.execute()[0][DataObject.id]
            else:
                items = session.query(Collection.id).filter(\
                    Criterion('=', CollectionMeta.name, 'sys::runsheet::state')).filter(\
                    Criterion('=', CollectionMeta.value, q)).count(Collection.id)
                count  = items.execute()[0][Collection.id]
            queues[q] = {'enabled': enabled, 'count': count}
    return render_template('queues.html', queues=queues)

@bp.route('/resource_data')
@flaskcache.cache.memoize(timeout=300, make_name=flaskcache.dep_zone)
def resource_data_cached():
    return resource_data()
    
def resource_data():
    resources =  {}    
    with irods_manager.session(current_user) as session:
        q = session.query(Resource.name)
        for r in q:
            resources[r[Resource.name]] = {}
            resource = session.resources.get(r[Resource.name])
            metadata = resource.metadata.items()
            metanames = [ m.name for m in metadata ]
            for property in RESOURCE_PROPS:
                meta_name = RESOURCE_PROPS[property].get('meta')
                if meta_name:
                    if meta_name in metanames:
                        irods_meta = resource.metadata.get_one(meta_name)
                        if RESOURCE_PROPS[property].get('unit', False):
                            value = irods_meta.units
                        else:
                            value = irods_meta.value
                        factor = RESOURCE_PROPS[property].get('factor')
                        if factor:
                            resources[r[Resource.name]][property] = float(value) / factor
                        else:
                            resources[r[Resource.name]][property] = value
    return resources
    

@bp.route('/resources')
@login_required
def resources():
    resources =  resource_data()
    return render_template('resources.html', columns=RESOURCE_PROPS, resources=resources)

@bp.route('/_update_resources', methods=['POST'])
@auth_endpoint
def update_resources():
    with irods_manager.session(current_user) as session:
        data = request.form.to_dict()
        # Create a dict of the form data
        new_settings = {}
        for d in data:
            resource, attr = d.split('__')
            value = data[d]
            if not resource in new_settings:
                new_settings[resource] = {}
            new_settings[resource][attr] = value
        for resource in new_settings:
            res_obj = session.resources.get(resource)
            for property in RESOURCE_PROPS:
                meta_name = RESOURCE_PROPS[property]['meta']
                if property in new_settings[resource]:
                    if new_settings[resource][property]:
                        try:
                            current_meta = res_obj.metadata.get_one(meta_name)
                        except KeyError:
                            current_meta = iRODSMeta(meta_name, '')
                        new_meta = iRODSMeta(meta_name, current_meta.value, current_meta.units)
                        new_value = new_settings[resource][property]
                        if RESOURCE_PROPS[property].get('factor'):
                            new_value = str(int(float(new_value) * RESOURCE_PROPS[property].get('factor') // 1))
                        if RESOURCE_PROPS[property].get('unit', False):
                            new_meta.units = new_value
                        else:
                            new_meta.value = new_value
                        res_obj.metadata[meta_name] = new_meta
                elif RESOURCE_PROPS[property].get('type') == 'bool':
                    res_obj.metadata[meta_name] = iRODSMeta(meta_name, 'false')
                else:
                    del res_obj.metadata[meta_name]

    return redirect(url_for('admin.resources'))

@bp.route('/modify')
def modify():
    data = request.args.to_dict()
    action = data.get('action')
    queue = data.get('queue', 'none')
    if action is None:
        return redirect(url_for('admin.admin'))
    if action == 'disable' or action == 'enable':
        value = 'true' if action == 'enable' else 'false'
        new_meta = iRODSMeta(f'sys::enable::{queue}', value)
        coll = os.path.join('/', current_user.irods_zone, 'system/runsheet')
        with irods_manager.session(current_user) as session:
            collobj = session.collections.get(coll)
            collobj.metadata[new_meta.name] = new_meta

    return redirect(url_for('admin.admin'))

@bp.route('/tiering/pending')
@login_required
def pending_tiering_page():
    columns = [
        { "field": "collection", "title": "Collection", "sortable": True },
        { "field": "state", "title": "State", "sortable": True },
        { "field": "desired_state", "title": "Desired state", "sortable": True },
        { "field": "status", "title": "Status", "sortable": True }
    ]
    return render_template('tiering_jobs.html', columns=columns, tablename='pending_jobs', url=url_for('admin.pending_tiering_ops'), 
                           pagetitle='Pending Data Migration Jobs', menuname='pendingtiering')

@flaskcache.cache.memoize(timeout=120, make_name=flaskcache.dep_zone)
@bp.route('/tiering/_pending')
def pending_tiering_ops():
    result = []
    with irods_manager.session(current_user) as session:
        q = session.query(Collection.name, CollectionMeta.value).filter( \
            Criterion('=', CollectionMeta.name, ATTR_ARCHIVE_STATE))
        states = { r[Collection.name]: r[CollectionMeta.value] for r in q}
        q = session.query(Collection.name, CollectionMeta.value).filter( \
            Criterion('=', CollectionMeta.name, ATTR_ARCHIVE_DESIREDSTATE))
        desired_states = { r[Collection.name]: r[CollectionMeta.value] for r in q}
        for coll, state in states.items():
            if state != ( desired_state := desired_states.get(coll)):
                try:
                    status = session.collections.get(coll).metadata.get_one(ATTR_ARCHIVE_STATUS).value
                except KeyError:
                    status = 'OK'
                result.append(
                    { 'collection': datafield('Collection', coll, Datatypes.IRODS_COLLECTION).htmlstring,
                    'state': state,
                    'desired_state': desired_state,
                    'status': status })
    return jsonify(result)


@bp.route('/tiering/active')
@login_required
def active_tiering_page():
    columns = [
        { "field": "collection", "title": "Collection", "sortable": True },
        { "field": "state", "title": "State", "sortable": True },
        { "field": "desired_state", "title": "Desired state", "sortable": True }
    ]
    return render_template('tiering_jobs.html', columns=columns, tablename='active_jobs', url=url_for('admin.active_tiering_ops'),
                           pagetitle='Active Data Migration Jobs', menuname='activetiering')

@bp.route('/tiering/_active')
def active_tiering_ops():
    result = []
    with irods_manager.session(current_user) as session:
        q = session.query(RuleExec.name)
        rules = [ r[RuleExec.name] for r in q if 'collection_tiering' in r[RuleExec.name] ]
        colls = { c.split("'")[1]: "" for c in rules }
        for coll in colls:
            m = session.collections.get(coll).metadata
            desired_state = m.get_one(ATTR_ARCHIVE_DESIREDSTATE).value
            state = m.get_one(ATTR_ARCHIVE_STATE).value
            result.append({
                'collection': datafield('Collection', coll, Datatypes.IRODS_COLLECTION).htmlstring,
                'state': state,
                'desired_state': desired_state
            })
    return jsonify(result)

@bp.route('/accounting', methods = ["GET"])
def accounting():
    api = AccountingAPI(current_app, current_user)
    accounting_data = api.get_request()
    departments = list_departments(accounting_data)
    all_department_overview = total_usage_perDepartment(accounting_data)
    per_department_overview = total_userusage_perDeparment(accounting_data)
    return render_template(
        'accounting.html',
        title = "Accounting page",
        departments = departments,
        all_department_overview = all_department_overview,
        per_department_overview = per_department_overview, )
        # main_chartdata = prepChartdata(main_display))

@bp.route('/accounting_getdate', methods = ["GET"])
def get_dates():
    # get datevalue from the selector
    start = request.args.get('start')
    end = request.args.get('end')
    acc_data = request_accdata(start, end, "DAILY", dummydata=True)
    departments = [depa for depa in list(acc_data)]
    main_display = perDepartment(acc_data)
    detailed_display = [perUser(depa, acc_data) for depa in departments]
    return redirect(
        url_for(
            "admin.accounting",
            departments = departments,
            main_display = main_display,
            detailed_display = zip(departments, detailed_display),
            main_chartdata = prepChartdata(main_display)
        )
    )

@bp.route('/collection_actions', methods= ["POST"])
def collection_actions():
    data = request.form.to_dict()
    collection = data.get('collection')
    action = data.get('action')
    if not collection or not action:
        return { "Result": "Failed" }, 400
    if action == 'remove-locks':
        meta = cached_iqry.qcollmetadict(collection)
        for m in meta:
            if m.startswith(ATTR_LOCK):
                cached_iqry.rmallcollmetaattr(collection, m)
    if action == 'rerun-tiering':
        desired_state = cached_iqry.qcollmetaval(collection, ATTR_ARCHIVE_DESIREDSTATE)
        if desired_state:
            cached_iqry.scollmetaval(collection, ATTR_ARCHIVE_DESIREDSTATE, desired_state, force=True, atomic=False)
    if action == 'remove-state':
        meta = cached_iqry.qcollmetadict(collection)
        for prefix in (ATTR_CONSISTENCY_PREFIX, ATTR_COLLSIZE, ATTR_COLLSIZE_TIME):
            for m in meta:
                if m.startswith(prefix):
                    cached_iqry.rmallcollmetaattr(collection, m)
    if action == 'reset-archive':
        cached_iqry.rmallcollmetaattr(collection, ATTR_ARCHIVE_LASTCHECK)
        cached_iqry.rmallcollmetaattr(collection, ATTR_ARCHIVE_LASTRUN)
    if action == 'make-dataset':
        with irods_manager.session(current_user) as session:
            collobj = session.collections.get(collection)
            get_or_set_uid(collobj)
    # Add a short delay, otherwise the removed metadata will still be visible
    time.sleep(0.2)
    return { "Result": "OK" }
