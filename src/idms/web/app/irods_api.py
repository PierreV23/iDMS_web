"""API Functions accessing iRODS
"""
from flask import Blueprint, request
from flask_login import current_user
from irods.models import User, UserMeta
from irods.column import Criterion
from idms.common.irods.irods_sessions import irods_manager
from .utils.flaskcache import cache, key_zone

bp = Blueprint('irods_api', __name__, url_prefix='/irods_api')


@bp.route('/user_search', methods=['GET'])
@cache.cached(timeout=600, key_prefix=key_zone)
def usersearch():
    """Generate a list of irods users that contain query string q
    """

    def userrecord(user):
        return { 'account': user[User.name], 'label': f'{user[User.name]} ({user[UserMeta.value]})' }
    
    query = request.args.get('q', '').lower()
    
    if len(query) < 3:
        return []

    with irods_manager.session(current_user) as session:
        q = session.query(User, UserMeta, case_sensitive=False).filter(
            Criterion('like', User.name, f'%{query}%')
        ).filter(Criterion('=', UserMeta.name, 'sys::ad::displayName'))
        results_map = { u[User.name]: userrecord(u) for u in q }

        q = session.query(User, UserMeta, case_sensitive=False).filter(
            Criterion('like', UserMeta.value, f'%{query}%')
        ).filter(Criterion('=', UserMeta.name, 'sys::ad::displayName'))
        for u in q:
            results_map[u[User.name]] = userrecord(u)

        return list(results_map.values())
