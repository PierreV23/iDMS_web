from flask_login import current_user
from .utils import flaskcache
from .utils.projectdb_api import rest_call
from idms.web.app.utils import cached_iqry
from irods.models import Collection, CollectionMeta
from irods.column import Criterion
from datetime import datetime, timezone
from idms.common.irods.irods_sessions import irods_manager
from idms.common.constants.attribute_names import (
    ATTR_RUNSHEET_PROCESSID,
    ATTR_RUN_STARTTIME,
    ATTR_RUN_FINISHTIME
)

@flaskcache.cache.memoize(timeout=3600, make_name=flaskcache.dep_zone)
def all_collection_attr_value(attr):
    with irods_manager.session(current_user) as session:
        q = session.query(Collection.name, CollectionMeta.value).filter(
            Criterion('=', CollectionMeta.name, attr)
        )
        return { c[Collection.name]: c[CollectionMeta.value] for c in q }    

def runspermonth(process_id):
    process_record, result = rest_call('GET', f'processes/{process_id}')
    if result != 200:
        return {}
    process = process_record.get('name')
    colls = cached_iqry.qcollbymeta(ATTR_RUNSHEET_PROCESSID, process)
    times = all_collection_attr_value(ATTR_RUN_FINISHTIME)

    data = {}
    mintime = 10000000000
    maxtime = 0
    for coll in colls:
        finish = times.get(coll[Collection.name], 'NOTIME')
        try:
            dt = datetime.fromtimestamp(int(float(finish)), tz=timezone.utc)
            label = f'{dt.year}/{dt.month}'
            data[label] = data.get(label, 0) + 1
            mintime = min(mintime, int(float(finish)))
            maxtime = max(maxtime, int(float(finish)))
        except:
            # Skip this record
            pass
    for ts in range(mintime, maxtime, 28*86400):
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        label = f'{dt.year}/{dt.month}'
        data.setdefault(label, 0)
    return data


def runspermetaattr(process_id, attr_name):
    process_record, result = rest_call('GET', f'processes/{process_id}')
    if result != 200:
        return {}
    process = process_record.get('name')
    colls = cached_iqry.qcollbymeta(ATTR_RUNSHEET_PROCESSID, process)
    print(f'SEARCH {attr_name}')
    values = all_collection_attr_value(attr_name)

    data = {}
    for coll in colls:
        label = values.get(coll[Collection.name])
        if label:
            data[label] = data.get(label, 0) + 1
        
    return data

def runtimedist(process_id):
    
    def get_label(bucket):
        return f'{"0" if bucket<9 else ""}{bucket+1}h'
    
    BUCKETS = 24
    BUCKET_SIZE = 3600
    process_record, result = rest_call('GET', f'processes/{process_id}')
    if result != 200:
        return {}
    process = process_record.get('name')
    colls = cached_iqry.qcollbymeta(ATTR_RUNSHEET_PROCESSID, process)
    finish_times = all_collection_attr_value(ATTR_RUN_FINISHTIME)
    start_times = all_collection_attr_value(ATTR_RUN_STARTTIME)
    runtimes = {}
    data = {}
    for coll_record in colls:
        coll = coll_record[Collection.name]
        try:
            runtime = int(float(finish_times.get(coll, 'NONE'))) - int(float(start_times.get(coll, 'NONE')))
            runtimes[coll] = runtime
        except:
            pass
    for i in range(BUCKETS):
        data[get_label(i)] = 0
    for runtime in runtimes.values():
        bucket = runtime//BUCKET_SIZE
        if bucket >= BUCKETS:
            data['>1d'] = data.get('>1d', 0) + 1
        else:
            label = get_label(bucket)
            data[label] = data.get(label, 0) + 1
        
    return data

def runtimehist(process_id):
    CUTOFF = 7*86400
    process_record, result = rest_call('GET', f'processes/{process_id}')
    if result != 200:
        return {}
    process = process_record.get('name')
    colls = cached_iqry.qcollbymeta(ATTR_RUNSHEET_PROCESSID, process)
    finish_times = all_collection_attr_value(ATTR_RUN_FINISHTIME)
    start_times = all_collection_attr_value(ATTR_RUN_STARTTIME)
    runtimes = {}
    data = {}
    for coll_record in colls:
        coll = coll_record[Collection.name]
        try:
            runtime = int(float(finish_times.get(coll, 'NONE'))) - int(float(start_times.get(coll, 'NONE')))
            runtimes[coll] = runtime
        except:
            pass

    total_time = {}
    count = {}
    for coll_record in colls:
        coll = coll_record[Collection.name]
        finish = finish_times.get(coll, 'NOTIME')
        try:
            dt = datetime.fromtimestamp(int(float(finish)), tz=timezone.utc)
            runtime = runtimes.get(coll)
            if runtime and runtime < CUTOFF:
                label = f'{dt.year}/{dt.month}'
                total_time[label] = total_time.get(label, 0) + runtime
                count[label] = count.get(label, 0) + 1
        except:
            # Skip this record
            pass
        
    data = { label: total_time/count[label] for label, total_time in total_time.items() }
        
    return data
    