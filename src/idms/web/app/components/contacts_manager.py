#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov 19 09:05:26 2019

@author: wierinve
"""

import json
from flask import abort, flash, Blueprint, render_template, redirect, request, url_for
from flask_login import current_user, login_required
from flask import jsonify
from idms.web.app.utils.flaskcache import cache, key_zone, key_userzone, dep_zone, dep_userzone
from irods.models import Collection, CollectionMeta, User, UserMeta
from irods.column import Criterion
from idms.web.app.utils.datafield import datafield
from idms.web.app.utils.cached_iqry import *
from idms.common.irods.irods_sessions import irods_manager
from idms.web.app.utils.projectdb_api import EPOCH, iso2dt, search, rest_call, add_checkbox

bp = Blueprint('contacts', __name__, url_prefix='/contacts')


@cache.memoize(timeout=600, make_name=dep_userzone)
def refdata_permissions(refdata):
    """Return True if current_user is manager of reference dataset, for now return True until apropriate endpoint is available
    """
    return { 'managers': True, 
             'users': True }

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




@bp.route('/projects/delete_contact', methods=['POST'])
def delete_contact():
    json = request.get_json(force=True)
    objecttype = json['objecttype']
    entity_id = json['entity_id']
    contact_id = json['contact_id']

    result, status = None, 500
    if objecttype in ['projects', 'processes']:   
        result, status = rest_call('DELETE', f"projects/{entity_id}/contacts/{contact_id}")
    elif objecttype in ['reference_data']:   
        result, status = rest_call('DELETE', f"reference/{entity_id}/contacts/{contact_id}")

    ret = {}
    if status == 200:
        ret = { "success": True }
    else:
        ret = { "msg": f"Error: {result['message']}"}
    return ret


@bp.route('/projects/update_contact', methods=['POST'])
def update_contact():
    json = request.get_json(force=True)
    objecttype = json['objecttype']
    entity_id = json['entity_id']
    contact_id = json['contact_id']
    contact = json['contact']

    result, status = None, 500
    if objecttype in ['projects', 'processes']:   
        result, status = rest_call('PUT', f"projects/{entity_id}/contacts/{contact_id}", contact)
    elif objecttype in ['reference_data']:   
        result, status = rest_call('PUT', f"reference/{entity_id}/contacts/{contact_id}", contact)

    ret = {}
    if status == 200:
        ret = { "success": True }
    else:
        ret = { "msg": f"Error: {result['message']}", "contact": result['contact'] }
    return ret


@bp.route('/projects/create_contact', methods=['POST'])
def create_contact():
    json = request.get_json(force=True)
    objecttype = json['objecttype']
    entity_id = json['entity_id']
    contact = json['contact']
    
    result, status = None, 500
    if objecttype in ['projects', 'processes']:   
        result, status = rest_call('POST', f"projects/{entity_id}/contacts", contact)
    elif objecttype in ['reference_data']:   
        result, status = rest_call('POST', f"reference/{entity_id}/contacts", contact)

    ret = {}
    if status == 201:
        ret = { "success": True , "contact": result }
    else:
        ret = { "msg": f"Error: {result['message']}"}
    return ret



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
        can_modify = project_permissions(objectname).get('managers', True)
    elif objecttype == 'processes':
        can_modify = process_permissions(objectname).get('managers', True)
    return render_template('usermanager.html', object=objectname, objecttype=objecttype, usertype=usertype, can_modify=can_modify)


@bp.route('/contactmanager', methods=['GET'])
def contactmanager():
    objectname = request.args.get('object')
    objecttype = request.args.get('objecttype')
    # can_modify will be used to hide/show the add/delete buttons
    # if we are not sure, set it to true
    # the rest service will enforce permissions anyway
    can_modify = True
    permissions = None 
    options = {
            "pipeline_errors": True,
            "pipeline_results": True,
            "config_changes": True,
            "new_data": True
    }
    contacts, result = ([],{})
    if objecttype == 'projects':
        permissions = project_permissions(objectname)
        can_modify = permissions.get('managers', True)
        contacts, result = rest_call('GET', '{}/{}/contacts'.format('projects', objectname))
    elif objecttype == 'processes': 
        permissions = process_permissions(objectname)
        can_modify = permissions.get('managers', True)
        contacts, result = rest_call('GET', '{}/{}/contacts'.format('projects', objectname))
    elif objecttype == 'reference_data':
        permissions = refdata_permissions(objectname)
        can_modify = permissions.get('managers', True)
        contacts, result = rest_call('GET', '{}/{}/contacts'.format('reference', objectname))

    
    return render_template('contactmanager.html', 
                           object=objectname, 
                           objecttype=objecttype, 
                           options=options,
                           contacts=contacts, 
                           can_modify=can_modify, 
                           permissions=permissions)


