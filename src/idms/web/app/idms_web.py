import logging
import logging.config
import atexit
import os
import redis
import secrets
from pathlib import Path
from flask import Flask, redirect, url_for, request
from flask_login import LoginManager
from flask_session import Session
from cachelib.file import FileSystemCache

from .components import contacts_manager, docviewer
from .utils import auth, cluster, flaskcache
from idms.web.app.utils.datafieldregistry import datafield_registry
from idms.web.app.utils.webuser import WebUser
import irods.exception
from Crypto.PublicKey import RSA
from idms.web.app.utils.webuser import AuthException

from . import collbrowser, routes, jobs, messages
from . import projects, admin, reports, userinfo, referencedatasets
from . import upload, search, metaedit, irods_api
from .utils.database import jobs_db, search_db
from idms.common.irods.irods_sessions import irods_manager
from idms.web.app.utils.encryption import generate_fernet_key_from_string
from .branding import init_branding, get_branding
from .plugin_manager import PluginManager
from .menu_manager import menu_manager
from .action_manager import action_manager
from idms.web.app.features import FEATURES
from idms.web.app.utils.workdir import init_workdir

# This is the default log config. It can (and should) be overruled by
# setting LOGCONFIG in config.py
DEFAULT_LOGCONFIG = {
    'version': 1,
    'formatters': {'default': {'format': '[%(asctime)s] %(levelname)s - %(module)s: %(message)s'}},
    'handlers': {'default': {'class': 'logging.StreamHandler', 'formatter': 'default'}},
    'root': {'level': 'DEBUG', 'handlers': ['default']}
}


logger = logging

def create_app():
    global logger

    instance_path = os.environ.get('FLASK_INSTANCE_PATH')

    # Initialize app
    app = Flask(__name__,
                instance_path=instance_path,
                instance_relative_config=True)

    # Load configuration
    app.config.from_pyfile('config.py', silent=False)

    # Initialize logging
    logconfig = app.config.get('LOGCONFIG', DEFAULT_LOGCONFIG)
    logconfig['disable_existing_loggers'] = False
    logging.config.dictConfig(logconfig)

    # Reinitialize global logger
    logger = logging.getLogger(__name__)
    logger.info('iDMS initializing ...')

    # Handle missing config values
    DEFAULT_CONFIG = {
        'SECRET_KEY': secrets.token_hex(32),
        'CACHE_TYPE': 'SimpleCache',
        'CACHE_DEFAULT_TIMEOUT': 300
    }
    for key, value in DEFAULT_CONFIG.items():
        if app.config.get(key) is None:
            logger.warning(f'{key} is not set in config.py. Using default value')
            app.config[key] = value

    # Setup session storage
    if app.config.get('CACHE_TYPE') == 'RedisCache':
        app.config['SESSION_TYPE'] = 'redis'
        hostname = app.config.get('CACHE_REDIS_HOST', 'localhost')
        app.config['SESSION_REDIS'] = redis.Redis.from_url(f'redis://{hostname}:6379')
        logger.info('Using REDIS session storage')
    else:
        app.config['SESSION_TYPE'] = 'cachelib'
        app.config['SESSION_CACHELIB'] = FileSystemCache(cache_dir='flask_session', threshold=500)
        logger.info('Using DISK session storage')

    flaskcache.init(app)

    Session(app)

    # Generate encryption key
    if app.config.get('SERVER_SIDE_ENCRYPTION', False):
        if app.config.get('SERVER_SIDE_ENCRYPTION_KEY') is None:
            raise ValueError("SERVER_SIDE_ENCRYPTION is enabled, but SERVER_SIDE_ENCRYPTION_KEY is not set")
        app.config['FERNET_KEY'] = generate_fernet_key_from_string(app.config.get('SERVER_SIDE_ENCRYPTION_KEY'))

    # Import datafields
    datafield_config = os.path.join(app.root_path, "config", "datafields.py")
    if os.path.exists(datafield_config):
        datafield_registry.load_known_attributes(datafield_config)

    # Import file mappings
    json_path = os.path.join(app.root_path, "config", "extensionmap.json")
    docviewer.doc_viewer_manager.load_mappings(json_path)

    # Import FEATURE dict
    json_path = os.path.join(app.root_path, "config", "features.json")
    FEATURES.load_features(json_path)

    json_path = os.path.join(app.root_path, "config", "actions.json")
    action_manager.load_from_json(json_path)

    # Load branding
    init_branding(app)
    init_workdir(app, ['svg'])

    app.register_blueprint(routes.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(collbrowser.bp)
    app.register_blueprint(jobs.bp)
    app.register_blueprint(docviewer.bp)
    app.register_blueprint(projects.bp)
    app.register_blueprint(referencedatasets.bp)
    app.register_blueprint(cluster.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(upload.bp)
    app.register_blueprint(userinfo.bp)
    app.register_blueprint(messages.bp)
    app.register_blueprint(search.bp)
    app.register_blueprint(metaedit.bp)
    app.register_blueprint(contacts_manager.bp)
    app.register_blueprint(irods_api.bp)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    # Initialize MenuManager
    json_path = os.path.join(app.root_path, "config", "menu.json")
    menu_manager.load_from_json(json_path)


    app.plugin_manager = PluginManager(
        app,
        datafield_registry=datafield_registry,
        menu_manager=menu_manager,
        doc_viewer_manager=docviewer.doc_viewer_manager,
        action_manager=action_manager
    )
    if not app.config.get('DISABLE_PLUGINS', False):
        app.plugin_manager.load_plugins()

    # When running under uwsgi, the postfork decorator is required
    # for the database connections
    try:
        from uwsgidecorators import postfork
        @postfork
        def init_dbs_wrapper():
            init_dbs(app)
    except ModuleNotFoundError:
        init_dbs( app )

    atexit.register(close_dbs)

    errorhandlers(app)

    @login_manager.user_loader
    def load_user(userid):
        return WebUser.retrieve(userid)

    @app.context_processor
    def inject_menu():
        return dict(sidebar_menu=menu_manager.get_visible_menu)

    @app.context_processor
    def inject_branding():
        return dict(branding=get_branding(app))

    @app.context_processor
    def inject_header_message():
        header_messages = messages.load_messages(category='banner', only_current=True)
        return dict(header_messages=header_messages)

    logger.info('iDMS initialized')

    return app

def errorhandlers(app):
    @app.errorhandler(irods.exception.PAM_AUTH_PASSWORD_FAILED)
    def invalid_session0(e):
        """Session may be stale. Destroy it and redirect to login page."""
        logging.info("Invalid session")
        return auth.logout()

    @app.errorhandler(irods.exception.CAT_INVALID_AUTHENTICATION)
    def invalid_session1(e):
        """Session may be stale. Destroy it and redirect to login page."""
        logging.info("Invalid session")
        return auth.logout()

    @app.errorhandler(AuthException)
    def auth_failed(e):
        """Destroy session and redirect to login page."""
        logging.info("Auth Exception")
        return redirect(url_for('auth.login', next=request.full_path))

    @app.errorhandler(AttributeError)
    def handle_attribute_error(e):
        """Destroy session and redirect to login page."""
        logging.exception(f"AttributeError: {e}")
        return redirect(url_for('auth.login', next=request.full_path))

    @app.errorhandler(irods.exception.CAT_INVALID_USER)
    def invalid_user(e):
        """Connection to iRODS failing. Redirect to login page"""
        logging.info("Invalid user")
        return auth.logout()

def is_uwsgi_master():
    try:
        import uwsgi
        # Check if running in the master process
        return uwsgi.worker_id() == 0
    except ModuleNotFoundError:
        return False


def init_dbs(app):
    jobs_db.init_app(app)
    search_db.init_app(app)
    irods_manager.init_app(app.config.get('IRODS_ENVS', {}),
                            app.config.get('conn_refresh_time', 120),
                            background_cleanup=not is_uwsgi_master())
    if not app.config.get('DISABLE_PLUGINS', False):
        for f in app.plugin_manager.postfork_functions:
            logging.info(f'Running plugin postfork function {f.__qualname__}')
            f(app)

def close_dbs():
    logging.debug('Closing dbs ...')
    irods_manager.close()
