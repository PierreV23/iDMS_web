import json
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from idms.common.irods.irods_sessions import irods_manager
from irods.models import Collection, CollectionMeta
from irods.column import Criterion
from idms.web.app.utils import cached_iqry
from idms.web.app.plugin import BasePlugin

PLUGIN_NAME = 'sequencer_report'

bp = Blueprint(
    PLUGIN_NAME,
    __name__,
    template_folder='templates',
    static_folder='static',
    url_prefix=f'/{PLUGIN_NAME}'
)

class SequencerReport(BasePlugin):
    name = PLUGIN_NAME
    description = 'Sequencer data import report'
    optional = True
    def setup(self):
        self.register_menu_item(url=f"/{self.name}/sequencers", name='sequencers', label="Sequencers", icon="fas fa-table", parent='reports')
        self.app.register_blueprint(bp)


@bp.route('/seqdata')
@login_required
def sequencer_data():
    if not current_user.is_admin:
        return('<tr><td colspan=3>Access denied</td></tr>')
    with irods_manager.session(current_user) as session:
        # FIND SERIALS
        qry = session.query(CollectionMeta.value).filter(
            Criterion('=', CollectionMeta.name, 'sequencing::serial')
        )
        serials = { s[CollectionMeta.value] for s in qry }
        # Find last import
        imports = cached_iqry.qcollbymetaattr('ID')
        sequencer_data = []
        for serial in serials:
            record = {
                'serial': serial
            }
            mycolls = cached_iqry.qcollbymeta('sequencing::serial', serial)
            rootcolls = inter2(imports, mycolls)
            rootcolls = sorted(rootcolls, key = lambda x: x[Collection.create_time])
            if rootcolls:
                newest = rootcolls[-1]
                record['time'] = newest[Collection.create_time].strftime('%Y-%m-%d %H:%M:%S')
                for f in [ 'brand', 'host', 'platform' ]:
                    record[f] = cached_iqry.qcollmetaval(newest[Collection.name], f'sequencing::{f}')
            record['runs'] = len(rootcolls)
            sequencer_data.append(record)
        columns = [
            { "field": "serial", "title": "Serial", "sortable": True },
            { "field": "time", "title": "Last data uploaded", "sortable": True },
            { "field": "brand", "title": "Sequencing brand",  "sortable": True },
            { "field": "platform", "title": "Sequencing platform",  "sortable": True },
            { "field": "host", "title": "Sequencing host",  "sortable": True },
            { "field": "runs", "title": "Runs", "sortable": True}
        ]
        data = {
            'id': 'sequencing_report',
            'columnsJSON': json.dumps(columns),
            'dataJSON': json.dumps(sequencer_data),
        }
    return render_template('bootstraptable.html', data=data)

@bp.route('/sequencers')
def sequence():
    return render_template('report_sequencers.html')

def inter2(a, b):
    """Return intersection of two list of collection objects

    Args:
        a (list): List of Collection objects
        b (list): List of Collection objects

    Returns:
        list: List of Collection objects (a & b)
    """    
    aa = { x[Collection.id]: x for x in a }
    ai = set(aa)
    bi = { x[Collection.id] for x in b }
    ids = ai & bi
    return [ aa[i] for i in ids ]


    

