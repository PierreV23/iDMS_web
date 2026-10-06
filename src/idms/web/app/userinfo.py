#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov 19 15:23:56 2019

@author: wierinve
"""

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from idms.common.irods.irods_sessions import irods_manager
from idms.common.filesys import fs_irods
from idms.web.app.collbrowser import contents_changed
from .utils import cached_iqry as iqry

bp = Blueprint('userinfo', __name__, url_prefix='/userinfo')

ATTR_CLUSTER_USERNAME_TEMPLATE = "cluster::{}::username"
ATTR_CLUSTER_SSHKEY_TEMPLATE = "cluster::{}::sshkey_path"
ATTR_CLUSTER_CONFIG_REQUEST_TEMPLATE = "cluster::{}::autoconfig"


@bp.route('/api/setting', methods=['GET', 'POST', 'DELETE'])
def usersetting():
    if request.method == 'POST':
        if request.is_json:
            attr = request.json.get('attr')
            value = request.json.get('value')
        else:
            formdata = request.form.to_dict()
            attr = formdata.get('attr')
            value = formdata.get('value')
        current_user.settings[attr] = value
        return { 'result': 'OK'}, 200
    elif request.method == 'GET':
        attr = request.args.get('attr')
        value = current_user.settings.get(attr)
        if value is None:
            return { 'result': 'NOT FOUND' }, 404
        else:
            return { 'value': current_user.settings.get(attr, '') }, 200
    elif request.method == 'DELETE':
        if request.is_json:
            attr = request.json.get('attr')
            current_user.settings.delete(attr)
            return {'result': 'OK'}, 200

def userinfo(user):
    with irods_manager.session(current_user) as session:
        userinfo = session.users.get(user)
        input_meta = { x.name: x.value for x in userinfo.metadata.items()}
    return(input_meta)


def groupinfo(group):
    ginfo={}
    try:
        with irods_manager.session(current_user) as session:
            gobj = session.user_groups.get(group)
    except:
        ginfo["None"] = {'sys::ad::mail': None, 'sys::ad::department': None}
        return(ginfo)
    for n in gobj.members:
        x = n.name.split("_")
        if x[0] == "svc-irods" or x[0] == "svc-sscc-irods":
            ginfo[n.name] = userinfo(n.name)
            ginfo[n.name].update({"serviceaccount": True})
        else:
            ginfo[n.name] = userinfo(n.name)
            ginfo[n.name].update({"serviceaccount": False})
    return(ginfo)

@bp.route('/groupdetails')
@login_required
def groupdetails():
    group = request.args.get('group','', type=str)
    ginfo = groupinfo(group)
    return render_template('groupdetails.html', group=group, ginfo=ginfo)

def cluster_config():
    clusters = {}
    for cluster, cluster_data in current_user.irods_env.get("sites_and_clusters", {}).get("clusters", {}).items():
        homeColl = f"/{ current_user.irods_zone }/home/{current_user.username}"
        cluster_username_attr = ATTR_CLUSTER_USERNAME_TEMPLATE.format(cluster)
        cluster_sshkey_attr = ATTR_CLUSTER_SSHKEY_TEMPLATE.format(cluster)
        cluster_autoconf_attr = ATTR_CLUSTER_CONFIG_REQUEST_TEMPLATE.format(cluster)
        clusters[cluster] = {
            "username": iqry.qcollmetaval(homeColl, cluster_username_attr),
            "sshkey_path": iqry.qcollmetaval(homeColl, cluster_sshkey_attr),
            "autoconfig_request":iqry.qcollmetaval(homeColl, cluster_autoconf_attr, default='false')
        }
    return clusters

@bp.route('/api/requestclusterconfig', methods=['GET'])
def request_cluster_config():
    cluster = request.args.get('cluster')
    cluster_autoconf_attr = ATTR_CLUSTER_CONFIG_REQUEST_TEMPLATE.format(cluster)
    homeColl = f"/{ current_user.irods_zone }/home/{current_user.username}"
    iqry.scollmetaval(homeColl, cluster_autoconf_attr, 'true')
    return { 'result': 'OK' }, 200
        

@bp.route('/api/userclusterconfig', methods=['POST'])
def save_cluster_config():
    formdata = request.form.to_dict()
    cluster = formdata["cluster"]
    username = formdata["username"]
    sshkey = formdata["sshkey"]

    homeColl = f"/{ current_user.irods_zone }/home/{current_user.username}/"
    secretiObjFolder = f"/{ current_user.irods_zone }/home/{current_user.username}/.secret/"
    secretiObjName = f"/{ current_user.irods_zone }/home/{current_user.username}/.secret/{ cluster }_sshkey"

    with irods_manager.session() as session:
        try:
            fs_irods(session=session).mkdir(secretiObjFolder)
        except Exception as e:
            pass
        with fs_irods(session=session).open(secretiObjName, 'w') as iObj:
            iObj.write(sshkey.encode('utf-8'))
            contents_changed()

    cluster_username_attr = ATTR_CLUSTER_USERNAME_TEMPLATE.format(cluster)
    cluster_sshkey_attr = ATTR_CLUSTER_SSHKEY_TEMPLATE.format(cluster)

    iqry.rmallcollmetaattr(homeColl, cluster_username_attr)
    iqry.scollmetaval(homeColl, cluster_username_attr, username)
    iqry.rmallcollmetaattr(homeColl, cluster_sshkey_attr)
    iqry.scollmetaval(homeColl, cluster_sshkey_attr, secretiObjName)

    return { 'result': 'OK' }, 200