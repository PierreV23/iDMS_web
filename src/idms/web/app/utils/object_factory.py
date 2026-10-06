#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 20 11:09:54 2020

@author: wierinve
"""


class ObjectFactory:
    """
    Standard objectfactory class
    """
    def __init__(self):
        self._builders = {}
        self._defaultbuilder = None

    def register_default_builder(self, builder):
        self._defaultbuilder = builder

    def register_builder(self, key, builder):
        self._builders[key] = builder

    def create(self, key, **kwargs):
        if key in self._builders:
            builder = self._builders[key]
        else:
            builder = self._defaultbuilder
        if builder is None:
            raise ValueError(key)
        return builder(**kwargs)
