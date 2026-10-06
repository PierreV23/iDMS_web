#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May  7 11:51:05 2019

@author: Erwin van Wieringen
"""

import base64
import yaml
import time
import socket
import sys

def error(msg):
    print("%s : %s" % (sys.argv[0], msg))
    exit(2)

def decode_pw(enc_pw):
    return base64.b64decode(enc_pw).decode('ascii')

def uxtowin(path):
    return '\\'.join(path.split('/'))

def wintoux(path):
    return '/'.join(path.split('\\'))

def uncsplit(unc):
    """
    Split UNC path in server, service, path components
    """
    split_unc = unc.split('\\')
    if len(split_unc) < 4 or split_unc[1] != '':
        error("UNC path format error: %s" % unc)
    server = split_unc[2]
    nbserver = server.split('.')[0].upper()
    service = split_unc[3]
    path = '/'.join(split_unc[4:])
    return server, service, path, nbserver

def utc2local(utc):
    return time.mktime(time.localtime(utc))

def read_credfile(filename):
    with open(filename) as credfile:
        y_creds = yaml.load(credfile, Loader=yaml.Loader)
    return y_creds['user'], y_creds['password'], y_creds['domain']

def myshortname():
    return socket.gethostname().split('.')[0]
