#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov 12 14:33:10 2019

@author: wierinve
"""
import functools
import logging
import time

from datetime import timedelta
from flask import Blueprint, flash, render_template, redirect, request, url_for, current_app, jsonify
from flask_login import login_user, logout_user, current_user
from idms.web.app.utils.webuser import WebUser
from .. import messages

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route("/login", methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        requestdata = request.form.to_dict()
        user = WebUser.from_login(username=requestdata['username'],
                    password=requestdata['password'],
                    environment=requestdata['environment'])
        if not user.validate_irods_session():
            logging.info(f"User {user} failed to log in to {requestdata['environment']}")
            flash('Login to the web interface failed', 'login')
            return redirect(url_for("auth.login"))
        logging.info(f"User {user} logged in to {requestdata['environment']}")
        login_user(user, duration=timedelta(hours=24))
        user.store()
        user.settings['last_login'] = int(time.time())

        # Check for messages
        for message in messages.get_my_login_messages():
            flash(message, "news")
        return redirect(requestdata['next'])
    else:
        nexturl = request.args.get('next', default='/', type=str)
        return render_template('login.html', next=nexturl, envs=current_app.config["IRODS_ENVS"])


@bp.route('/logout')
def logout():
    if isinstance(current_user, WebUser):
        logging.info(f"User {current_user.username} logged out of {current_user.environment} environment")
        current_user.delete()
    # TODO Remie: remove iRODS sessions as well?
    logout_user()
    return redirect(url_for('auth.login'))

# This decorator can be used for API functions that require authentication
def auth_endpoint(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'msg': 'Authentication required'}), 401
        return func(*args, **kwargs)
    return wrapper
