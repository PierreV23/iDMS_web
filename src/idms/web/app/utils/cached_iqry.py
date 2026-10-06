from .decorators import with_irods_session
from .flaskcache import cache, dep_zone
from idms.common.irods.iqry import qusermeta, qresmeta, qcollmeta, qcollchildren, qcolldataobjects
from idms.common.irods.iqry import qcollbymetaattr, qcollbymeta, qcollbystaticmeta, qcollmetavalstatic
from idms.common.irods.iqry import qcollproperty, qdataobjmeta, qdataobjbymeta, qcolldataobjectpaths
#these are the functions we want to shadow / redefine with invalidation logic..
from idms.common.irods.iqry import delcollmeta as _delcollmeta
from idms.common.irods.iqry import rmallcollmetaattr as _rmallcollmetaattr
from idms.common.irods.iqry import addcollmetaval as _addcollmetaval
from idms.common.irods.iqry import scollmetaval as _scollmetaval
from idms.common.irods.iqry import susermetaval as  _susermetaval

#for convenience the unchanged methods?
from idms.common.irods.iqry import qcollmetaval, qusermetadict, qusermetaval, qcollmetavals, qcollmetadict
from idms.common.irods.iqry import qpathobjecttype, qcollmetavals_with_placeholder

def invalidate(collection):
    cache.delete_memoized(qcollmeta, collection=collection)
    cache.delete_memoized(qcollchildren, collection=collection)
    cache.delete_memoized(qcolldataobjects, collection=collection)


#Apply the flask caching mechanism to the helper functions of idms.common.irods
#each of the functions needs the current irods-session, so use that decorator as well
qusermeta = with_irods_session( cache.memoize(timeout=600, make_name=dep_zone)(qusermeta))
qresmeta = with_irods_session( cache.memoize(timeout=300, make_name=dep_zone)(qresmeta))
qcollmeta = with_irods_session( cache.memoize(timeout=60, make_name=dep_zone)(qcollmeta))
qcollchildren = with_irods_session( cache.memoize(timeout=300, make_name=dep_zone)(qcollchildren))

qcolldataobjects = with_irods_session( cache.memoize(timeout=120, make_name=dep_zone)(qcolldataobjects))
qcollbymetaattr = with_irods_session( cache.memoize(timeout=120, make_name=dep_zone)(qcollbymetaattr))
qcollbymeta = with_irods_session( cache.memoize(timeout=120, make_name=dep_zone)(qcollbymeta))
qcollbystaticmeta = with_irods_session( cache.memoize(timeout=86400, make_name=dep_zone, response_filter=lambda arg: bool(arg))(qcollbystaticmeta))

qcollmetavalstatic = with_irods_session( cache.memoize(timeout=86400, make_name=dep_zone, response_filter=lambda arg: bool(arg))(qcollmetavalstatic))
qcollproperty = with_irods_session( cache.memoize(timeout=86400, make_name=dep_zone)(qcollproperty))

qdataobjmeta = with_irods_session( cache.memoize(timeout=60, make_name=dep_zone)(qdataobjmeta))
qdataobjbymeta = with_irods_session( cache.memoize(timeout=120, make_name=dep_zone)(qdataobjbymeta))
qcolldataobjectpaths = with_irods_session( cache.memoize(timeout=120, make_name=dep_zone)(qcolldataobjectpaths))


#
qusermetaval = with_irods_session( qusermetaval )
qusermetadict = with_irods_session( qusermetadict )
qcollmetaval = with_irods_session( qcollmetaval )
qcollmetadict = with_irods_session( qcollmetadict )
qcollmetavals = with_irods_session( qcollmetavals )
qpathobjecttype = with_irods_session( qpathobjecttype )
qcollmetavals_with_placeholder = with_irods_session( qcollmetavals_with_placeholder )

@with_irods_session
def susermetaval(session, user, attr, value, unit=None):
    _susermetaval(session, user, attr, value, unit)
    cache.delete_memoized(qusermeta)

@with_irods_session
def scollmetaval(session, coll, attr, value, unit=None):
    _scollmetaval(session, coll, attr, value, unit)
    cache.delete_memoized(qcollmeta, coll)

@with_irods_session
def addcollmetaval(session, coll, attr, value, unit=None):
    _addcollmetaval(session, coll, attr, value, unit)
    cache.delete_memoized(qcollmeta, coll)

@with_irods_session
def rmallcollmetaattr(session, coll, attr):
    _rmallcollmetaattr(session, coll, attr)
    cache.delete_memoized(qcollmeta, coll)

@with_irods_session
def delcollmeta(session, coll, attr, value=None, unit=None):
    _delcollmeta(session, coll, attr, value, unit)
    cache.delete_memoized(qcollmeta, coll)

