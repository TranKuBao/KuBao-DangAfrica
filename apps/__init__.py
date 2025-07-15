# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from importlib import import_module

db = SQLAlchemy()
login_manager = LoginManager()

def register_extensions(app):
    db.init_app(app)
    login_manager.init_app(app)

def register_blueprints(app):
    for module_name in ('authentication', 'home', 'dyn_dt', 'charts','reconna','targets','managershell',):
        module = import_module('apps.{}.routes'.format(module_name))
        app.register_blueprint(module.blueprint)

from apps.authentication.oauth import github_blueprint, google_blueprint

def create_app(config):

    # Contextual
    basedir = os.path.abspath(os.path.dirname(__file__))  # apps/
    project_root = os.path.abspath(os.path.join(basedir, '..'))  # ← flask-soft-ui-dashboard-master

    TEMPLATES_FOLDER = os.path.join(project_root, 'templates')
    STATIC_FOLDER = os.path.join(project_root, 'static')

    print(' > TEMPLATES_FOLDER: ' + TEMPLATES_FOLDER)
    print(' > STATIC_FOLDER:    ' + STATIC_FOLDER)

    app = Flask(__name__, static_url_path='/static', template_folder=TEMPLATES_FOLDER, static_folder=STATIC_FOLDER)

    UPLOAD_FOLDER = str(os.path.abspath(os.path.join(__file__, '..', '..', 'pocsuite3', 'pocs')))
    CHECK_FOLDER = str(os.path.abspath(os.path.join(__file__, '..', 'checkversionplatform')))
    REPORT_FOLDER = str(os.path.abspath(os.path.join(__file__, '..', '..', 'reports')))
    POCSUITE3_FOLDER = str(os.path.abspath(os.path.join(__file__, '..', '..', 'pocsuite3')))

    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['CHECK_FOLDER'] = CHECK_FOLDER # folder rỗng để check thôi
    app.config['REPORT_FOLDER'] = REPORT_FOLDER
    app.config['POCSUITE3_FOLDER'] = POCSUITE3_FOLDER
    print(' > UPLOAD_FOLDER: ' + UPLOAD_FOLDER)
    print(' > CHECK_FOLDER:    ' + CHECK_FOLDER)
    print(' > REPORT_FOLDER: ' + REPORT_FOLDER)
    print(' > POCSUITE3_FOLDER:    ' + POCSUITE3_FOLDER)
    
    app.config.from_object(config)
    register_extensions(app)
    register_blueprints(app)
    app.register_blueprint(github_blueprint, url_prefix="/login")    
    app.register_blueprint(google_blueprint, url_prefix="/login")    
    return app
