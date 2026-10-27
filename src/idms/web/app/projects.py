#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov 19 09:05:26 2019

@author: wierinve
"""

import json
import os
import subprocess
from flask import abort, flash, Blueprint, render_template, redirect, request, url_for, current_app
from flask_login import current_user, login_required
from flask import jsonify
from .utils.flaskcache import cache, dep_userzone, dep_zone
from irods.models import Collection, CollectionMeta, User, UserMeta
from irods.exception import CAT_NO_ROWS_FOUND
from irods.column import Criterion
from idms.web.app.utils.datafield import datafield, Datatypes
from graphviz import Digraph
from .utils import cached_iqry
from idms.common.constants.attribute_names import  (
    ATTR_UPLOAD_DEFAULT_PREFIX,
    ATTR_METADATA_PREFIX,
    ATTR_SCHEMA_IN_USE,
    ATTR_PROJECT_SUFFIX,
    ATTR_DATASET_DEFAULT_SUFFIX,
    ATTR_PROJECTID,
    ATTR_RUN_REQUESTINGUSER,
    ATTR_RUNSHEET_TAG
)
from idms.web.app.config.collbrowser import COLL_KEY_MAP
from idms.common.irods.irods_sessions import irods_manager
from .utils.projectdb_api import EPOCH, iso2dt, search, rest_call, add_checkbox
from .processstats import runspermonth, runspermetaattr, runtimedist, runtimehist

bp = Blueprint('projects', __name__, url_prefix='/projects')

@cache.memoize(timeout=600, make_name=dep_userzone)
def project_permissions(project):
    """Return True if current_user is manager of project
    """
    result = {}
    for usertype in ('users', 'managers'):
        pl, exitcode = rest_call('GET', f'projects/{project}/{usertype}')
        result[usertype] = current_user.username in [ m.get('username', '__INVALID_RECORD__') for m in pl ]
    return result

def process_permissions(process):
    pl, exitcode = rest_call('GET', f'processes/{process}/managers')
    return {'managers': current_user.username in [ m.get('username', '__INVALID_RECORD__') for m in pl ] }

def get_projectlist():
    pl, result = rest_call('GET', 'projects')
    projectlist = { p['name']: p for p in pl }
    #projectlist = sorted(projectlist)
    return projectlist

def get_processlist(project):
    pl, result = rest_call('GET', f'projects/{project}/processes')
    processes = []
    if result == 200:
        processes = {p["name"]: p for p in pl}
    return processes

def get_processgrouplist(project):
    pl, result = rest_call('GET', f'projects/{project}/processgroups')
    processgroups = []
    if result == 200:
        processgroups = [ p['name'] for p in pl ]
    return processgroups

def get_process2list():
    pl, result = rest_call('GET', 'processes')
    processes = []
    if result == 200:
        processes = [ p['name'] for p in pl ]
    return processes

@cache.memoize(timeout=86400, make_name=dep_zone)
def get_departments():
    with irods_manager.session(current_user) as session:
        query = session.query(UserMeta.value).filter(
            Criterion('=', UserMeta.name, 'sys::ad::department')).order_by(UserMeta.value).filter(
            Criterion('!=', UserMeta.value, '*'))
        departments = [ u[UserMeta.value] for u in query ]
    return departments


@bp.route('/')
@login_required
def show_projects():
    """
    Return a web page with a list of all projects

    url params:
        project: switch to projects page and show <project>
        process: switch to processes page and show <processid>
    """
    # TODO: refactor passing of arguments
    page = request.args.get('page', 'projects')

    project = request.args.get('project', current_user.settings.get('last_project', ''))
    process = request.args.get('process', current_user.settings.get('last_process', ''))
    activetabname = request.args.get('activetabname', '')
    processgroup = request.args.get('processgroup', '')
    processlist = get_process2list()
    if page == 'processes':
        return render_template('processes.html', processes=processlist, process=process)
    else:
        projectlist = get_projectlist()
        return render_template('projects.html', projects=projectlist, processes=processlist,
            project=project, process=process, activetabname=activetabname, processgroup=processgroup)

@bp.route('/details')
def show_projectdetails():
    """
    Shows page with project settings, metadata and processes belonging to a project
    """
    projectname = request.args.get('project_name', '', type=str)
    processname = request.args.get('process', '', type=str)
    processgroup = request.args.get('processgroup', 'default', type=str)
    projectdetails, result = rest_call('GET', 'projects/{}'.format(projectname))

    # Retrieve groups associated with project
    with irods_manager.session(current_user) as session:
        query = session.query(User.name).filter(
            Criterion('!=', User.type, "rodsuser")).filter(
                Criterion('=', UserMeta.name, "projectID")).filter(
                    Criterion('=', UserMeta.value, projectname)).order_by(User.name)
        groups = [ datafield('group', u[User.name], Datatypes.IRODS_GROUP) for u in query ]
    projectdetails['groups'] = groups
    projectdetails['extra_groups'] = [ d for d in groups if d.value not in (projectdetails['user_group'], projectdetails['manager_group']) ]

    # to prevent break if no projectdetails available yet
    try:
        metadata_collection=projectdetails['default_collection']
    except Exception as e:
        print(e)
        metadata_collection=''

    processing = iso2dt(projectdetails.get('last_updated', EPOCH)) > iso2dt(projectdetails.get('last_verified', EPOCH))
    return render_template('projectdetails.html', projectdetails=projectdetails, processing=processing,
                           processname=processname, processgroup=processgroup, project_permissions=project_permissions(projectname),
                           metadata_collection=metadata_collection,
                           metadata_prefix=ATTR_METADATA_PREFIX, upload_default_prefix=ATTR_UPLOAD_DEFAULT_PREFIX,
                           attribute_type_project=ATTR_SCHEMA_IN_USE + ATTR_PROJECT_SUFFIX,
                           attribute_type_dataset_default=ATTR_SCHEMA_IN_USE + ATTR_DATASET_DEFAULT_SUFFIX,
                           departments=get_departments())

@bp.route('_projectcolls')
def projectcolls():
    """
    """
    projectname = request.args.get('project', '', type=str)
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 999, type=int)
    filterstr = request.args.get('filter', '{}')

    irods_session = current_user.irods_session

    sortkey = request.args.get('sort', 'name')
    sort_order = request.args.get('order', 'asc')

    c_sortkey = COLL_KEY_MAP.get(sortkey, 'coll_name')

    # Create collection and data filters
    filters = json.loads(filterstr)
    qc_filters = [Criterion('=', CollectionMeta.name, 'projectID'), Criterion('=', CollectionMeta.value, projectname)]
    if 'displayname' in filters:
        qc_filters.append(Criterion('like', Collection.name, f'%{filters["displayname"]}%'))

    # Get item counts
    qc_count = irods_session.query(Collection.id)
    for qc_filter in qc_filters:
        qc_count = qc_count.filter(qc_filter)
    coll_count = next(qc_count.count(Collection.id).get_results())[Collection.id]

    results = { 'total': coll_count, 'rows': []}
    # Query for collection subcollections

    q1 = irods_session.query(Collection)
    for qc_filter in qc_filters:
        q1 = q1.filter(qc_filter)
    q1 = q1.order_by(c_sortkey, order=sort_order).offset(offset).limit(limit)
    try:
        colls = q1.execute()
        for coll in colls:
            objdict = {
                'displayname': datafield('irods_collection', coll[Collection.name], Datatypes.IRODS_COLLECTION).collentry,
                'path': coll[Collection.name],
                'object': 'collection',
                'size': 'DIR',
                'create_time': datafield('create_time', coll[Collection.create_time], Datatypes.TIMESTAMP).htmlstring,
                'owner_name': coll[Collection.owner_name]
            }
            objdict['type'] = cached_iqry.qcollmetaval(coll[Collection.name], 'sys::data::type', default='')
            results['rows'].append(objdict)
    except CAT_NO_ROWS_FOUND:
        pass
    return jsonify(results)


@bp.route('_projectcolltable')
def projectcolltable():
    """
    """
    projectname = request.args.get('project', '', type=str)
    options = {
        'download_btn': False,
        'view_btn': False,
        'delete_btn': False
    }
    path=f"/{current_user.irods_zone}/projects/{projectname}"
    return render_template('colltable.html', path=path, display_field=None, options=options)


@bp.route('/processdetails')
def show_processdetails():
    """
    Shows page with process settings
    """
    processname = request.args.get('name', '', type=str)
    pl, result = rest_call('GET', f'processes/{processname}')
    return render_template('processdetails.html', details=pl, sites_and_clusters=current_user.irods_env.get("sites_and_clusters", {}))


@bp.route('/update_project', methods=['GET', 'POST'])
def update_projectsettings():
    """
    Called when changing project settings from the web interface
    The request contains an <action> variable that specifies the kind of update
    that is requested
    """
    requestdata = request.form.to_dict()
    location = ''
    project = requestdata.get('project')
    process = requestdata.get('process')
    action = requestdata.get('action')

    if action == 'add_process2':
        if process:
            data = {'name': process}
            response, result = rest_call('POST', 'processes', data=data)
        location=f'page=processes&process={process}'
    elif action == 'remove_process':
        print(f'Remove process {process}')
        if process:
            response, result = rest_call('DELETE', f'processes/{process}')
            print(response, result)
            if result != 200:
                flash(response.get('message'), 'error')
                location = f'page=processes&process={process}'
            else:
                location = 'page=processes'
    elif action == 'add_processgroup':
        name = requestdata.get('name')
        if project and name:
            data = {'name' : name }
            response, result = rest_call('POST', f'projects/{project}/processgroups', data=data)
        location=f'project={project}&activetabname=processgroups&processgroup={name}'
    elif action == 'rename_processgroup':
        oldname = requestdata.get('oldname')
        newname = requestdata.get('name')
        if project and oldname and newname:
            data = {'name' : newname }
            response, result = rest_call('PUT', f'projects/{project}/processgroups/{oldname}', data=data)
        location=f'project={project}&activetabname=processgroups&processgroup={newname}'
    elif action == 'remove_processgroup':
        name = requestdata.get('name')
        if project and name:
            data = {'name' : name }
            response, result = rest_call('DELETE', f'projects/{project}/processgroups/{name}', data=data)
        location=f'project={project}&activetabname=processgroups'
    elif action == 'update_project':
        data = { 'pipelines': '0', 'public': '0' }
        for attr in ['description', 'default_collection', 'service_account', 'pipelines', 'public', 'department']:
            if attr in requestdata:
                data[attr] = requestdata[attr]
        rest_call('PUT', 'projects/{}'.format(project), data=data)
        location=f'project={project}'
    elif action == 'add_project':
        response, result = rest_call('POST', 'projects'.format(project), data={'name': project})
        if result == 202:
            location=f'project={project}'
        else:
            flash(response.get('message', 'Unknown error'), 'error')
            location='page=projects'
    elif action == 'remove_project':
        response, result = rest_call('DELETE', 'projects/{}'.format(project))
        location='page=projects'

    return redirect(f'{url_for("projects.show_projects")}?{location}')

def is_valid_git_repo(repo_url):
    """Checks if a remote Git repository exists and is accessible via git ls-remote."""
    if not repo_url:
        return False
    
    # Prevent popups and username prompts on the server
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.pop("SSH_ASKPASS", None)
    
    try:
        # Runs 'git ls-remote <url> HEAD' with a 5-second timeout
        subprocess.run(
            ['git', '-c', 'http.sslVerify=false', 'ls-remote', repo_url, 'HEAD'],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            env=env
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False

@bp.route('/_updateproc', methods=['POST'])
def update_process():
    """
    """
    requestdata = request.form.to_dict()
    requestdata["compatible_clusters"] = request.form.getlist("compatible_clusters")
    data = {}
    procid = requestdata.get('procid')
    process = requestdata.get('process')
    
    # Verify git repository
    git_repo = requestdata.get('repo')
    if git_repo and not is_valid_git_repo(git_repo):
        flash(f"Invalid or inaccessible Git repository URL: '{git_repo}'", "error")
        return redirect(url_for("projects.show_projects", page="processes", process=process))

    for attr in ['description', 'repo', 'tag', 'concurrency_limit', 'max_runtime', 'compatible_clusters', 'required_memory']:
        if attr in requestdata:
            data[attr] = requestdata[attr]
    add_checkbox(data, requestdata, 'do_staging', negate=True, key='omit_staging')
    add_checkbox(data, requestdata, 'do_bringonline', negate=True, key='omit_bringonline')
    add_checkbox(data, requestdata, 'modify_in_place')
    add_checkbox(data, requestdata, 'restartable')
    add_checkbox(data, requestdata, 'distribution')
    result = rest_call('PUT', f'processes/{procid}', data=data)
    if result[1] == 401:
        flash(f"Access denied while updating process '{process}'", 'error')
    return redirect(f'{ url_for("projects.show_projects") }?page=processes&process={process}')

@bp.route('/get_process', methods=['GET', 'POST'])
def get_process():
    data = request.form.to_dict()
    if not 'project' in data:
        abort(400)
    processlist = get_processlist(data['project'])
    return jsonify(processlist)

@bp.route('_myprojects', methods=['GET'])
def my_projects():
    projectlist = current_user.projects()
    projectdetails = {}
    pl, result = rest_call('GET', 'projects')
    if result == 200:
        projectdetails = { project['name'] : project['default_collection'] for project in pl if project['name'] in projectlist }
    return projectdetails

@bp.route('_myprojectview', methods=['GET'])
def my_projectview():
    columns = request.args.get('columns')
    projectdetails = my_projects()
    if columns is None:
        columns = min(4, 1 + len(projectdetails) // 20)
    return render_template('_myprojects.html', projectdetails=projectdetails, columns=columns )


@bp.route('_pgaction', methods=['GET', 'POST'])
def pgaction():
    project = request.args.get('project')
    group = request.args.get('group')
    action = request.args.get('action')

    # Set the default results for success and error
    action_result = { 'success': True }
    action_result_ERROR = { 'success': False,
                            'message': "Unknown error",
                            'category': "error" }

    if action == 'add_process':
        process = request.args.get('process')
        name = request.args.get('name')
        # Check if the process exists:
        pr, r2 = rest_call('GET', f'processes/{process}')
        if r2 != 200:
            action_result = action_result_ERROR
            action_result['message'] = "Can't get processes"
            return action_result
        if name == "":
            # Auto-generate a name based on the process name
            all_pgprocs, r3 = rest_call('GET', f'projects/{project}/processgroups/{group}/processes')
            if r3 != 200:
                action_result = action_result_ERROR
                action_result['message'] = "Can't get processes in processgroup"
                return action_result
            names = [ p.get('name') for p in all_pgprocs ]
            index = 1
            while True:
                name = f'{process}-{index}'
                if name not in names:
                    break
                index += 1

        new_process = {
            'name': name,
            'processid': pr.get('id')
        }
        pl, status_code = rest_call('POST', f'projects/{project}/processgroups/{group}/processes', new_process)
    elif action == 'update_process':
        process = request.args.get('process')
        data = {}
        for attr in ['lsf_queue', 'tag']:
            value = request.args.get(attr)
            if value:
                data[attr] = value
        pl, status_code = rest_call('PUT', f'projects/{project}/processgroups/{group}/processes/{process}', data = data)
    elif action == 'update_processes':
        lsf_queue = request.args.get('lsf_queue')
        pl, status_code = rest_call('GET', f'projects/{project}/processgroups/{group}/processes')
        if status_code == 200:
            for procref in pl:
                _, status_code = rest_call('PUT', f'projects/{project}/processgroups/{group}/processes/{procref.get("id")}',
                    data = { 'lsf_queue': lsf_queue })
    elif action == 'delete_process':
        process = request.args.get('process')
        pl, status_code = rest_call('DELETE', f'projects/{project}/processgroups/{group}/processes/{process}')
    elif action == 'set_input':
        process = request.args.get('process')
        input = request.args.get('input')
        pl, status_code = rest_call('PUT',
            f'projects/{project}/processgroups/{group}/processes/{process}',
            { 'input': input})
    elif action == 'add_dependency':
        process = request.args.get('process')
        depend = request.args.get('depend')
        pl, status_code = rest_call('POST',
            f'projects/{project}/processgroups/{group}/processes/{process}/dependencies',
            { 'depends_on': depend })
    elif action == 'delete_dependency':
        process = request.args.get('process')
        depend = request.args.get('depend')
        pl, status_code = rest_call('DELETE',
            f'projects/{project}/processgroups/{group}/processes/{process}/dependencies/{depend}')

    #return the success/error state
    if status_code not in [200, 201]:
        action_result = action_result_ERROR
        if pl and 'message' in pl:
            action_result["message"] = pl['message']
    return action_result


@bp.route('_process_list_refdata', methods=['GET'])
def process_list_refdata():
    processid = request.args.get('process')
    refdatasForProcess, result = rest_call('GET', f'processes/{processid}/referencedataversion')
    refdatasets, result = rest_call('GET', f'reference')
    ref_versions = {}
    for refdataFP in refdatasForProcess:
        refdataid = refdataFP['referencedataid']
        versions, result = rest_call('GET', f'reference/{refdataid}/versions')
        ref_versions[refdataid] = versions
    return render_template('process_reference_data.html', processid=processid, reference_data_sets=refdatasets, reference_data_for_process=refdatasForProcess, ref_versions=ref_versions)


@bp.route('_process_add_referencedataversion', methods=['GET'])
def process_add_referencedataversion():
    referencedataid = request.args.get('referencedataid')
    referencedataversionid = request.args.get('referencedataversionid')
    processid = request.args.get('processid')
    label = request.args.get('label')
    result, r = rest_call('POST', f'/processes/{processid}/referencedataversion',
                                { "referencedataid": referencedataid ,
                                  "referencedataversionid": referencedataversionid,
                                  "label": label } )
    return result

@bp.route('_process_del_referencedataversion', methods=['GET'])
def process_del_referencedataversion():
    processid = request.args.get('processid')
    referencedataid = request.args.get('referencedataid')
    result, r = rest_call('DELETE', f'/processes/{processid}/referencedataversion/{referencedataid}' )
    return result


@bp.route('_process_set_referencedataversion', methods=['GET'])
def process_set_referencedataversion():
    referencedataid = request.args.get('referencedataid')
    referencedataversionid = request.args.get('referencedataversionid')
    processid = request.args.get('processid')
    result, r = rest_call('PUT', f'/processes/{processid}/referencedataversion/{referencedataid}',
                                { "referencedataversionid": referencedataversionid } )
    return result

@bp.route('_referencedataversions', methods=['GET'])
def referencedataversions():
    referencedataid = request.args.get('referencedataid')
    all_versions, r = rest_call('GET', f'reference/{referencedataid}/versions')
    return all_versions


#Awful lot of RESTCalls happening here...
@bp.route('pg_list_processref_refdata', methods=['GET'])
def pg_list_processref_refdata():
    project = request.args.get('project')
    group = request.args.get('group')
    process = request.args.get('process')
    process_ref = request.args.get('process_ref')
    refdatasForProcess, code = rest_call('GET', f'processes/{process}/referencedataversion')
    if code != 200:
        return []

    for refdataFP in refdatasForProcess:
        id = refdataFP["id"]
        refdataid = refdataFP["referencedataid"]
        versions, code = rest_call('GET', f'reference/{refdataid}/versions')
        if code != 200:
            return[]
        else:
            refdataFP["versions"] = versions

    refdatasForProcessRef, code = rest_call('GET', f'/projects/{project}/processgroups/{group}/processes/{process_ref}/referencedataversion')
    refdatasForProcessRefByRDFBID = {}
    if code != 200:
        return []
    for refdataFPR in refdatasForProcessRef:
        refdataFP_id = refdataFPR["processdefault"]["id"]
        refdatasForProcessRefByRDFBID[refdataFP_id] = refdataFPR
    result = { "refdatasForProcess": refdatasForProcess , "refdatasForProcessRef": refdatasForProcessRefByRDFBID}
    return result


@bp.route('_pg_set_referencedataversion', methods=['GET'])
def pg_set_referencedataversion():
    #None or Id of the entry in table refdataversion2processref, that contains the superseding versionid
    refdataversion2processrefid = request.args.get('refdataversion2processrefid')
    #either -2 (remove superseding entry), -1 (convert to null) or the id of a version that will superseed the process-default
    supersedingversionid = int(request.args.get('supersedingversionid'))
    #the entry-id in refdataversion2processref that defines the default version to use, which will be superseded by a pg-specific entry
    processdefaultid = request.args.get('processdefaultid')
    project = request.args.get('project')
    group = request.args.get('group')
    process_ref = request.args.get('process_ref_id')

    result = {}
    #depending on supersedingversionid either delete existing entries (-2), put null in (-1) or set on the given value.
    if supersedingversionid == -2:
        result, code = rest_call('DELETE', f'/projects/{project}/processgroups/{group}/processes/{process_ref}/referencedataversion/{refdataversion2processrefid}' )
    else:
        if supersedingversionid == -1:
            supersedingversionid = None
        if refdataversion2processrefid:
            refdataversion2processrefid = int(refdataversion2processrefid)
            #existing entry should be changed, via PUT
            result, code = rest_call('PUT', f'/projects/{project}/processgroups/{group}/processes/{process_ref}/referencedataversion/{refdataversion2processrefid}',
                                    { "supersedingversionid": supersedingversionid} )
        else:
            #a new entry needs to be created via POST
            result, code = rest_call('POST', f'/projects/{project}/processgroups/{group}/processes/{process_ref}/referencedataversion',
                                    {
                                        "supersedingversionid": supersedingversionid,
                                        "processdefaultid": processdefaultid
                                    } )
    return result


@bp.route('_pg_add_referencedataversions', methods=['GET'])
def pg_add_referencedataversions():
    referencedataid = request.args.get('referencedataid')
    project = request.args.get('project')
    group = request.args.get('group')
    process = request.args.get('process')
    result, r = rest_call('POST', f'/projects/{project}/processgroups/{group}/processes/{process}/referencedataversion',
                                {"referencedata_versionid": referencedataid } )
    return result


@bp.route('_pg_list_referencedataversions',  methods=['GET'])
def pg_list_referencedataversions():
    project = request.args.get('project')
    group = request.args.get('group')
    process = request.args.get('process')
    result, r = rest_call('GET', f'/projects/{project}/processgroups/{group}/processes/{process}/referencedataversion')
    return result


@bp.route('_pggraph', methods=['GET'])
def pg_graph():
    """
    Generate a graph of process flow

        Node names:
            name: 'out,<id>', with id being the id from pgprocess
            label: 'out,name', with name being the name from pgprocess
                if id==0, label='DATA'
            id: 'out, id, name'

        Process names:
            name: 'proc,<id>', with id being the id from pgprocess
            label: '<name>', with name being the name from pgprocess
            id: 'proc, id, name'
    """
    def add_process(name, tag, procid, selected):
        extra_settings = {}
        if selected:
            extra_settings = {
                'style': 'filled',
                'fillcolor': 'lightblue'
            }
        nodename = f'n,{procid}'
        nodeid = f'n,{procid},{name}'
        graph.node(nodename, label=name, shape='cds', id=nodeid, tooltip=tag, **extra_settings)

    project = request.args.get('project')
    group = request.args.get('group', 'default')
    selected_processref = request.args.get('selected_processref')
    pl, result = rest_call('GET', f'projects/{project}/processgroups/{group}/processes')
    if result != 200:
        return ""
    # Create the process group graph
    graph = Digraph('processgroup_graph')
    graph.graph_attr['rankdir'] = 'LR'
    # There is always a node for NEW_DATA
    graph.node('d,0', label="   NEW DATA   ", shape='box', id='d,0', tooltip='NEW DATA')
    for process in pl:
        pname = process.get('name')
        ptag = process.get('tag', '')
        add_process(pname, ptag, process.get('id'), pname==selected_processref)
    # get the dependencies
    pd, r2 = rest_call('GET', f'projects/{project}/processgroups/{group}/dependencies')
    for process in pl:
        processname = f'n,{process.get("id")}'
        input = process.get("input")
        if input:
            precessor = f'n,{input}'
        else:
            precessor = f'd,0'
        graph.edge(precessor, processname, style='bold')
        for dep in [ p for p in pd if p.get('processrefid') == process.get('id') ]:
            depend_id = dep.get('depends_on')
            if depend_id is not None:
                depnode = f'n,{depend_id}'
                graph.edge(depnode, processname, style='dashed')

    graph_output = graph.pipe(format='svg').decode('utf-8')
    return graph_output


@bp.route('_pgdetails')
def pg_details():
    project = request.args.get('project')
    group = request.args.get('group', 'default')
    selected_processref = request.args.get('selected_processref')
    mode = request.args.get('mode')
    pl, result = rest_call('GET', f'projects/{project}/processgroups/{group}/processes')
    all_processes, result = rest_call('GET', f'processes')
    all_processes = sorted(all_processes, key=lambda x: x['name'].lower())
    dependency_names = []
    selected_details = None
    selected_tags = []
    all_reference_datasets = []
    connected_reference_datasets = []
    selected_process = datafield('process', 'NOT FOUND', Datatypes.TEXT)
    list_of_lsf_queue_options = current_app.config.get('IRODS_ENVS', {}).get(current_user.env_tag, {}).get('lsf_queues', [])
    if selected_processref:
        sel_list = search(pl, lambda x: x.get('name'), selected_processref)
        selected_details  = sel_list[0] if sel_list else None
        dependencies, r2 = rest_call('GET', f'projects/{project}/processgroups/{group}/processes/{selected_processref}/dependencies')
        dependency_names = [ p['name'] for p in pl if p['id'] in [ d['depends_on'] for d in dependencies ]]
        selected_processlist = search(all_processes, lambda x: x.get('id'), selected_details.get('processid'))
        #additional rest calls to get all reference data
        all_reference_datasets, r3 = rest_call('GET', f'reference' )
        connected_reference_datasets, r4 = rest_call('GET', f'projects/{project}/processgroups/{group}/processes/{selected_processref}/referencedataversion')
        if selected_processlist:
            selected_process = datafield('process', selected_processlist[0].get('name'), Datatypes.PROCESS)
        selected_tags, r5 = rest_call('GET', f'processes/{selected_details.get("processid")}/tags')
    message = ''
    if mode == 'select_input':
        message = f'Please select input for process {selected_processref}'
    elif mode == 'add_dependency':
        message =f'Please select a required process for {selected_processref}'
    return render_template('pg_details.html', project=project, group=group,
        all_processes=all_processes, pg_processes=pl, selected_details=selected_details,
        selected_tags=selected_tags,
        list_of_lsf_queue_options=list_of_lsf_queue_options,
        selected_process=selected_process,
        dependencies=dependency_names,
        all_reference_datasets=all_reference_datasets, connected_reference_datasets=connected_reference_datasets ,
        message=message, project_permissions=project_permissions(project))

@bp.route('processgroups', methods=['GET'])
def processgroups():
    # Retrieve the list of processes in a group
    project = request.args.get('project')
    processgroup = request.args.get('group', 'default')
    # find all groups
    pl, result = rest_call('GET', f'projects/{project}/processgroups')
    groups = [ g.get('name') for g in pl ]
    return render_template('processgroups.html', project=project, processgroup=processgroup, processgroups=groups, project_permissions=project_permissions(project))


@bp.route('usermanager', methods=['GET'])
def usermanager():
    objectname = request.args.get('object')
    objecttype = request.args.get('objecttype')
    usertype = request.args.get('usertype')
    # can_modify will be used to hide/show the add/delete buttons
    # if we are not sure, set it to true
    # the rest service will enforce permissions anyway
    can_modify = True
    if objecttype == 'projects':
        pl, result = rest_call('GET', f'projects/{objectname}/external/{usertype}/groups')
        external_groups = pl if result == 200 else []
        can_modify = project_permissions(objectname).get('managers', True) and not external_groups
    elif objecttype == 'processes':
        can_modify = process_permissions(objectname).get('managers', True)
        external_groups = []
    return render_template('usermanager.html', object=objectname, objecttype=objecttype, usertype=usertype, can_modify=can_modify, external_groups=external_groups)


@bp.route('processusage', methods=['GET'])
def processusage():
    process = request.args.get('process')
    return render_template('processusage.html', process=process)

@bp.route('_processusage_table', methods=['GET'])
def process_usage_table():
    process = request.args.get('process')
    if process is None:
        return {}
    output = []
    data, result = rest_call('GET', f'processes/{process}/references')
    for record in data:
        project = record.get('project')
        processgroup = record.get('processgroup')
        output.append({
            'project': datafield('project', project, Datatypes.PROJECTID).htmlstring,
            'processgroup': f'<a href={ url_for('projects.show_projects', project=project, processgroup=processgroup, activetabname="processgroups") }>{processgroup}</a>',
            'name': record.get('name'),
            'tag': record.get('tag'),
            'url': record.get('url')
        })
    return output

@bp.route('_process_stats', methods=['GET'])
def process_stats():
    process_id = request.args.get('process')
    return render_template('process_stats_tabs.html', process_id=process_id)

@bp.route('_process_stats_page', methods=['GET'])
def process_stats_page():
    data_url=url_for('projects.process_stats_data', **request.args)
    return render_template('bargraph.html', data_url=data_url)

@bp.route('_process_stats_data', methods=['GET'])
def process_stats_data():
    args = request.args
    statname = args.get('statname')
    process_id = args.get('process')
    if statname == 'proc-stats-history':
        stats = dict(sorted(runspermonth(process_id).items()))
        name = 'Runs'
        title = 'Runs per month'
    if statname == 'proc-stats-projects':
        stats = dict(sorted(runspermetaattr(process_id, ATTR_PROJECTID).items()))
        name = 'Runs'
        title = 'Runs per project'
    if statname == 'proc-stats-runtime-dist':
        stats = dict(sorted(runtimedist(process_id).items()))
        name = 'Runs'
        title = 'Runtime distribution'
    if statname == 'proc-stats-runtime-hist':
        stats = dict(sorted(runtimehist(process_id).items()))
        name = 'Seconds (avg)'
        title = 'Runtime history'
    if statname == 'proc-stats-versions':
        stats = dict(sorted(runspermetaattr(process_id, ATTR_RUNSHEET_TAG).items()))
        name = 'Runs'
        title = 'Runs per version'
    if statname == 'proc-stats-users':
        stats = dict(sorted(runspermetaattr(process_id, ATTR_RUN_REQUESTINGUSER).items()))
        name = 'Runs'
        title = 'Requesting users'        

    data = {
        'labels': list(stats.keys()),
        'values': list(stats.values()),
        'name': name,
        'title': title
    }
    return data