# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from importlib import import_module

from flask_socketio import SocketIO # thêm để tương tác reverseShell
socketio = SocketIO(cors_allowed_origins="*")  # Cho phép mọi origin, có thể chỉnh lại cho bảo mật


db = SQLAlchemy()
login_manager = LoginManager()

def register_extensions(app):
    db.init_app(app)
    login_manager.init_app(app)

def register_blueprints(app):
    for module_name in ('authentication', 'home', 'dyn_dt', 'charts','reconna','targets','managershell','partial',):
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


    # Khởi tạo socketio với app
    socketio.init_app(app, cors_allowed_origins="*")
    
    # Đảm bảo shell_manager được khởi tạo với app instance
    from apps.managershell.pwncat import init_shell_manager
    shell_manager = init_shell_manager(app)
    shell_manager.socketio = socketio
    
    # Thêm shell_manager vào globals trước khi setup
    globals()['shell_manager'] = shell_manager
    
    # Setup shell_manager trong routes
    from apps.managershell.routes import setup_shell_manager
    setup_shell_manager()
    
    # Đăng ký các event cho terminal shell
    from apps.managershell.socketio_events import register_terminal_events
    register_terminal_events(socketio)

    return app

__all__ = ['db', 'login_manager', 'create_app', 'socketio', 'shell_manager']