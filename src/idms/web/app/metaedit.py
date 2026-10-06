import os
import json
import jsonavu
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_login import current_user
from idms.web.app.utils import cached_iqry
from idms.common.constants.attribute_names import (
                            ATTR_SCHEMA_IN_USE,
                            ATTR_PROJECT_SUFFIX,
                            ATTR_DATASET_UPLOAD_SUFFIX,
                            ATTR_DATASET_DEFAULT_SUFFIX,
                            ATTR_REFERENCE_SUFFIX,
                            ATTR_METADATA_PREFIX,
                            ATTR_UPLOAD_DEFAULT_PREFIX,
                            ATTR_UPLOADMETA,
                            AVU2JSON_PREFIX
                        )
from idms.common.irods.irods_sessions import irods_manager
from irods.models import CollectionMeta
from irods.exception import CollectionDoesNotExist, DataObjectDoesNotExist
from pathlib import Path

bp = Blueprint('metaedit', __name__, url_prefix='/metaedit')

def schemaPaths(name):
    defaults = {
        'SCHEMATA_BASE_PATH': 'system/schemata',
        'DATASET_SCHEMATA_PATH': 'datasets',
        'PROJECT_SCHEMATA_PATH': 'projects',
        'REFERENCE_DATASET_SCHEMATA_PATH': 'referencedata'
    }
    if name in defaults:
        return current_app.config.get(name, defaults[name])
    raise AttributeError

def get_schemata( schema_collection ):
    """ Return list of all schemata from the leaf down to the base collection
        as a dictionary:
        {
            schema-name : schema-location
            TODO: what if the same name is on different levels
        }
    """
    def get_schemata_in_coll( coll ):
        result = {}
        for obj in coll.data_objects:

            schema_path = Path(obj.name)
            # Only display .json
            if schema_path.suffix != '.json':
                continue

            result[schema_path.stem] = f"{coll.path}/{obj.name}"

        return result

    result = {}

    schema_collection_path = Path('/', current_user.irods_zone, schema_collection)

    with irods_manager.session(current_user) as session:
        
        while schema_collection_path != '/' and schema_collection_path != Path('/', current_user.irods_zone, schemaPaths('SCHEMATA_BASE_PATH')).parent: 
            try:
                schema_coll = session.collections.get(str(schema_collection_path))
                result.update(get_schemata_in_coll(schema_coll))
            except CollectionDoesNotExist as e:
                continue
            finally:
                # go up one level in the collection tree
                schema_collection_path = schema_collection_path.parent
    return result


@bp.route('/')
# def metadata_editor():
#     schema_endpoint = url_for('metaedit.schemata')
#     return render_template('metadata_editor.html', **request.args)


@bp.route('/schemata_project')
def schemata_for_project():
    """ Schemata for a project
    """
    project_name = request.args.get('project_name', '')
    meta_schemata_collection = Path('/', current_user.irods_zone, schemaPaths('SCHEMATA_BASE_PATH'), schemaPaths('PROJECT_SCHEMATA_PATH'), project_name)
    meta_values_collection = request.args.get('collection')
    prefix=ATTR_METADATA_PREFIX
    suffix=ATTR_PROJECT_SUFFIX
    return schemata(meta_schemata_collection, meta_values_collection, prefix, suffix)

@bp.route('/schemata_dataset_upload')
def schemata_for_dataset_upload():
    """ Schemata for a dataset upload
    """
    project_name = request.args.get('project_name', '')
    meta_schemata_collection = Path('/', current_user.irods_zone, schemaPaths('SCHEMATA_BASE_PATH'), schemaPaths('DATASET_SCHEMATA_PATH'), project_name)
    meta_values_collection = request.args.get('collection')
    prefix=ATTR_UPLOADMETA
    suffix=ATTR_DATASET_UPLOAD_SUFFIX
    return schemata(meta_schemata_collection, meta_values_collection, prefix, suffix)

@bp.route('/schemata_dataset_default')
def schemata_for_dataset_default():
    """ Schemata for a dataset, available as default metadata, used in a dataset upload
    """
    project_name = request.args.get('project_name', '')
    meta_schemata_collection = Path('/', current_user.irods_zone, schemaPaths('SCHEMATA_BASE_PATH'), schemaPaths('DATASET_SCHEMATA_PATH'), project_name)
    meta_values_collection = request.args.get('collection')
    prefix=ATTR_UPLOAD_DEFAULT_PREFIX
    suffix=ATTR_DATASET_DEFAULT_SUFFIX
    return schemata(meta_schemata_collection, meta_values_collection, prefix, suffix)

@bp.route('/schemata_reference')
def schemata_for_reference_dataset():
    """ Schemata for a reference dataset, so not linked to a project
    """
    refdata_name = request.args.get('refdata_name', '')
    meta_schemata_collection = Path('/', current_user.irods_zone, schemaPaths('SCHEMATA_BASE_PATH'), schemaPaths('REFERENCE_DATASET_SCHEMATA_PATH'), refdata_name)
    meta_values_collection = request.args.get('collection')
    prefix=ATTR_METADATA_PREFIX
    suffix=ATTR_REFERENCE_SUFFIX
    return schemata(meta_schemata_collection, meta_values_collection, prefix, suffix)


def schemata(meta_schemata_collection :Path, meta_values_collection :str, prefix: str, suffix :str):
    """ Returns a list of schemata

        Request parameter is the upload path
        Returns a bootstraptable data structure like:
        {
        'rows': [
                    {'schema': <schemaname>,
                    'selected: True or False,
                    'schema_has_data': True or False,
                    'schemapath': <schemapath>,
                    'order': order to display the schemata
                }, {...}
            ]
        }
    """

    # Retrieve available schemata for this project
    available_schemata = get_schemata(meta_schemata_collection)

    # Get schemata in use for the collection (specific suffix -> type)
    schemata_in_use = [a[CollectionMeta.value] for a in cached_iqry.qcollmetavals(meta_values_collection, ATTR_SCHEMA_IN_USE + suffix)]

    # If the form has data there is a metadata attribute with a combination of <prefix> and the path of the schema
    coll_meta_names = [a[CollectionMeta.name] for a in cached_iqry.qcollmeta(meta_values_collection)]

    rows = [
        {'schema': k, 
         'selected': v in schemata_in_use, 
         'schema_has_data': prefix + v in coll_meta_names, 
         'schemapath': v, 
         'order': v.count('/')} for k, v in available_schemata.items()
    ]
    return jsonify({'rows': rows})


@bp.route('_store_metadata', methods=['POST'])
def store_metadata():
    """ Stores the metadata provided by the data structure
        under the schema <schemapath> on a collection
        data can be empty if deleting all metadata in a form!
    """
    collection = request.json.get('collection')
    data = request.json.get('data')
    schemapath = request.json.get('schemapath')
    prefix = request.json.get('prefix')

    if not (collection and schemapath and prefix):
        return jsonify({}), 500
    try:
        store_collection_metadata_structured(collection, data, schemapath, prefix)
        return jsonify({'result': 'OK'}), 200
    except Exception as e:
        logging.error(f'Not allowed to edit this metadata: {e}')
        return jsonify({}), 500

@bp.route('_set_schemata_for_collection', methods=['POST'])
def set_schemata_for_collection():
    """ Store the schemata used on the collection with
        key ATTR_UPLOAD_PREFIX
        There can be multiple schemata

        args:
            attr_type: default schema attribute or in use attribute
            collection: collection path
            schemapath: path to the schema dataobject
            action(str): add or remove
    """
    attr_type = request.json.get('attr_type')
    collection = request.json.get('collection')
    schemapath = request.json.get('schemapath')
    action = request.json.get('action')
    prefix = request.json.get('prefix')

    if not (collection and schemapath and action):
        return jsonify({}), 500
    if action == 'add':
        try:
            cached_iqry.addcollmetaval(collection, attr_type, schemapath)
            return jsonify({ 'result': 'OK' }), 200
        except Exception as e:
            logging.error(f'Not allowed to add schemata: {e}')
            return jsonify({}), 500
    if action == 'remove':
        # Remove the related metadata
        try:
            cached_iqry.delcollmeta(collection, attr_type, schemapath)
            store_collection_metadata_structured(collection, None, schemapath, prefix)
            remove_collection_metadata(collection, prefix + schemapath)
            return jsonify({ 'result': 'OK' }), 200
        except Exception as e:
            logging.error(f'Not allowed to remove schemata: {e}')
            return jsonify({}), 500


def remove_all_constraints(schema_json :dict) ->dict:

    '''
    Recursively remove all `required` constraints from a JSON Schema.
    Also set minItems to 0.
    Works for nested objects, as well as the root required field.
    For use in default schemata, where no fields should be required

    input: json schema
    output: json schema without required fields and with minItems = 0
    '''

    # check keys on top level
    if isinstance(schema_json, dict):
        for key, value in schema_json.items():
            if key == "required" and isinstance(value, list):
                schema_json[key] = []
            if key == "minItems" and isinstance(value, int):
                schema_json[key] = 0
            else:
                # check lower level items (nested)
                remove_all_constraints(value)

    # check items in a list, and inspect them separately
    elif isinstance(schema_json, list):
        for item in schema_json:
            remove_all_constraints(item)

    return schema_json


def remove_specific_constraints(schema_json :dict, keys :list = None) ->dict:
    '''
    Recursively remove specific `required` constraints from a JSON Schema if they are in a list of keys
    This keys can be listed in "required": or have the property "minItems": >0
    Works for nested objects, as well as the root required field.
    For use for infered metadata fields, that are not manually iput, but are requirred in the original schema

    input:  schema_json: the json schema
            keys: list of keys in schema_json to limit the removal of constraints to

    output: json schema without specific required constraints
    '''

    # No keys, return original schema
    if keys == None or keys == []:
        return schema_json

    # check keys on top level
    if isinstance(schema_json, dict):

        # Remove specific keys from "required"
        if "required" in schema_json and isinstance(schema_json["required"], list):
            schema_json["required"] = [ field for field in schema_json["required"] if field not in keys ]

        # Traverse properties while knowing the property name, these could be nested!
        if "properties" in schema_json and isinstance(schema_json["properties"], dict):

            for prop_name, prop_schema in schema_json["properties"].items():

                if not prop_name in keys:
                    continue
                if "minItems" in prop_schema:
                    prop_schema["minItems"] = 0

                # check the nested items for constraints
                remove_specific_constraints(prop_schema, keys)

    # check items in a list of dicts, and inspect them one by one
    elif isinstance(schema_json, list):
        for item in schema_json:
            remove_specific_constraints(item, keys)

    return schema_json


@bp.route('_get_schema_and_data', methods=['GET'])
def get_schema_and_data():
    """ Retrieve a metadata schema, the uiSchema
    and the already existing metadata for the schema

    Params:
        schemapath: path to the schema dataobject
        collection: path to the collection
        
    Error handling:
        Errors will be displayed in the interface
        5 kind of errors can occur: 
            1) json.loads() error (invalid json)
            2) reactJSON.Parse() error (valid json, not readable in React) 
                -> displayed in form
            3) ui_json.loads() error
            4) ui_json Parse error 
                -> displayed in form
            5) validation error in JSON (conditions are not met)
                -> displayed and highlighted in Form
    """
    
    schema = "{}"
    ui_schema = "{}"
    data = "{}"
    
    prefix = request.args.get('prefix')
    schemapath = request.args.get('schemapath')
    meta_default_values_collection = request.args.get('meta_default_values_collection')
    meta_values_collection = request.args.get('collection')
    metadata_infered = current_app.config.get('METADATA_INFERED', {})

    with irods_manager.session(current_user) as session:
        obj = session.data_objects.get(schemapath)

    with obj.open('r') as f:
        schema = f.read().decode('UTF-8')

        # the json schema is always provided and should be readable
        try:
            schema_json = json.loads(schema)
        except json.JSONDecodeError as e:
            logging.error(f"Invalid schema JSON: {schemapath}: {e}")
            return jsonify({
                'error': f'Invalid schema JSON: {schemapath.split('/')[-1]}. Fixing the JSON will enable you to add or edit metadata',
                'details': str(e)
            }), 400
        except Exception as e:
            logging.error(f"Error loading schema JSON: {schemapath}: {e}")
            return jsonify({
                'error': f'Error loading schema JSON: {schemapath.split('/')[-1]}',
                'details': str(e)
            }), 500

        # Remove specific required constraints from schema
        # if metadata is inferred by other metadata fields
        for schemaname, keys in metadata_infered.items():
            if schemapath.endswith(schemaname):
                schema_json = json.loads(schema)
                schema_json = remove_specific_constraints(
                    schema_json, keys
                )
                schema = json.dumps(schema_json)

        # Remove all required constraints for default metadata
        if prefix == ATTR_UPLOAD_DEFAULT_PREFIX:
            schema_json = json.loads(schema)
            schema_json = remove_all_constraints(schema_json)
            schema = json.dumps(schema_json)

    # Find UI schema, if provided
    ui_schemapath = (
        os.path.dirname(schemapath)
        + '/ui/ui_'
        + os.path.basename(schemapath)
    )

    # Validate the ui_schema if provided
    try:
        ui_obj = session.data_objects.get(ui_schemapath)
        with ui_obj.open('r') as f:
            ui_schema = f.read().decode('UTF-8')
            ui_schema_json = json.loads(ui_schema)
            ui_schema = json.dumps(ui_schema_json)
    except json.JSONDecodeError as e:
        logging.error(f"Invalid UI schema JSON: {ui_schemapath}: {e}")
        return jsonify({
                'error': f'Invalid UI schema JSON: {ui_schemapath.split('/')[-1]}',
                'details': str(e)
            }), 400
    # ui schema is optional, so pass if collection or object is not in iRODS
    except CollectionDoesNotExist as e:
        logging.info(f'ui folder does not exist for {ui_schemapath}')
        pass
    except DataObjectDoesNotExist as e:
        logging.info(f'ui json file does not exist for {ui_schemapath}')
        pass
        
    default_data = {}

    # find default metadata from default values collection 
    if meta_default_values_collection:
        default_data = get_collection_metadata_structured(
            meta_default_values_collection,
            ATTR_UPLOAD_DEFAULT_PREFIX
        ).get(schemapath, {})

    # The default metadata for dataset upload is the Project metadata
    if meta_default_values_collection == meta_values_collection:
        project_schemapath = schemapath.replace(
            schemaPaths('DATASET_SCHEMATA_PATH'),
            schemaPaths('PROJECT_SCHEMATA_PATH')
        )

        default_data = get_collection_metadata_structured(
            meta_default_values_collection,
            ATTR_METADATA_PREFIX
        ).get(project_schemapath, {})

    # 
    used_data = get_collection_metadata_structured(
        meta_values_collection,
        prefix
    ).get(schemapath, {}) or {}

    # Default values first, then existing values overwrite them
    data = default_data | used_data

    return jsonify({
        'schema': schema,
        'ui_schema': ui_schema,
        'data': json.dumps(data)
    })


def get_collection_metadata_structured(collection :str, prefix :str) -> dict:
    """ Get schema metadata from a collection

        Removes the ATTR_UPLOADPREFIX prefix from attribute name

        Use jsonavu package to retrieve metadata structure
    """
    start = len(prefix)
    collection_metadata = cached_iqry.qcollmeta(collection)
    jsonavu_metadata = [
        {
            'a': record[CollectionMeta.name][start:],
            'v': record[CollectionMeta.value],
            'u': record[CollectionMeta.units]
        } for record in collection_metadata if record[CollectionMeta.name].startswith(prefix)
    ]
    data = jsonavu.avu2json(jsonavu_metadata, AVU2JSON_PREFIX) or {}
    return data


def remove_collection_metadata(collection, prefix):
    """ Remove metadata with a specified prefix from collection
    """
    metadata = cached_iqry.qcollmeta(collection)
    for record in metadata:
        if record[CollectionMeta.name].startswith(prefix):
            cached_iqry.delcollmeta(collection, record[CollectionMeta.name])


def store_collection_metadata_structured(collection, data, schemapath, prefix):
    """ Store schema metadata from a collection

        Use jsonavu package to create metadata structure

        Does not modify data from other schemata
    """
    existing_data = get_collection_metadata_structured(collection, prefix)
    existing_data[schemapath] = data
    jsonavu_metadata = jsonavu.json2avu(existing_data, AVU2JSON_PREFIX)
    remove_collection_metadata(collection, prefix)
    for avu in jsonavu_metadata:
        # prevent saving of unwanted residual schema name, if on json top level all schemata are unchecked
        if avu['u'] != f'{AVU2JSON_PREFIX}_0_z':
            cached_iqry.scollmetaval(collection, f"{prefix}{avu['a']}", avu['v'], avu['u'])
