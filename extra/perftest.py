import os
import ssl
from irods.session import iRODSSession
from irods.models import DataObject, Collection, CollectionMeta
from irods.column import Criterion
from stats import TD

TESTFLOWCELLS = [ 'FAS35315', 'FAS35321', 'FAS61137', 'FAS37788' ]

def irodsConnect(irodsfile="", use_ssl=False, **kwargs):
    """Connect to irods iCAT and return iRODSSession object

    Args:
        irodsfile: irods environment file to use.
        use_ssl: use ssl if True
    
    Returns:
        iRODSSession object
    """
    if irodsfile:
        envFile = irodsfile
    else:
        try:
            envFile = os.environ['IRODS_ENVIRONMENT_FILE']
        except KeyError:
            envFile = os.path.expanduser('~/.irods/irods_environment.json')

    if use_ssl:
        context = ssl._create_unverified_context(purpose=ssl.Purpose.SERVER_AUTH,
                                             cafile=None, capath=None, cadata=None)
        ssl_settings = {'irods_ssl_ca_certificate_file': '/etc/irods/ssl/irods.crt',
                        'ssl_context': context}
        session = iRODSSession(irods_env_file=envFile, **ssl_settings, **kwargs)
    else:
        session = iRODSSession(irods_env_file=envFile, **kwargs)
    return session

t0 = TD('irods')
session = irodsConnect(use_ssl=True)
t0.cp('session create')
for flowcell in TESTFLOWCELLS:
    q = session.query(Collection.name).filter(\
        Criterion('=', CollectionMeta.name, 'minion::flow_cell_id')).filter(\
        Criterion('=', CollectionMeta.value, flowcell)).filter(\
        Criterion('like', Collection.name, '/rivmZone/projects/ngslab/minion/%'))
    t0.cp(f'q create {flowcell}')
    colls = [ x for x in q ]
    t0.cp(f'q run {flowcell}')
    if colls:
        print(colls[0][Collection.name])
    t0.cp(f'q print {flowcell}')


