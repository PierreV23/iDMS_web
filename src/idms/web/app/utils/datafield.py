#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 10 15:22:06 2020

@author: wierinve


Defines basic datafield classes for the idms web application

"""

import math
import os
import re
from datetime import datetime, timedelta, timezone
from flask import url_for
from irods.models import Collection
from idms.web.app.utils.datafieldregistry import datafield_registry as dfr, Datafield
from . import cached_iqry

class Datatypes:
    BASE = 'base'
    INT = 'int'
    BYTES = 'bytes'
    BOOLEAN = 'boolean'
    TEXT = 'text'
    TIMEDELTA = 'timedelta'
    TIMESTAMP = 'timestamp'
    IRODS_COLLECTION = 'irods_collection'
    COLLECTION_ID = 'collection_id'
    RUNSHEET = 'runsheet'
    IRODS_OBJECT = 'irods_object'
    IRODS_USER = 'irods_user'
    IRODS_GROUP = 'irods_group'
    PROJECTID = 'projectid'
    PROCESS = 'process'
    PROCESSGROUPGUID = 'processgroupguid'
    URL = 'url'
    

# Some functions for backward compatability

MAXLEN = 45

def AVU2data(attr, value, unit):
    return dfr.create(attr, value, unit)

def datafield(name, value, datatype):
    return dfr.create(name, value, datatype)

# Classes
@dfr.register_type(Datatypes.BASE)
class data_base(Datafield):

    def __init__(self, name, value, datatype=None):
        self.name = name
        self.value = value
        self.datatype = datatype

    @property
    def url(self):
        return ''

    @property
    def htmlshort(self):
        return self.htmlstring
    
    def htmlshort2(self, classes="", maxlen=MAXLEN):
        l = len(self.value)
        if l>maxlen:
            txt = self.value[l-maxlen:]
        else:
            txt = self.value
        return f'<div class="{classes}">{txt}</div>'

    @property
    def htmlstring(self):
        return str(self.value)

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return f'{self.name} = {self.value} {self.datatype}'

@dfr.register_type(Datatypes.INT)
class data_int(data_base):
    def __init__(self, name, value, datatype=None):
        if str(value).isnumeric():
            super().__init__(name, int(value), datatype)
            self.nan = False
        else:
            self.nan = True

    def __str__(self):
        return str(self.value)

    def __int__(self):
        return self.value

    def __lt__(self, other):
        return self.value < other.value

@dfr.register_type(Datatypes.TEXT)
class data_text(data_base):
    pass

@dfr.register_type(Datatypes.BYTES)
class data_bytes(data_int):
    def _formatted(self):
        labels = ['B', 'kB', 'Mb', 'GB', 'TB', 'PB', 'EB']
        bytes = int(self)
        if bytes == 0:
            return('0')
        g = math.log10(bytes)//3
        return '{0:.2f} {1}'.format(bytes/(1e3**g), labels[int(g)])

    @property
    def htmlstring(self):
        return str(self)

    def __str__(self):
        return self._formatted()

@dfr.register_type(Datatypes.BOOLEAN)
class data_boolean(data_base):

    def __eq__(self, other):
        if type(other) == bool:
            return self.value == other
        return self == other

    def __str__(self):
        return 'TRUE' if self.value else 'FALSE'

    @property
    def htmlstring(self):
        return str(self.value)

@dfr.register_type(Datatypes.TIMEDELTA)
class data_timedelta(data_base):

    def __str__(self):
        if self.value.isnumeric():
            return str(timedelta(seconds=int(self.value)))
        else:
            return self.value

    @property
    def htmlstring(self):
        return str(self)

@dfr.register_type(Datatypes.TIMESTAMP)
class data_timestamp(data_base):
    def __init__(self, name, value, datatype=None):
        if type(value) in (int, float):
            myvalue = float(value)
        elif type(value) == str:
            try:
                myvalue = float(value)
            except ValueError:
                raise ValueError(f'String {value} cannot be converted to timestamp')
        elif isinstance(value, datetime):
            # Assuming this is an irods timestamp, it will be local time without tz info
            myvalue = datetime.timestamp(value.replace(tzinfo=timezone.utc))
        else:
            raise ValueError(f'Data type {type(value)} cannot be converted to timestamp')
        self._formatted_date = datetime.fromtimestamp(myvalue).strftime("%d-%m-%Y %H:%M:%S")
        super().__init__(name, myvalue, datatype)

    def __str__(self):
        return self._formatted_date

    def __int__(self):
        return int(self.value)

    @property
    def htmlstring(self):
        return self.__str__()

    def __lt__(self, other):
        return self.value < other.value

    def __eq__(self, other):
        return self.value == other.value

@dfr.register_type(Datatypes.IRODS_COLLECTION)
class data_irods_collection(data_base):

    def displaystring(self, maxlen=999):
        if not self.value:
            return ""
        nameparts = self.value.split('/')
        shortname = nameparts[-1]
        prefix = '/{}'.format('/'.join(nameparts[1:-1]))
        if len(self.value) > maxlen:
            # LINE TOO LONG
            prefixlen = max(1, maxlen - len(shortname) - 2)
            prefix = '..' + prefix[-prefixlen:]
        if prefix == '/':
            return '/{}'.format(shortname)
        else:
            return '{}/{}'.format(prefix, shortname)

    @property
    def basename(self):
        return os.path.basename(self.value)

    @property
    def htmlstring(self):
        displaystring = self.displaystring()
        return '<a href="{0}?path={1}">{2}</a>'.format(
            url_for('collbrowser.collbrowser'), self.value, displaystring)

    @property
    def htmlshort(self):
        displaystring = self.displaystring(maxlen=MAXLEN)
        return '<div class="container"><a href="{0}?path={1}" data-toggle="tooltip" title="{1}">{2}</a></div>'.format(format(url_for('collbrowser.collbrowser')), self.value, displaystring)
    
    def htmlshort2(self, classes="", maxlen=MAXLEN):
        class_string = f'class="{classes}"' if classes else ""
        return '<div class="container"><a href="{0}?path={1}" data-toggle="tooltip" title="{1}"><span {3}>{2}</span></a></div>'.format(format(url_for('collbrowser.collbrowser')), self.value, self.basename, class_string)
    
    @property
    def collentry(self):
        return f'<span class="path-change" data-path="{self.value}">{self.basename}</span>'

    def __lt__(self, other):
        return self.value < other.value

@dfr.register_type(Datatypes.COLLECTION_ID)
class data_collection_id(data_base):
    def __init__(self, name, value, datatype=None):
        self._ref_col = None
        self._searched_for_ref_col = False
        super().__init__(name, value, datatype)

    @property
    def ref_col(self):
        if self._searched_for_ref_col:
            return self._ref_col
        query = cached_iqry.qcollbymeta('sys::dataset_id', self.value)
        for coll in query:
            self._ref_col = coll[Collection.name]
        self._searched_for_ref_col = True
        return self._ref_col

    @property
    def htmlstring(self):
        if self.ref_col is None:
            return self.value
        return '<a href="{0}?path={1}">{1}</a>'.format(
            url_for('collbrowser.collbrowser'), self.ref_col)

@dfr.register_type(Datatypes.RUNSHEET)
class data_runsheet(data_base):

    @property
    def htmlshort(self):
        display_runsheet_id = re.sub('-runsheet.yaml', '', self.value)[:8]
        return '<a href="{0}" data-toggle="tooltip" title="{1}">{2}</a>'.format(self.url, self.value, display_runsheet_id)

    @property
    def htmlstring(self):
        return '<a href="{0}" data-toggle="tooltip" title="{1}">{1}</a>'.format(self.url, self.value)

    @property
    def url(self):
        return f'{url_for("jobs.jobdetails")}?name={self.value}'

    def __str__(self):
        return str(self.value)

    def __lt__(self, other):
        return self.value < other.value

@dfr.register_type(Datatypes.IRODS_OBJECT)
class data_irods_object(data_base):

    @property
    def htmlstring(self):
        shortname = self.value.split('/')[-1]
        return '<a href="#" onClick="showModal(\'{0}\', \'{1}\')">{1}</a>'.format(self.value, shortname)

    def __lt__(self, other):
        return self.value < other.value

@dfr.register_type(Datatypes.IRODS_USER)
class data_irods_user(data_base):
    pass


@dfr.register_type(Datatypes.IRODS_GROUP)
class data_irods_group(data_base):
        
    @property
    def htmlstring(self):
        return '<a href="{0}">{1}</a>'.format(url_for('userinfo.groupdetails', group=self.value), self.value)

@dfr.register_type(Datatypes.PROJECTID)
class data_projectid(data_base):

    @property
    def htmlstring(self):
        return '<a href="{0}">{1}</a>'.format(url_for('projects.show_projects', project=self.value), self.value)

@dfr.register_type(Datatypes.PROCESS)
class data_process(data_base):

    @property
    def htmlstring(self):
        return '<a href="{0}">{1}</a>'.format(url_for('projects.show_projects', page='processes', process=self.value), self.value)

@dfr.register_type(Datatypes.PROCESSGROUPGUID)
class data_processgroupguid(data_base):

    @property
    def htmlstring(self):
        return '<a href={0}?processgroupguid={1}>{1}</a>'.format(url_for('jobs.jobdetails'), self.value)

    @property
    def htmlshort(self):
        return '<a href={0}?processgroupguid={1} data-toggle="tooltip" title="{1}">{2}</a>'.format(url_for('jobs.jobdetails'), self.value, self.value[:8])

@dfr.register_type(Datatypes.URL)
class data_url(data_base):

    @property
    def htmlstring(self):
        return '<a href="{0}">{0}</a>'.format(self.value)
