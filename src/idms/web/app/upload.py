#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Data upload interface voor iDMS
"""

import os
import shutil
import logging
import time
import jsonavu
from flask import Blueprint, render_template, redirect, request, url_for, flash
from flask_login import current_user, login_required
from idms.web.app.utils.datafield import datafield, Datatypes
from idms.web.app.utils.projectdb_api import rest_call
from idms.common.irods.irods_helper import get_or_set_uid
import randomname
import json
import re
from irods.models import Collection, CollectionMeta
from irods.column import Criterion


from idms.common.irods.irods_sessions import irods_manager
from idms.common.filesys.fs_irods import fs_irods

from idms.common.constants.attribute_names import ( 
        ATTR_PROJECTID,
        ATTR_UPLOAD,
        ATTR_UPLOADNAME,
        ATTR_UPLOADPARENT,
        ATTR_UPLOADSETTINGS ,
        ATTR_UPLOADMETA, 
        ATTR_SCHEMA_IN_USE,
        ATTR_DATASET_DEFAULT_SUFFIX,
        ATTR_DATASET_UPLOAD_SUFFIX,
        META_SUFFIXLENGTH,
        AVU2JSON_PREFIX
        )

from idms.web.app.utils import cached_iqry


# remove spacial characters, but there is no need to only allow [a-zA-Z_], quotes, paranthesis, "@" are all valid characters
# for AVU keys a stronger sanitazition might be desired, allowing only [0-9a-Z_:-]
def sanitize(s, strong=False):
    s = s.replace("\t", "    ")
    if strong:
        s = re.sub(r"[^0-9a-zA-Z_: -]", "", s).strip()
        s = s.strip().replace(" ", "_")
    else:
        s = re.sub(r"[^ -ÿ]", "", s)
    return s.strip()

def validate_collection_name(s):
    allowed_set = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")

    # True if text contains characters outside the allowed set
    invalid_chars = set(s) - allowed_set
    is_valid = not bool(invalid_chars)

    return is_valid, invalid_chars

def format_invalid_characters(cl):
    """Show invalid characters in readable format

    Args:
        cl (iterable): list of invalid characters

    Returns:
        str: description string
    """
    REPLACEMENTS = {
        ' ': '<SPACE>',
        '\t': '<TAB>'
    }
    return ' '.join([REPLACEMENTS.get(s, s) for s in cl])

class UploadType:
    Pending = 'pending'
    Ready = 'ready'
    Done = 'done'

bp = Blueprint('upload', __name__, url_prefix='/upload')

def collection_basename(coll):
    """Return the basename of a collection without the path, and without the numeric suffix

    So /rivmZone_acc_01/projects/ngslab/output/230911_NB502001_0032_AHTFHKAFX3_0000
    returns 230911_NB502001_0032_AHTFHKAFX3
    assuming sys::suffixlength == 4
    """

    name = os.path.basename(coll)
    sl = cached_iqry.qcollmetaval(coll, META_SUFFIXLENGTH)
    if sl:
        name = name[:-int(sl)-1]
    return name


#there is a generate_unique_dataset_from in irods_helper
def unique_coll(base_coll, prefix=None, use_date=False):
    """Create a collection with a unique collection name

    The unique name will consist of an optional prefix, an optional date and a number.

    Args:
        base_coll (string): Parent collection of collection name to create
        prefix (string): Prefix for the collection name. If the prefix name alone is unique, it
                        will become the new collection name. If none is supplied, a prefix will be generated
        use_date (boolean): Will append the current date to the suffix

    Returns:
        string: Full irods path to unique collection
    """
    if prefix is None:
        fullprefix = 'dataset' # TODO : generate name (randomname)
    elif prefix == '':
        fullprefix = ''
    else:
        fullprefix = f'{prefix}'

    if use_date:
        datestr = time.strftime('%Y%m%d_%H%M%S')
        if fullprefix:
            fullprefix = f'{fullprefix}_{datestr}'
        else:
            fullprefix = f'{datestr}'

    if not fullprefix:
        collname = os.path.join(base_coll,'0000')
    else:
        collname = os.path.join(base_coll, f'{fullprefix}')
        fullprefix = f'{fullprefix}_'
    i = 1
    with irods_manager.session(current_user) as session:
        while session.collections.exists(collname):
            collname = os.path.join(base_coll, f'{fullprefix}{i:04}')
            i += 1
        logging.debug('upload/unique_coll(): mkdir "{}"'.format(collname))
        fs_irods(session=session).mkdir(collname)
    # TODO : add some metadata?
    return collname


@bp.errorhandler(413)
def too_large(e):
    return "File is too large", 413


@bp.route('show_uploads')
@login_required
def show_uploads():
    return render_template('uploads.html')



@bp.route('_pendinguploads')
def pending_uploads():
    state = request.args.get('state', UploadType.Pending)
    pending = []
    with irods_manager.session(current_user) as session:
        query = session.query(Collection).filter( \
            Criterion('=', Collection.owner_name, current_user.username)).filter( \
            Criterion('=', CollectionMeta.name, ATTR_UPLOAD)).filter( \
            Criterion('=', CollectionMeta.value, state))
        for c in query:
            coll = c[Collection.name]
            projectID = cached_iqry.qcollmetaval(coll, f'{ATTR_UPLOADSETTINGS}projectID', default='')
            name = cached_iqry.qcollmetaval(coll, ATTR_UPLOADNAME, default=coll)
            name_url = url_for('upload.upload_settings', coll=coll)
            if state == UploadType.Pending:
                namestr = f'<a href="{ name_url }">{name}</a>'
            else:
                namestr = name

            pending.append(
                { 'name': namestr,
                'collection':  datafield('collection', coll, Datatypes.IRODS_COLLECTION).htmlstring,
                'projectID': datafield('project', projectID, Datatypes.PROJECTID).htmlstring
                }
            )
    response = {
        'rows': pending
    }
    return json.dumps(response)

@bp.route('_uploadsettings', methods=['GET', 'POST'])
def upload_settings():
    FIELDS = {
        'projectID':   'Project',
        'collection':  'Collection name',
        'description': 'Description'
    }
    if request.method == 'GET':
        coll = request.args.get('coll')
        if coll is None:
            return redirect(url_for('upload.show_uploads'))
        name = os.path.basename(coll)
        my_projects = current_user.projects()
        meta = cached_iqry.qcollmetadict(coll)
        data = { k: meta.get(f'{ATTR_UPLOADSETTINGS}{k}', '') for k in FIELDS }
        return render_template('upload_settings.html', name=name, coll=coll, projects=my_projects, fields=FIELDS, data=data)
    if request.method == 'POST':
        data = request.form.to_dict()
        coll = data.get('coll')
        projectID = data.get('projectID')
        projectID_meta_current = cached_iqry.qcollmetadict(coll).get(f'{ATTR_UPLOADSETTINGS}projectID', None)
        if projectID_meta_current is not None and projectID != projectID_meta_current:
            unset_upload_meta(coll)
        collection_name = data.get('collection')
        valid, invalid_chars = validate_collection_name(collection_name)
        if not valid:
            invalid_character_string = format_invalid_characters(invalid_chars)
            flash(f'Please use alphanumeric characters only in collection name. Found invalid characters: {invalid_character_string}', 'error')
            return redirect(url_for('upload.upload_settings', coll=coll))        
        for k, v in data.items():
            if k in FIELDS and v:
                cached_iqry.scollmetaval(coll, f'{ATTR_UPLOADSETTINGS}{k}', str(v).strip())
        if data.get('submitbutton', 'save') == 'next':
            return redirect(url_for('upload.upload_meta', coll=coll))
        else:
            return redirect(url_for('upload.upload_settings', coll=coll))


@bp.route('_uploadmeta', methods=['GET', 'POST'])
def upload_meta():
    if request.method == 'GET':
        collection = request.args.get('coll')
        name = os.path.basename(collection)
        if collection is None:
            return redirect(url_for('upload.show_uploads'))
        project_name = cached_iqry.qcollmetaval(collection, f'{ATTR_UPLOADSETTINGS}projectID')
        
        meta_default_values_collection = None
        # schemata for datasets in this project are here:
        if project_name:
            project_details, _ = rest_call('GET', 'projects/{}'.format(project_name))
            meta_default_values_collection = project_details.get('default_collection', '')
        
        metadata = cached_iqry.qcollmeta(collection) #the typed version tries reading the unit field as a python type
        metadict = cached_iqry.qcollmetadict(collection)
        avudata = [ { 'a': avu[CollectionMeta.name][len(ATTR_UPLOADMETA):], 'v': avu[CollectionMeta.value], 'u': avu[CollectionMeta.units] } for avu in metadata if avu[CollectionMeta.name].startswith(ATTR_UPLOADMETA) ]
        data = jsonavu.avu2json(avudata, AVU2JSON_PREFIX)
        metadict = cached_iqry.qcollmetadict(collection) # no unit here, not needed
        selectedSchema = metadict.get(ATTR_SCHEMA_IN_USE + ATTR_DATASET_UPLOAD_SUFFIX, None)     
        prefix=ATTR_UPLOADMETA   
        return render_template('upload_meta.html',
                                coll=collection,   #This is for the menu! Just so we don't lose which collection we are working on when we switch inside the menu between upload_settings, upload_meta and upload_data
                                collection=collection, #Same collection, but the meta-edit-component expects the collection to be called 'collection'
                                meta_default_values_collection = meta_default_values_collection, 
                                project_name=project_name, 
                                name=name, #basename of the collection, usually the autogenerated 'cold-fractal' temporary collection
                                selectedSchema=selectedSchema, 
                                prefix=prefix,
                                data=data, 
                                attribute_type=ATTR_SCHEMA_IN_USE + ATTR_DATASET_UPLOAD_SUFFIX
                                )


def unset_upload_meta(collection):
    metadata = cached_iqry.qcollmeta(collection) 
    avudata = [ { 'a': avu[CollectionMeta.name], 'v': avu[CollectionMeta.value], 'u': avu[CollectionMeta.units] } for avu in metadata ]
    for avu in avudata:
        if avu['a'].startswith(ATTR_UPLOADMETA):
            cached_iqry.delcollmeta(collection, avu['a'], avu['v'], avu['u'] )
        if avu['a'] == [ATTR_SCHEMA_IN_USE + ATTR_DATASET_UPLOAD_SUFFIX]:
            cached_iqry.delcollmeta(collection, avu['a'], avu['v'], avu['u'] )


@bp.route('_uploaddata', methods=['GET', 'POST'])
def upload_data():
    if request.method == 'GET':
        coll = request.args.get('coll')
        name = os.path.basename(coll)
        return render_template('upload_data.html', name=name, coll=coll)
    if request.method == 'POST':
        f = request.files['file']
        data = request.form.to_dict()
        coll = data.get('coll', '/')
        fullPath = data.get('fullPath', f.filename)
        if fullPath == 'undefined':
            fullPath = f.filename
        filename = os.path.join(coll, fullPath)
        filepath = os.path.dirname(filename)
        with irods_manager.session(current_user) as session:
            if not fs_irods(session=session).folderexists(filepath):
                fs_irods(session=session).mkdir(filepath)
            with fs_irods(session=session).open(filename, 'w') as d:
                shutil.copyfileobj(f, d)
        cached_iqry.invalidate(coll)
        return 'OK'

@bp.route('_actions', methods=['GET'])
def upload_actions():
    action = request.args.get('action')
    coll = request.args.get('coll')
    if action == 'finalize':
        # show error message when metadata schema is not selected
        list_of_used_schemata = [key for key in cached_iqry.qcollmetadict(coll).keys() if key.startswith(ATTR_UPLOADMETA)]
        if len(list_of_used_schemata) == 0:
            flash('No metadata schema was selected.', 'error')
            return redirect(url_for('upload.upload_meta', coll=coll))
        cached_iqry.scollmetaval(coll, ATTR_UPLOAD, UploadType.Ready)
        return redirect(url_for('upload.show_uploads'))
    elif action == 'cancel':
        if not coll.startswith( os.path.join( '/', current_user.irods_zone, 'home', current_user.username ) ):
            flash('Unauthorized action!', 'error')
            return redirect(url_for('upload.show_uploads'))
        with irods_manager.session(current_user) as session:
            fs_irods(session=session).rmdir(coll, recurse=True, force=True)
        return redirect(url_for('upload.show_uploads'))
    flash(f'Unknown request: {action}', 'error')
    return redirect(url_for('upload.upload_settings', coll=coll))


@bp.route('newupload')
def new_upload():
    # Create an upload-collection
    # First generate a unique upload name
    unique = False
    while not unique:
        name = randomname.get_name()
        with irods_manager.session(current_user) as session:
            q = session.query(CollectionMeta.value).filter(\
                Criterion('=', CollectionMeta.name, ATTR_UPLOADNAME)).filter(\
                Criterion('=', CollectionMeta.value, name))
            unique = q.execute().length == 0

    # Now generate a collection for the upload
    coll = unique_coll(os.path.join('/', current_user.irods_zone, 'home', current_user.username), prefix=name)
    with irods_manager.session(current_user) as session:
        collobj = session.collections.get(coll)
        get_or_set_uid(collobj)
        cached_iqry.scollmetaval(coll, ATTR_UPLOADNAME, name)
        cached_iqry.scollmetaval(coll, ATTR_UPLOAD, UploadType.Pending)
        if (parent := request.args.get('parent')) is not None:
            cached_iqry.scollmetaval(coll, ATTR_UPLOADPARENT, parent)
            projectID = cached_iqry.qcollmetaval(parent, ATTR_PROJECTID)
            if projectID:
                cached_iqry.scollmetaval(coll, f'{ATTR_UPLOADSETTINGS}projectID', projectID)
                suggested_name = collection_basename(parent)
                if suggested_name:
                    cached_iqry.scollmetaval(coll, f'{ATTR_UPLOADSETTINGS}collection', suggested_name)

    return redirect(url_for('upload.upload_settings', coll=coll ))

@bp.route('_posttest', methods=['POST'])
def posttest():
    return 'OK', 200

