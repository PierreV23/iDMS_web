"""
Created on Tue Nov 12 16:39:47 2019

@author: wierinve
"""

import json
import logging

from flask_login import UserMixin
from flask import session, current_app
from flask_login import current_user
from irods.models import User, Group, UserMeta
from irods.column import Criterion
from . import flaskcache
from . import cached_iqry

from idms.common.irods.irods_sessions import irods_manager, create_session
from idms.web.app.utils.iconnect import Connection2
from idms.web.app.utils.encryption import encrypt, decrypt
from idms.web.app.features import FEATURES

ATTR_DISPLAYNAME = 'sys::ad::displayName'

logger = logging.getLogger(__name__)

class AuthException(Exception):
    pass

class IRSettings:
    def __init__(self, user, prefix=''):
        self.user = user
        self.prefix = prefix

    def __getitem__(self, key):
        val = cached_iqry.qcollmetaval(f'/{current_user.irods_zone}/home/{current_user.username}', f'{self.prefix}{key}')
        if val is None:
            raise KeyError
        return json.loads(val)

    def __setitem__(self, key, value):
        cached_iqry.scollmetaval(f'/{current_user.irods_zone}/home/{current_user.username}', f'{self.prefix}{key}', json.dumps(value))

    def get(self, key, default=None):
        try:
            value = self[key]
        except KeyError:
            value = default
        return value
    
    def delete(self, key):
        attr = f'{self.prefix}{key}'
        cached_iqry.rmallcollmetaattr(f'/{current_user.irods_zone}/home/{current_user.username}', attr)

    def items(self):
        meta = cached_iqry.qcollmetadict(f'/{current_user.irods_zone}/home/{current_user.username}')
        keys = [ k[len(self.prefix):] for k in meta if k.startswith(self.prefix) ]
        return [ (k, self[k]) for k in keys ]

    def setdefault(self, key, default):
        try:
            value = self[key]
        except KeyError:
            self[key] = default
        return self[key]

class WebUser(UserMixin):

    def __init__(self, username=None, environment=None, encrypted_password="", encrypted_native_password=None,
                 is_authenticated=None, is_admin=None, fullname=None, **kwargs):
        """WebUser application user instance

        These args are required.
            username (_type_, optional): _description_. Defaults to None.
            environment (_type_, optional): _description_. Defaults to None.
            password (str, optional): _description_. Defaults to "".

        These args can be supplied to speed up the user creation, but they are optional.
            native_password (_type_, optional): _description_. Defaults to None.
            is_authenticated (bool, optional): _description_. Defaults to False.
            is_admin (bool, optional): _description_. Defaults to False.
            fullname (_type_, optional): _description_. Defaults to None.
        """
        self.username = username
        self.environment = environment
        self._encrypted_password = encrypted_password
        self._encrypted_native_password = encrypted_native_password
        self._is_authenticated = is_authenticated
        self._is_admin = is_admin
        self._fullname = fullname

        self._irods_env = {}

        self.settings = IRSettings(self.username, prefix='ngsweb::')

    @classmethod
    def from_login(cls, username=None, password=None, environment=None):
        return cls(username=username, encrypted_password=encrypt(password), environment=environment)

    def __repr__(self):
        return f'WebUser({self.username})'

# iRODS session properties
    @property
    def irods_env(self):
        return current_app.config["IRODS_ENVS"].get(self.environment, None)

    @property
    def irods_server(self):
        return self.irods_env.get('host')

    @property
    def irods_zone(self):
        return self.irods_env.get('zone')

    @property
    def refdata_coll(self):
        return self.irods_env.get('refdata_collection', None)

    @flaskcache.cache.memoize(timeout=5, make_name=flaskcache.dep_userzone)
    def feature(self, name):
        default = FEATURES.get(name, (None, 'false'))[1]
        return self.settings.get(f'feature::{name}', default) == 'true'

    @property
    def minilims_db(self):
        self.minilims_db = self.irods_env.get('minilims_db', 'sqlite://')

# Authentication properties

    @property
    def is_authenticated(self):
        if self._is_authenticated is None:
            self.validate_irods_session()
        return self._is_authenticated

    @property
    def password(self):
        return decrypt(self._encrypted_password)

    @property
    def native_password(self):
        if self._encrypted_native_password is None:
            return decrypt(self._encrypted_password)
        return decrypt(self._encrypted_native_password)

    @property
    def is_admin(self):
        if self._is_admin is None:
            self._is_admin = False
            if self._is_authenticated:
                try:
                    with irods_manager.session(current_user) as session:
                        user = session.users.get(self.username)
                        self._is_admin = user.type == 'rodsadmin'
                except:
                    self._is_admin = None
                    return False
        return self._is_admin

    @flaskcache.cache.memoize(timeout=3600, make_name=flaskcache.dep_userzone)
    def groups(self):
        with irods_manager.session(current_user) as session:
            q = session.query(Group).filter( User.name == self.username )
            result = [ r[Group.name] for r in q ]
        return result

    @flaskcache.cache.memoize(timeout=3600, make_name=flaskcache.dep_userzone)
    def projects(self):
        with irods_manager.session(current_user) as session:
            q = session.query(Group.name, UserMeta.value).filter(\
                Criterion('=', UserMeta.name, 'projectID'))
            grps = self.groups()
            usr_groups = [ r for r in q if r[Group.name] in grps ]

            my_projects = list(set([ r[UserMeta.value] for r in usr_groups ]))

        return my_projects

    @property
    def fullname(self):
        if self._fullname is None or self._fullname == self.username:
            self._fullname = cached_iqry.qusermetaval(self.username, ATTR_DISPLAYNAME, self.username)
        return self._fullname

    def store(self):
        """Store user in Flask session."""
        if 'user_data' not in session:
            session['user_data'] = {}
        info = {
            'username': self.username,
            'environment': self.environment,
            'encrypted_password': self._encrypted_password,
            'encrypted_native_password': self._encrypted_native_password,
            'is_authenticated': self.is_authenticated,
            'is_admin': self.is_admin,
            'fullname': self.fullname
        }
        session['user_data'][self.username] = info

    @classmethod
    def retrieve(cls, username):
        """Retrieve previously stored user from Flask session."""
        if 'user_data' in session and username in session['user_data']:
            try:
                user = cls(**session['user_data'][username])
            except:
                return None
            if user.is_authenticated:
                return user
            else:
                return None
        return None

    def delete(self):
        """Delete user from Flask session."""
        if 'user_data' in session:
            del session['user_data']
        irods_manager.remove(self)


    def validate_irods_session(self):
        logger.debug(f'Validate session for user {self.username}')
        try:
            # we cannot use the session in the sessionmanager, as it is identified by the username only
            # to check the credentials, we need to make a new session with the password of this webuser.

            # Create iRODS session and verify if root collection can be retrieved
            env_config = current_app.config["IRODS_ENVS"].get(self.environment, None) or {}
            scheme = env_config.get("authentication_scheme", "pam_password")
            use_pam = scheme == "pam_password"
            check_pw_session = create_session(env_config, self, use_pam=use_pam)
            if use_pam:
                # Get the temporary password from our custom Connection class
                conn = Connection2(check_pw_session.pool, check_pw_session.pool.account)
                # Store the temporary password
                self._encrypted_native_password = encrypt(conn.native_password)
            else:
                # native password is the credential. touch home path to verify authentication
                check_pw_session.collections.get(f"/{env_config.get('zone')}/home/{self.username}")
                self._encrypted_native_password = None
            self._is_authenticated = True
            check_pw_session.cleanup()
            # Remove old sessions
            irods_manager.remove(self)
            return True
        except Exception as e:
            logging.exception(f"Authentication (session validation) failed for user {self.username} on {self.environment}")
            irods_manager.remove(self)
        return False


    def get_id(self):
        return self.username
