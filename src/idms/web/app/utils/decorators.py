
from functools import wraps
from flask_login import current_user
from idms.common.irods.irods_sessions import irods_manager


def with_irods_session(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Any function decorated like this will get the irods_session of the current user as first argument
            with irods_manager.session(current_user) as session:
                return f(session, *args, **kwargs)
        return decorated
    