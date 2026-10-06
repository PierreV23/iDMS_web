import json
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from idms.common.irods.irods_sessions import irods_manager
from irods.models import Resource
from irods.column import Criterion
from idms.web.app.utils import cached_iqry
from idms.web.app.utils.datafield import datafield, Datatypes
from idms.web.app.plugin import BasePlugin

PLUGIN_NAME = 'resource_report'

bp = Blueprint(
    PLUGIN_NAME,
    __name__,
    template_folder='templates',
    static_folder='static',
    url_prefix=f'/{PLUGIN_NAME}'
)

class ResourceReport(BasePlugin):
    name = PLUGIN_NAME
    description = 'Resource data usage report'
    optional = True
    def setup(self):
        self.register_menu_item(url=f"/{self.name}/report", name=self.name, label="Resource report", icon="fas fa-table", parent='reports')
        self.app.register_blueprint(bp)

@bp.route('/resdata')
@login_required
def resource_data():
    if not current_user.is_admin:
        return('<tr><td colspan=3>Access denied</td></tr>')
    with irods_manager.session(current_user) as session:
        # FIND RESOURCE USAGE
        qry = session.query(Resource)
        resources = list(qry)
        resource_data = []
        for resource in resources:
            record = { 'resource': resource[Resource.name]}
            free = resource[Resource.free_space]
            if str(free).isnumeric():
                record['free'] = datafield('free', free, Datatypes.BYTES).htmlstring
            else:
                record['free'] = 'UNKNOWN'
            resource_data.append(record)
        columns = [
            { "field": "resource", "title": "Resource", "sortable": True },
            { "field": "free", "title": "Free space", "sortable": True },
            { "field": "size", "title": "Size",  "sortable": True },
            { "field": "percentage", "title": "Percent full",  "sortable": True }
        ]
        data = {
            'id': 'resource_report',
            'columnsJSON': json.dumps(columns),
            'dataJSON': json.dumps(resource_data),
        }
    return render_template('bootstraptable.html', data=data)

@bp.route('/report')
def sequence():
    return render_template('report_resources.html')


    

