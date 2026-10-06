NGSRUN_FIELDS = {
    'id': {'title': 'Run ID', 'format': 'int', 'field': 'id', 'sortable': 'true', 'visible': 'true', 'align': 'center', 'filtercontrol': 'input'},
    'creation_date': {'title': 'Creation Date', 'format': 'timestamp', 'field': 'creation_date', 'sortable': 'true', 'visible': 'false'},
    'name': {'title': 'Name', 'format': 'text', 'field': 'name', 'sortable': 'true', 'visible': 'true', 'align': 'center', 'filtercontrol': 'input'},
    'flowcell': {'title': 'Flowcell', 'format': 'text', 'field': 'flowcell', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'input', 'formatter': 'flowcellFormatter'},
    'project': {'title': 'Project', 'format': lambda k, v: 'string' if v == 'Multiple' else 'projectid', 'field': 'project', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'select'},
    'owner': {'title': 'User', 'format': 'text', 'field': 'owner', 'sortable': 'true', 'visible': 'true', 'filtercontrol': 'select'},
    'datacoll': {'title': 'Collection', 'format': 'irods_collection', 'field': 'datacoll', 'sortable': 'false', 'visible': 'true'},
    'description': {'title': 'Description', 'format': 'text', 'field': 'description', 'sortable': 'false', 'visible': 'false', 'filtercontrol': 'input'}
}

BARCODE_FIELDS = {
    'enabled': {'title': 'Enabled', 'field': 'enabled', 'sortable': 'true'},
    'barcode': {'title': 'Barcode', 'field': 'barcode', 'sortable': 'true'},
    'sampleid': {'title': 'ID', 'field': 'sampleid', 'sortable': 'true'},
    'virus_target': {'title': 'Virus Target', 'field': 'virus_target', 'sortable': 'true'},
    'primer_set': {'title': 'Primer Set', 'field': 'primer_set', 'sortable': 'true'},
    'kit': {'title': 'Kit', 'field': 'kit', 'sortable': 'true'},
    'description': {'title': 'Description', 'field': 'description', 'sortable': 'true'},
    'project': {'title': 'Project', 'format': 'projectid', 'field': 'project', 'sortable': 'true', 'filtercontrol': 'select'}
}