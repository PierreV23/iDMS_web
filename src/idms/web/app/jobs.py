#!/usr/bin/env python3
"""
Created on Mon Nov 18 13:49:12 2019

@author: wierinve
"""

import json
import os
import sys
from datetime import datetime, timezone

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from graphviz import Digraph
from idms.web.app.utils.datafield import datafield, Datatypes
from idms.web.app.config.displayfields import PG_FIELDS, PG_JOB_FIELDS
from idms.common.irods.irods_sessions import irods_manager
from idms.common.filesys.fs_irods import fs_irods
from idms.common.irods.irods_sessions import irods_manager
from irods.column import Criterion
from irods.exception import CAT_NO_ACCESS_PERMISSION, DataObjectDoesNotExist
from irods.models import Collection, CollectionMeta
from idms.common.constants.attribute_names import (
    ATTR_RUNSHEET_ID,
    ATTR_RUNSHEET_CREATETIME,
    ATTR_RUNSHEET_PROCESSGROUPGUID
)

from .collbrowser import shape
from .utils import cached_iqry
from .utils.database import jobs_db
from .utils.flaskcache import cache, key_userzone, key_zone

bp = Blueprint('jobs', __name__, url_prefix='/jobs')


MAX_READ_LOG_BYTES = 10000000

# @bp.before_request
# def before_request_func():
#     # This ensures the flash error message will show up if the job table is not available
#     jobs_db.connection()

def utc_to_local(utc_dt):
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=None)

def timestamp_to_local(timestamp):
    utc_dt = datetime.utcfromtimestamp(float(timestamp))
    return utc_to_local(utc_dt)

@bp.route('/api/pgprocs')
def processgroupprocs():
    PGFIELDS = {
        'sys::runsheet::id': ('runsheet', 'runsheet'),
        'sys::runsheet::description' : ('description', 'text'),
        'sys::runsheet::state': ('state', 'text'),
        'sys::run::result': ('result', 'text'),
        'user::run::exit_code': ('result', 'text'),
        'sys::run::start_time': ('start', 'timestamp'),
        'sys::run::finish_time': ('end', 'timestamp'),
    }
    processgroupguid = request.args.get('processgroupguid')
    q = cached_iqry.qcollbymeta('sys::runsheet::processgroupid', processgroupguid)
    result = []
    for r in q:
        metadata = cached_iqry.qcollmetadict(r[Collection.name])
        job = {}
        for field in PGFIELDS:
            if metadata.get(field):
                job[PGFIELDS[field][0]] = datafield(PGFIELDS[field][0], metadata.get(field,''), PGFIELDS[field][1]).htmlshort
#        job = { PGFIELDS[field][0]: datafield(PGFIELDS[field][0], metadata.get(field,''), PGFIELDS[field][1]).htmlstring for field in PGFIELDS }
        result.append(job)
    return { 'rows': result }


@bp.route('_filterdata')
@cache.cached(timeout=60, key_prefix=key_zone)
def filterdata():
    # Determine prepopulated filter values for 'select' filters
    field = request.args.get('field', type=str)
    table = request.args.get('table', type=str)

    with jobs_db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT DISTINCT {field} FROM {table} WHERE {field} IS NOT NULL")
        results = cursor.fetchall()
    filter_values = {v[0]:v[0] for v in results}
    return jsonify(filter_values)


@bp.route('_pglist')
def pglist():
    # JS Frontend code will redirect to login page
    if not current_user.is_authenticated:
        return "Unauthorized", 401
    
    #POPULATE processgrouplist
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 999, type=int)
    filters = json.loads(request.args.get('filter', '{}'))
    order = request.args.get('order', 'desc')
    sort = request.args.get('sort', 'create_time')
    search = request.args.get('search')
    processgroupid = request.args.get('processgroupid', None, type=str)
    current_user.settings['default_project'] = filters.get('projectid', '')

    where_clause = 'WHERE 1=1'
    join_clause = ''

    if processgroupid:
        where_clause += f' AND processgroupid = {processgroupid}'

    if search:
        join_clause = "JOIN rivm_mat_jobtable AS jt USING(processgroupid)"
        where_clause += f" AND (jt::text LIKE '%%{search}%%' OR pg::text LIKE '%%{search}%%')"

    # Apply filters on pgs_query ('select' and 'input')
    for _, field_attrs in PG_FIELDS.items():
        field_name = field_attrs['field']
        filter_value = filters.get(field_name)
        filter_control = field_attrs.get('filtercontrol')
        if not filter_value or filter_control is None:
            continue
        if filter_control == 'select':
            where_clause += f" AND pg.{field_name} = '{filter_value}'"
        if filter_control == 'input':
            where_clause += f" AND pg.{field_name} LIKE '%%{filter_value}%%'"

    sqlj = f"""SELECT DISTINCT pg.*, COUNT(pg.*) OVER () AS total_count
                FROM rivm_v_processgroups AS pg
                {join_clause}
                {where_clause}
                ORDER BY {sort} {order}
                OFFSET {offset} LIMIT {limit}"""

    pgs_query = jobs_db.connection().sql(sqlj)
    count_processgroups = pgs_query[0]['total_count'] if len(pgs_query) else 0

    # format data pgs_query
    result = []
    for processgroup in pgs_query:
        record = {}
        for f in PG_FIELDS:
            dbkey = PG_FIELDS[f]['field']
            val = processgroup.get(dbkey, None)
            if val is not None:
                formatted = datafield(dbkey, val, PG_FIELDS[f]['format'])
                record |= { dbkey: formatted.htmlshort, f'_{dbkey}': formatted.value }
        result.append(record)

    return { 'rows': result, 'filters': filters, 'total': count_processgroups }

@bp.route('_jobrefresh')
def jobs_refresh():
    sql = 'SELECT refresh_time FROM rivm_mat_jobtable LIMIT 1'
    result = jobs_db.connection().sql(sql)
    if not result:
        return jsonify('unknown')
    else:
        return jsonify(datafield('refresh_time', float(result[0]['refresh_time']), Datatypes.TIMESTAMP).htmlshort)
 

@bp.route('_pgjobs')
def pgjobs():
# display jobs under a processgroupid
    processgroupid = request.args.get('processgroupid', None, type=str)

    result = []

    sql = f"SELECT * FROM rivm_mat_jobtable WHERE processgroupid = '{processgroupid}'"

    jobs_query = jobs_db.connection().sql(sql)

    for job in jobs_query:
        record = {}
        for f in PG_JOB_FIELDS:
            dbkey = PG_JOB_FIELDS[f]['field']
            val = job.get(dbkey, None)
            if val is not None:
                formatted = datafield(dbkey, val, PG_JOB_FIELDS[f]['format'])
                record |= { dbkey: formatted.htmlshort, f'_{dbkey}': formatted.value }
        result.append(record)

    columns = []
    for f in PG_JOB_FIELDS:
        if PG_JOB_FIELDS[f].get('filtercontrol') == 'select':
            f1 = {}
            for v in result:
                key = v.get(f'_{PG_JOB_FIELDS[f]["field"]}')
                if key:
                    f1[key] = key
            filterdata = json.dumps(f1)
            PG_JOB_FIELDS[f]['filterdata'] = f"json:{filterdata}"
        columns.append(PG_JOB_FIELDS[f])

    return { 'columns': columns, 'rows': result }

def get_queue_status():
    job_queues_metadata = cached_iqry.qcollmetadict(
        f"/{current_user.irods_zone}/system/runsheet"
    )
    job_queues_prefix = "sys::enable::"
    disabled_job_queues = [
        queue_name.split(job_queues_prefix)[1]
        for queue_name, queue_state in job_queues_metadata.items()
        if queue_name.startswith(job_queues_prefix)
        if queue_state == "false"
    ]
    return disabled_job_queues

@bp.route('/pg')
def show_pg():
    processgroupguid = request.args.get('processgroupguid', None, type=str)
    default_project = current_user.settings.get('default_project', '')
    visible_columns = current_user.settings.get('processgroups::columns', [v["field"] for v in PG_FIELDS.values()])
    current_user.settings['jobs::view'] = 'processgroups'
    disabled_queues = get_queue_status()
    return render_template('pglist.html', default_project=default_project
                            , processgroupguid=processgroupguid, columns=PG_FIELDS, visible_columns=visible_columns, disabled_queues=disabled_queues)

NAME_LENGTH = 15

def shortname(name,l):
    s = name
    if len(name)>l:
        s = '...' + name[-l+4:]
    return s


@bp.route('/processgraph')
def processgraph():
    runsheet_coll = request.args.get('runsheet', '/', type=str)
    graph = Digraph('processgraph')

    # We need the processgroupID
    processgroupid = cached_iqry.qcollmetavalstatic(runsheet_coll, 'sys::runsheet::processgroupid')
    q = cached_iqry.qcollbymeta('sys::runsheet::processgroupid', processgroupid)
    colls = [ r[Collection.name] for r in q ]

    for coll in colls:
        state = cached_iqry.qcollmetaval(coll, 'sys::runsheet::state', default='unknown').lower()

        if state == 'done':
            state = cached_iqry.qcollmetaval(coll, 'sys::run::result').lower()

        # draw the nodes
        penwidth = '3' if runsheet_coll == coll else '1'
        layout, legends = shape(state, penwidth=penwidth)

        graph.node(coll, label=cached_iqry.qcollmetavalstatic(coll, 'sys::runsheet::description'), margin = '0.1, 0', style=layout['style'], penwidth=layout['penwidth'],
            shape=layout['shape_process'], fillcolor=layout['fillcolor'], URL=url_for('jobs.jobdetails', name=cached_iqry.qcollmetaval(coll, ATTR_RUNSHEET_ID)))

    for coll in colls:
        ir = cached_iqry.qcollmetaval(coll, 'sys::pipeline::input_collection_id')
        input_colls = [ c for c in colls if cached_iqry.qcollmetavalstatic(c, 'sys::dataset_id') == ir ]
        if input_colls:
            for input_coll in input_colls:
                graph.edge(input_coll, coll)
        else:
            q = cached_iqry.qcollbystaticmeta('sys::dataset_id', ir)
            src = None
            for r in q:
                src = r[Collection.name]
            if src:
                layout, legends = shape('source')
                graph.node(src, shortname(src, NAME_LENGTH), shape=layout['shape'], margin = '0.1, 0', fillcolor=layout['fillcolor'], style=layout['style'],
                        tooltip = layout['tooltip'] + ': ' + src,
                        URL=url_for('collbrowser.collbrowser', path=src))
                graph.edge(src, coll)

    graph.graph_attr['rankdir'] = 'LR'
    graph.graph_attr['fontsize'] = '15'

    return graph.pipe(format='svg').decode('utf-8')

@bp.route('/jobdetails')
@login_required
def jobdetails():
    #this could be either the object-name of the yaml file or meta information attached to the collection
    jobnaam = request.args.get('name', '', type=str)
    processgroupguid = request.args.get('processgroupguid', '', type=str)

    details = {}
    metadata = {}

    # the jobnaam is refering to metainfo on a collection
    q = []
    if jobnaam:
        q = cached_iqry.qcollbystaticmeta(ATTR_RUNSHEET_ID, jobnaam)
    elif processgroupguid:
        q = cached_iqry.qcollbystaticmeta(ATTR_RUNSHEET_PROCESSGROUPGUID, processgroupguid)
    if len(q) < 1:
        flash(f'Cannot find unique job collection for {jobnaam}', 'error')
        return redirect(url_for('jobs.show_pg'))
    runsheet = q[0][Collection.name]
    if not jobnaam:
        jobnaam = cached_iqry.qcollmetaval(runsheet, ATTR_RUNSHEET_ID)
    metadata = cached_iqry.qcollmetadict(runsheet)
    details['Runsheet collection'] = datafield('runsheet',  runsheet, Datatypes.IRODS_COLLECTION)
    details['Create time'] = datafield('create_time', float(metadata[ATTR_RUNSHEET_CREATETIME]), Datatypes.TIMESTAMP)

    FIELDS = {
        'sys::run::start_time': ('Start time', 'timestamp'),
        'sys::run::finish_time': ('End time', 'timestamp'),
        'sys::runsheet::projectID': ('Project ID', 'projectid'),
        'sys::runsheet::processID': ('Process ID', 'process'),
        'sys::runsheet::description': ('Description', 'text'),
        'sys::runsheet::processgroupid': ('Processgroup Instance', 'processgroupguid'),
        'sys::runsheet::processgroup': ('Processgroup', 'text'),
        'sys::run::exit_code': ('Result', 'int'),
        'sys::run::output_collection': ('Output Collection', 'irods_collection'),
        'sys::run::account': ('Run Account', 'irods_user'),
        'sys::run::input_dir': ('Input directory', 'directory'),
        'sys::run::output_dir': ('Output directory', 'directory'),
        'sys::run::owner': ('Job owner', 'irods_user'),
        'sys::run::service_account': ('Sevice account', 'irods_user'),
        'sys::run::requestinguser': ('Requesting user', 'irods_user'),
        'sys::run::pipeline_dir': ('Pipeline run directory', 'directory'),
        'sys::run::run_dir': ('Pipeline run directory', 'directory'),
        'sys::run::site': ('Site', 'text'),
        'sys::run::cluster': ('Cluster', 'text'),
        'sys::run::useprojectaccount': ('Use project service account', 'boolean'),
        'sys::runsheet::repo': ('Git repository', 'url'),
        'sys::runsheet::tag': ('Git tag', 'tag'),
        'sys::runsheet::distribution': ('Distribution pipeline', 'boolean'),
        'sys::runsheet::omit_staging': ('Omit staging', 'boolean'),
        'sys::runsheet::omit_bringonline': ('Omit bring input data online', 'boolean'),
        'sys::runsheet::lsf_queue': ('LSF Queue', 'lsf_queue'),
        'sys::run::lsf_jobid': ('LSF Job ID', 'text'),
        'sys::run::pid': ('Process PID', 'text'),
    }
    MULTI_FIELDS = {
        'sys::runsheet::input_collection': ('Input Collection', 'irods_collection'),
        'sys::runsheet::dataobject': ('Dataobject', 'irods_object')
    }
    MULTI_PLACEHOLDER_FIELDS = {
        'sys::pipeline::refdata::[0]::reference_version_dataset_id': ('Reference Datasets', 'text')
    }
    for field in FIELDS:
        if field in metadata:
            details[FIELDS[field][0]] = datafield(field, metadata[field], FIELDS[field][1])
    multi = {}
    for field, attrs in MULTI_FIELDS.items():
        values = cached_iqry.qcollmetavals(runsheet, field)
        datavalues = [ datafield(field, value[CollectionMeta.value], attrs[1]).htmlstring for value in values ]
        multi[attrs[0]] = datavalues
    for field, attrs in MULTI_PLACEHOLDER_FIELDS.items():
        values = cached_iqry.qcollmetavals_with_placeholder(runsheet, field)
        datavalues = [ datafield(field, value[CollectionMeta.value], attrs[1]).htmlstring for value in values ]
        multi[attrs[0]] = datavalues
    processgroupid = metadata.get('sys::runsheet::processgroupid', '')
    return render_template('jobdetails.html', details=details, multi=multi, runsheet=runsheet, processgroupid=processgroupid, jobnaam=datafield('jobnaam', jobnaam, Datatypes.RUNSHEET))


@bp.route('alljoblogs')
def all_job_logs():
    jobnaam = request.args.get('name', '', type=str)
    with irods_manager.session(current_user) as session:

        # the jobnaam is refering to metainfo on a collection
        query = session.query(Collection.name, CollectionMeta).filter(
                Criterion('=', CollectionMeta.name, ATTR_RUNSHEET_ID )).filter(
                Criterion('=', CollectionMeta.value, f'{jobnaam}'))
        # Find the job log file
        results = query.get_results()
        job = next(results)
        runsheet = job[Collection.name]
        q2 = session.query(CollectionMeta.name, CollectionMeta.value).filter( \
                Criterion('=', Collection.name, runsheet ))
        metadata = {meta[CollectionMeta.name] : meta[CollectionMeta.value] for meta in q2}

        # Find output logs. Search first in __system__/log, then in log
        logfiles = {}
        for subdir in ('__system__/log', 'log'):
            log_location = '{}/{}'.format(metadata.get('sys::run::output_collection', '/INVALID_PATH'), subdir)
            if fs_irods(session=session).folderexists(log_location):
                logfiles = _get_logfiles(log_location)
                break
    return render_template('joblogs.html', jobnaam = datafield('jobnaam', jobnaam, Datatypes.RUNSHEET), logs = logfiles)

@bp.route('joblog')
def job_log():
    jobnaam = request.args.get('name', '', type=str)
    collection = ''
    colls = cached_iqry.qcollbymeta('sys::runsheet::id', jobnaam)
    if len(colls) == 1:
        with irods_manager.session(current_user) as session:
            for subdir in ('__system__/log', 'log'):
                log_location = '{}/{}'.format(colls[0][Collection.name], subdir)
                if fs_irods(session=session).folderexists(log_location):
                    collection = log_location
                    break        
    return render_template('joblog.html', jobnaam=datafield('jobnaam', jobnaam, Datatypes.RUNSHEET), collection=collection)


def _get_logfiles(location, subdir=''):
    logs = {}
    currentdir = os.path.join(location, subdir)
    with irods_manager.session(current_user) as session:
        for subdir2 in fs_irods(session=session).lsdirnames(currentdir):
            logs.update(_get_logfiles(location, subdir=os.path.join(subdir, subdir2)))
        logs.update({ os.path.join(subdir, filename): os.path.join(currentdir, filename) for filename in fs_irods(session=session).lsfilenames(currentdir) })
    return(logs)

@bp.route('/_joblog')
@cache.cached(timeout=120, key_prefix=key_userzone)
def show_logfile():
    # result object
    result = {
        "error": False,
        "data": None,
        "msg": None
    }


    path = request.args.get('path', '', type=str)
    filename = path.split("/")[-1]
    with irods_manager.session(current_user) as session:
        try:
            obj = fs_irods(session=session).getfile(path)
        except DataObjectDoesNotExist:
            result["msg"] = f"The {path} does not exist"
            result["error"] = True
            return result

        try:
            with obj.open('r') as f:
                data = f.read(MAX_READ_LOG_BYTES)
        except CAT_NO_ACCESS_PERMISSION: # if encountered the error
            result["msg"] = f"You don't have permission to access {filename}"
            result["error"] = True
            return result # return the result, otherwise data is being read

        if sys.getsizeof(data) >= MAX_READ_LOG_BYTES:
            result["data"] = f"{data.decode('utf-8')}\n!!! log truncated to max {MAX_READ_LOG_BYTES} bytes !!!"
            return result

        # if everything went well
        result["data"] = data.decode('utf-8')

    return result
