import time
from flask import jsonify, render_template, request, Blueprint

from idms.web.app.utils.flaskcache import cache, dep_zone
from idms.web.app.utils.datafield import datafield, Datatypes

from .utils.database import search_db

import logging

logging.basicConfig(
    format='%(filename)s:%(funcName)s:%(lineno)d - %(message)s',
    level=logging.INFO
)

""" Input structures:

searchdata: {
    'keywords': [
        'keyword1', 'keyword2'
    ],
    'meta' : {
        'attr1': 'value1',
        'attr2': 'value2'
    }
}

"""

# specific prefix strings in metadata are excluded. Specific prefixes can be included again.
attrs_to_exclude = ['sys::', 'ngsweb::']
attrs_to_include = ['sys::data::', 'sys::runsheet::']
exclude_string = ",".join(f"'{x}%'" for x in attrs_to_exclude) if attrs_to_exclude else ''
include_string = ",".join(f"'{x}%'" for x in attrs_to_include) if attrs_to_include else ''
ex_in_filter = f'''AND (meta_attr_name NOT LIKE ALL (ARRAY[{exclude_string}]) 
                    OR meta_attr_name LIKE ANY (ARRAY[{include_string}]))'''
########################

bp = Blueprint('search', __name__, url_prefix='/search')

class Const:
    KEYWORDS = 'keywords'
    META = 'meta'
    ID = 'id'
    COLLECTIONS = 'collections'
    DATAOBJECTS = 'dataobjects'
    NAME = 'name'
    VALUE = 'value'
    ATTRS = 'attrs'

class TableFormat:
    html = 'html'
    plain = 'plain'

class Tables:
    coll = 'r_coll_main'
    metamap = 'r_objt_metamap'
    meta = 'r_meta_main'
    coll_json = 'coll_json'


def search_dict(keywords, meta_attrs):
    '''Dictionary containing search parameters
    '''
    return {
        Const.KEYWORDS: keywords,
        Const.META: meta_attrs
    }


def result_data(collections, dataobjects, id, attrs=[]):
    '''Dictionary containing search results
    '''
    return {
        Const.COLLECTIONS: collections,
        Const.DATAOBJECTS: dataobjects,
        Const.ID: id,
        Const.ATTRS: attrs
    }


@bp.route('_searchtable', methods=['POST'])
def searchtable():
    '''Result table displaying the collections and specific table parameters
    '''
    data = request.json
    id = data.get('id', 0)
    tabledef = {
        'id': id,
        'pagination': 'true'
    }
    _, colls, attrs = search_collections(data)
    columns = [{
        'field': 'collection',
        'title': 'Collection'
    }]
    # We need different collection links depending on the data['format'] parameter
    dataformat = data.get('format', TableFormat.html)
    if dataformat == TableFormat.html:
        tabledata = [{ 'collection': datafield("collection", c, Datatypes.IRODS_COLLECTION).htmlstring } for c in colls ]
    elif dataformat == TableFormat.plain:
        tabledata = [{ 'collection': c } for c in colls ]
    tabledef |= {'columns': columns, 'data': tabledata, 'attrs': attrs}
    return jsonify(tabledef), 200


@bp.route('_search')
def search():
    '''This just fills the search modal
    '''
    return render_template('search2.html')


@bp.route('_x32', methods=['POST'])
def api_available_attrs():
    """Get available attributes depending on search result

    Returns:
        list: attr names
    """
    data = request.json
    keywords = data.get(Const.KEYWORDS)
    meta = data.get(Const.META)

    # Handle the case where there is no query yet
    if not(meta or keywords):
        all_attrs = all_collection_meta_attrs()
        return jsonify(sorted(all_attrs))

    _, _, attrs = search_collections(data)
    return jsonify(attrs)


@bp.route('_attrvalues', methods=['POST'])
def api_attrvalues_for_search():
    '''Get corresponding attribute values for search result collections
    '''
    data = request.json
    attr = data.get('attr')
    ids, _, _ = search_collections(data)
    if ids:
        vals = search_values_by_collection_ids_and_attr(ids, attr)
    else:
        vals = dataset_attr_values(attr)
    
    # sort and remove duplicates
    vals = sorted((x for x in vals if x is not None), key=str.lower)
   
    return jsonify(vals)


def search_collections(data):
    '''Search collections for specific search parameters
    '''
    ids = None
    all_colls = {}
    # Find keywords in collection paths
    for keyword in data.get(Const.KEYWORDS, []):
        if keyword:
            colls = datasets_with_text(keyword)
            all_colls = all_colls | colls
            if ids is None:
                ids = set(colls)
            else:
                ids = ids & set(colls)
    # Find metadata
    for attr, value in data.get(Const.META, {}).items():
        colls = collections_by_meta(attr, value)
        all_colls = all_colls | colls
        if ids is None:
            ids = set(colls)
        else:
            ids = ids & set(colls)
    if ids is None:
        ids = []
        collections = []
        attrs = all_collection_meta_attrs()
    else:
        collections = [ all_colls.get(id) for id in ids ]
        attrs = sorted([ a for a in search_attrs_by_collection_ids(sorted(ids)) if a not in data.get(Const.META, {}).keys() ])
    return sorted(ids), sorted(collections), list(attrs)


def search_attrs_by_collection_ids(ids):
    '''Search attributes for list of ids
    '''
    start_f = time.perf_counter()
            
    # define where clauses
    coll_id_filter = f"AND coll_id IN ({','.join(ids)})" if ids else ""

    sql = f"""
            SELECT meta_attr_name
            FROM {Tables.coll_json}
            CROSS JOIN LATERAL jsonb_object_keys(coll->'coll_meta') AS meta_attr_name
            WHERE COALESCE(meta_attr_name, '') <> ''
            {coll_id_filter}
            {ex_in_filter} 
            GROUP BY meta_attr_name
            ORDER BY meta_attr_name
        """

    result = { c[0] for c in runsql(sql) }
    
    end_f = time.perf_counter()

    logging.info(
    f"Query search_attrs_by_collection_ids took {end_f - start_f:.6f} seconds")

    return result
    

@cache.memoize(timeout=3600, make_name=dep_zone)
def search_values_by_collection_ids_and_attr(ids, attr):
    ''' Search values for a combination of list of collection ids and a given attribute
    '''
    start = time.perf_counter()

    sql = f"""
            SELECT coll->'coll_meta'->>'{attr}' AS meta_attr_value
            FROM {Tables.coll_json}
            WHERE coll_id IN ({','.join(ids)})
            AND coll->'coll_meta'->>'{attr}' IS NOT NULL
            ORDER BY meta_attr_value;
            """
        
    result = { c[0] for c in runsql(sql) }

    end = time.perf_counter()
    logging.info(f'Query _search_attrs_by_sorted_collection_ids took {end - start:.6f} seconds')

    return result

########################
# CACHED BASE FUNCTIONS
########################

def runsql(sql):
    ''' Executes a query
    '''
    start = time.perf_counter()
    
    with search_db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        result = [ { i: str(n) for i, n in enumerate(r) } for r in cursor.fetchall() ]

    end = time.perf_counter()

    logging.info(f'Query {sql} took {end - start:.6f} seconds')

    return result


@cache.memoize(timeout=3600, make_name=dep_zone)
def collections_by_meta(attr, value):
    '''Fetch collections with specific metadata attr, value pair
    '''
        
    sql = f"""
        SELECT coll_id, coll->>'coll_name' AS coll_name FROM {Tables.coll_json}
        WHERE coll->'coll_meta'->>'{attr}' = '{value}'
        GROUP BY 1,2
        ORDER BY 1;
        """

    result = { c[0]: c[1] for c in runsql(sql) }
    
    return result


@cache.memoize(timeout=3600, make_name=dep_zone)
def datasets_with_text(text):
    '''truncate search string for datasets search
    '''
    if len(text) > 10:
        subresults = datasets_with_text(text[:-1])
        results = { k: v for k, v in subresults.items() if text in v }
    else:
        results = _datasets_with_text(text)
    return results


@cache.memoize(timeout=3600, make_name=dep_zone)
def _datasets_with_text(text):
    ''' Find datasets containing a string in the name
    '''
    
    sql = f"""
            SELECT coll_id, coll->>'coll_name' AS coll_name
            FROM (SELECT * FROM {Tables.coll_json}
                WHERE coll->'coll_meta'->>'sys::dataset_id' IS NOT NULL) AS datasets
            WHERE coll->>'coll_name' LIKE '%{text}%';
            """
               
    result = { c[0]: c[1] for c in runsql(sql) }
    
    return result


@cache.memoize(timeout=600, make_name=dep_zone)
@bp.route('_allmetacoll')
def all_collection_meta_attrs():
    ''' Return all metadata attributes from the metadata of all collections
    '''
    sql = f"""
            SELECT meta_attr_name 
            FROM (
                SELECT jsonb_object_keys(coll->'coll_meta') AS meta_attr_name
                FROM (SELECT * FROM { Tables.coll_json }
                    WHERE coll->'coll_meta'->>'sys::dataset_id' IS NOT NULL
                    ) q
                ) q2
            WHERE meta_attr_name <> ''
            {ex_in_filter}
            GROUP BY meta_attr_name
            ORDER BY meta_attr_name
            """

    result = { c[0] for c in runsql(sql) }
    
    return result


@cache.memoize(timeout=600, make_name=dep_zone)
def dataset_attr_values(attr):
    ''' Metadata values for a given attribute
    '''
    sql = f"""
            SELECT coll->'coll_meta'->>'{attr}' AS meta_attr_value
            FROM ( SELECT * FROM {Tables.coll_json}
                    WHERE coll->'coll_meta'->>'sys::dataset_id' IS NOT NULL ) datasets
            WHERE COALESCE(coll->'coll_meta'->>'{attr}', '') <> ''
            GROUP BY coll->'coll_meta'->>'{attr}'
            """

    result = { c[0] for c in runsql(sql) }
   
    return result