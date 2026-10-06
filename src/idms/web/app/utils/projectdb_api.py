#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov 19 09:05:26 2019

@author: wierinve
"""

import requests
from requests.auth import HTTPBasicAuth
from flask import current_app
from flask_login import current_user
from .flaskcache import cache
from dateutil import parser as dateparser

REQUESTS_METHODS = {
    'GET':   requests.get,
    'PUT':   requests.put,
    'POST':  requests.post,
    'DELETE':requests.delete,
    'PATCH': requests.patch
}

EPOCH = '1970-01-01T01:00:00'

def iso2dt(timestr):
    """Convert ISO8601 datetime string to datetime

    Args:
        timestr (str): ISO8601 datetime string
    """
    if timestr is None:
        timestr = EPOCH
    return dateparser.parse(timestr)

def search(l, f, v):
    """Find an item x in a list l of objects
    where f(x) = v
    """
    matches = [ x for x in l if f(x) == v ]
    if not matches:
        matches = None
    return matches

# @cache.memoize(timeout=30, make_name=dep_userzone)
def rest_call(request_type, endpoint, data={}, hostname=None, user=None, passwd=None, prefix='/api/1.0'):
    if hostname is None:
        if (hostname := current_app.config.get('API_HOST')) is None:
            hostname = current_user.irods_server
    url = 'http://{}{}/{}'.format(hostname, prefix, endpoint)
    username = current_user.username if user is None else user
    password = current_user.password if passwd is None else passwd
    auth = HTTPBasicAuth(username, password)
    return_data = {}
    if request_type in REQUESTS_METHODS:
        response = REQUESTS_METHODS[request_type](url, auth=auth, json=data)
    try:
        return_data = response.json()
    except:
        return_data = {}
    if request_type != 'GET':
        cache.delete_memoized(rest_call)
    return return_data, response.status_code

def add_checkbox(data, attr, name, negate=False, key=None):
    set_value = 0 if negate else 1
    datakey = key if key else name
    if name in attr:
        data[datakey] = set_value
    else:
        data[datakey] = 1 - set_value
    return data