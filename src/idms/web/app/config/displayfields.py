JOB_FIELDS = {
    'sys::runsheet::id': {'title': 'Name', 'format': 'runsheet', 'field': 'id', 'sortable': 'true', 'visible': 'true'},
    'sys::runsheet::state': {'title': 'State', 'format': 'text', 'field': 'state', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'select'},
    'sys::runsheet::description': {'title': 'Description', 'format': 'text', 'field': 'description', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'input'},
    'sys::runsheet::processgroupid': {'title': 'Group ID', 'format': 'processgroupguid', 'field': 'processgroupid', 'sortable': 'true', 'visible': 'true'},
    'sys::runsheet::create_time': {'title': 'Create time', 'format': 'timestamp', 'field': 'create_time', 'sortable': 'true', 'visible': 'true'},
    'sys::run::start_time': {'title': 'Start time', 'format': 'timestamp', 'field': 'start_time', 'sortable': 'true', 'visible': 'true'},
    'sys::run::finish_time': {'title': 'End time', 'format': 'timestamp', 'field': 'finish_time', 'sortable': 'true', 'visible': 'true'},
    'sys::runsheet::projectID': {'title': 'Project', 'format': 'projectid', 'field': 'projectid', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'select'},
    'sys::run::exit_code': {'title': 'Exit Code', 'format': 'int', 'field': 'exit_code', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'select'},
    'sys::run::result': {'title': 'Result', 'format': 'text', 'field': 'result', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'select'},
    'sys::runsheet::input_collection': {'title': 'Input Collection', 'format': 'irods_collection', 'field': 'input_collection', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'input'}
}

PG_FIELDS = {
    'processgroupguid': {'title': 'Group ID', 'format': 'processgroupguid', 'field': 'processgroupid', 'sortable': 'true', 'visible': 'true'},
    'processgroup': {'title': 'Group', 'format': 'text', 'field': 'processgroup', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'select'},
    'description':  {'title': 'Description', 'format': 'text', 'field': 'description', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'input'},
    'state': {'title': 'Group state', 'format': 'text', 'field': 'state', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'select'},
    'states': {'title': 'Process states', 'format': 'text', 'field': 'states', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'input'},
    'exit_code': {'title': 'Result', 'format': 'int', 'field': 'exit_code', 'sortable': 'false', 'visible': 'true'},
    'process_count': {'title': '#', 'format': 'int', 'field': 'count', 'sortable': 'true', 'visible': 'true'},
    'project': {'title': 'Project', 'format': 'projectid', 'field': 'projectid', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'select'},
    'requesting_user': {'title': 'User', 'format': 'text', 'field': 'requesting_user', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'select'},
    'create_time': {'title': 'Create time', 'format': 'timestamp', 'field': 'create_time', 'sortable': 'true', 'visible': 'true'},
    'start': {'title': 'Start Time', 'format': 'timestamp', 'field': 'start_time', 'sortable': 'true', 'visible': 'true'},
    'finish': {'title': 'End Time', 'format': 'timestamp', 'field': 'finish_time', 'sortable': 'true', 'visible': 'true'},
    'input_collection': {'title': 'First Input Collection', 'format': 'irods_collection', 'field': 'first_input_collection', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'input'}
}

PG_JOB_FIELDS = {
    'sys::runsheet::id': {'title': 'Name', 'format': 'runsheet', 'field': 'id', 'sortable': 'true', 'visible': 'true'},
    'sys::runsheet::state': {'title': 'State', 'format': 'text', 'field': 'state', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'select'},
    'sys::runsheet::description': {'title': 'Description', 'format': 'text', 'field': 'description', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'input'},
    'sys::runsheet::processgroupid': {'title': 'Group ID', 'format': 'processgroupguid', 'field': 'processgroupid', 'sortable': 'true', 'visible': 'false'},
    'sys::runsheet::create_time': {'title': 'Create time', 'format': 'timestamp', 'field': 'create_time', 'sortable': 'true', 'visible': 'true'},
    'sys::run::start_time': {'title': 'Start time', 'format': 'timestamp', 'field': 'start_time', 'sortable': 'true', 'visible': 'true'},
    'sys::run::finish_time': {'title': 'End time', 'format': 'timestamp', 'field': 'finish_time', 'sortable': 'true', 'visible': 'true'},
    'sys::runsheet::projectID': {'title': 'Project', 'format': 'projectid', 'field': 'projectid', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'select'},
    'user::run::exit_code': {'title': 'Exit Code', 'format': 'int', 'field': 'exit_code', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'select'},
    'sys::run::result': {'title': 'Result', 'format': 'text', 'field': 'result', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'select'},
    'output_collection': {'title': 'Output Collection', 'format': 'collection_id', 'field': 'dataset_id', 'sortable': 'false', 'visible': 'true', 'filtercontrol': 'input'}    
}

RESOURCE_PROPS = {
    'site': {
        'label': 'Site',
        'meta': 'sys::site',
        'type': 'select',
        'options': ['RIVM', 'SURF'],
        'help': 'The physical site this resource is in'
    },
    'group': {
        'label': 'Group',
        'meta' : 'sys::tiering::group',
        'type' : 'text',
        'help' : 'The resource group that this resource belongs to'
    },
    'group_id': {
        'label': 'ID',
        'meta': 'sys::tiering::group',
        'type': 'number',
        'unit': True,
        'help': 'Unique id within a resource group'
    },
    'copies': {
        'label': 'Copies',
        'meta': 'sys::resource::copies',
        'type': 'number',
        'help': 'The number of copies that this resource provides'
    },
    'cost': {
        'label': 'Cost',
        'meta': 'sys::resource::cost',
        'type': 'number',
        'help': 'Number that indicates cost for storing data on this resource'
    },
    'maxcopies': {
        'label': 'Max copy actions',
        'meta': 'sys::resource::maxcopies',
        'type': 'number',
        'help': 'Maximum number of concurrent tiering actions that will copy data TO this resource'
    },
    'age_before_copy': {
        'label': 'Minimum age before copy (h)',
        'meta': 'sys::resource::min_age_before_copy',
        'type': 'number',
        'factor': 3600,
        'help': 'Data has to have this age before it will be copied to this resource'
    },
    'age_before_trim': {
        'label': 'Minimum age before trim (h)',
        'meta': 'sys::resource::min_age_before_trim',
        'type': 'number',
        'factor': 3600,
        'help': 'Data has to have this age before it will be removed from this resource'
    },
    'reference_data_retention': {
        'label': 'Reference data retention (h)',
        'meta': 'sys::resource::reference_data_retention',
        'type': 'number',
        'factor': 3600,
        'help': 'Reference data versions will be kept on this resource for this period after last use'
    },    
    'minfree': {
        'label': 'Minimum free space (GB)',
        'meta': 'sys::resource::spacelimit',
        'type': 'text',
        'factor': 1000000000,
        'help': 'No data will be copied (by tiering) to this resource once this limit is exceeded'
    },
    'targetfree': {
        'label': 'Target free space (GB)',
        'meta': 'sys::resource::spacetarget',
        'type': 'number',
        'factor': 1000000000,
        'help': 'Tiering process will remove data from this resource once this limit is exceeded'
    },
    'local': {
        'label': 'Local',
        'meta': 'sys::resource::local',
        'type': 'bool',
        'help': 'This resource is on-site'
    },
    'online': {
        'label': 'Online',
        'meta': 'sys::resource::online',
        'type': 'bool',
        'help': 'Data on this resoucre can be accessed directly'
    },
    'stage': {
        'label': 'Stage',
        'meta': 'sys::resource::stage',
        'type': 'bool',
        'help': 'Data is copied to this resource before a pipeline starts'
    },
    'keep': {
        'label': 'Keep',
        'meta': 'sys::resource::keep',
        'type': 'bool',
        'help': 'Once data is on this resource, it will not be removed (except when "local" is required)'
    },
    'surf': {
        'label': 'SURF',
        'meta': 'sys::resource::surf',
        'type': 'bool',
        'help': 'This resource is at SURF. Special dm functions will be used'
    },
    'tar': {
        'label': 'TAR',
        'meta': 'sys::resource::tar',
        'type': 'bool',
        'help': 'Datasets are archived in a TAR file before being moved to this resource'
    },
    'manifest': {
        'label': 'MANIFEST',
        'meta': 'sys::resource::manifest',
        'type': 'bool',
        'help': 'TAR manifest files are stored on this resource'
    },
    'refdata': {
        'label': 'RefData',
        'meta': 'sys::resource::reference_data_resource',
        'type': 'bool',
        'help': 'This resource is suitable to store Reference Datasets'
    },
    'enabled': {
        'label': 'Enabled',
        'meta': 'sys::resource::enabled',
        'type': 'bool',
        'help': 'This resource can be used'
    },
    'available': {
        'label': 'Available',
        'meta': 'sys::resource::available',
        'type': 'status',
        'help': 'This resource is found to be available by the automatic resource test script'
    },    
}
