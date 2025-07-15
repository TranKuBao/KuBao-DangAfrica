# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import datetime as dt
from apps.managershell import blueprint
from apps import db
from apps.models import Targets, Incidents, Credentials, VulInTarget, Collections, CollectedFiles, VerificationResults
from apps.authentication.models import Users
from jinja2 import TemplateNotFound
from flask_wtf import FlaskForm
from flask_login import login_required, current_user
from flask import render_template, request, redirect, url_for, jsonify, session

from lib.server.server import Server
from lib import database, const





#bắt đầu code từ đây
@blueprint.route('/shell')
def targets():
    return jsonify({'status':0, 'code':"Tesst shell completed"})
