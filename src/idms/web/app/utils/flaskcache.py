
import logging
from flask import request
from flask_caching import Cache
from flask_login import current_user

cache = Cache()
logger = logging.getLogger(__name__)

def configure_cache(app):
    if app.config.get('CACHE_TYPE') == "RedisCache":
        # Try to initialize REDIS Cache
        # if it fails, fall back to SimpleCache
        try:
            redis_host = app.config.get('CACHE_REDIS_HOST', '')
            import redis
            redis_test = redis.Redis('redis')
            redis_test.set('test', 'value')
            logger.info(f'Use REDIS on host {redis_host}')
        except:
            app.config['CACHE_TYPE'] = "SimpleCache"
            logger.info('Use Simple Cache')
    else:
        logger.info(f'Cache type is {app.config.get("CACHE_TYPE")}')

def init(app):
#    global cache
    configure_cache(app)
    cache.init_app(app)

def dep_zone(funcname):
    if hasattr(current_user, 'irods_zone'):
        return f'{current_user.irods_zone}{funcname}'
    else:
        return funcname

def dep_userzone(funcname):
    return f'{current_user.username}{current_user.irods_zone}{funcname}'

def key_zone():
    return f'{current_user.irods_zone}{request.full_path}'

def key_userzone():
    return f'{current_user.username}{current_user.irods_zone}{request.full_path}'

def cache_report(prefix=''):
    print('############### CACHE #######################')
    if hasattr(cache, 'key_prefix'):
        k_prefix = cache.cache.key_prefix
    else:
        k_prefix = ""
    keys = cache.cache._write_client.keys(k_prefix + '*')
    keys = [k.decode('utf8') for k in keys]
    keys = [k.replace(k_prefix, '') for k in keys]
    values = cache.get_many(*keys)
    for key in keys:
        if key.startswith(prefix):
            print(f'{key:30} -> {str(cache.get(key))}' )