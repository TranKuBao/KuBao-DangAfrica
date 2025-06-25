# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
import wtforms
from apps.home import blueprint
from apps import db
from apps.models import Targets
from apps.authentication.models import Users
from jinja2 import TemplateNotFound
from flask_wtf import FlaskForm
from flask_login import login_required, current_user
from flask import render_template, request, redirect, url_for, jsonify, session

from lib.server.server import Server
from lib import database, const

import os
from os import urandom,path as ospath,remove as osremove

import subprocess
import re
import sys,types



##IMPORTING POCSUITE3
from pocsuite3.lib.core.data import kb,conf
lib_path = ospath.abspath(ospath.join('pocsuite3'))
# thêm thư mục cần load vào trong hệ thống
sys.path.append(lib_path)
try:
    import pocsuite3
except ImportError:
    sys.path.append(ospath.abspath(ospath.join(ospath.dirname(__file__), ospath.pardir)))
from pocsuite3.cli import check_environment, module_path
from pocsuite3 import set_paths
from pocsuite3.lib.core.interpreter import PocsuiteInterpreter
from pocsuite3.lib.core.option import init_options, _cleanup_options
# from pocsuite3.modules.listener.reverse_tcp import  WebServer
#Running Poc_core
check_environment()
set_paths(module_path())
init_options()
poc_core = PocsuiteInterpreter()
## Ending IMPORTING POCSUITE#
server = Server()
db = database.Database()

UPLOAD_FOLDER = str(os.path.abspath(os.path.join(__file__, '..', 'pocsuite3', 'pocs')))
CHECK_FOLDER = str(os.path.abspath(os.path.join(__file__, '..', 'checkversionplatform')))
REPORT_FOLDER = str(os.path.abspath(os.path.join(__file__, '..', 'reports')))
POCSUITE3_FOLDER = str(os.path.abspath(os.path.join(__file__, '..', 'pocsuite3')))






#bắt đầu code từ đây
@blueprint.route('/targets')
def targets():
    return render_template('targets/index-targets.html', segment='index_targets')

#lấy và search ở hàm này
@blueprint.route('/api/targets', methods=['GET'])
def get_all_targets():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '', type=str).strip()
    per_page = 6
    print(f"[x] page: {page} & search_querry={search_query}")
    targets_paginated, total_pages = Targets.search(search_query, page, per_page)

    html = render_template('partials/partial_list_targets.html', targets=targets_paginated, loader=0)

    return jsonify({
        'html': html,
        'total_pages': total_pages
    })

@blueprint.route('/api/add_targets', methods=['POST'])
def add_targets():
    """API để thêm một target mới"""
    try:
        # Get JSON data from request
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No input data provided'}), 400

        # Trích xuất và xử lý dữ liệu từ client
        new_target = Targets.create_target(
            hostname=data.get('Hostname'),
            ip_address=data.get('Ip_address'),
            server_type=data.get('Server_type'),
            os=data.get('Operating_system'),
            location=data.get('Location'),
            status=data.get('Status'),
            privilege_escalation=data.get('Privilege_escalation') == 'true',  # chuyển thành bool
            exploitation_level=data.get('Exploitation_level'),
            incident_id=data.get('Id_vul_in_target'),
            notes=data.get('Notes')
        )
        #print(new_target)
        return jsonify({
            'message': 'Target added successfully',
            'target_id': new_target.server_id
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Server error', 'details': str(e)}), 500

#xem thông tin của 1 target
@blueprint.route('/view-target', methods=['GET'])
def view_target():
    #lấy thông tin của CSDL
    #lấy thông tin CVE lấy được
    #lấy thông tin về trình sát
    
    list_poc=["Trần Ku em", "Hello Các em", "Nguyễn Mlem Kem"]
    return render_template('targets/view-target.html', segment='view_target',list_poc=list_poc)

#Tương tác terminal của 1 target thông qua 1 POC
@blueprint.route('/run-cmd',methods=['POST'])
def run_cmd():
    data = request.get_json()
    cmd = data.get("command", "")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        output = result.stdout if result.stdout else result.stderr or "Thành công nhưng không có đầu ra."
    except Exception as e:
        output = str(e)
    return jsonify({"output": output})




#POCs
@blueprint.route('/pocs')
def pocs():
    return render_template('pocs/index-pocs.html', segment='index-pocs')

def matches_search_poc(poc, keyword):
    keyword = keyword.lower()
    return any([
        keyword in (poc.get("name") or "").lower(),
        keyword in (poc.get("appname") or "").lower(),
        keyword in (poc.get("appversion") or "").lower(),
        keyword in (poc.get("vulType") or "").lower(),
        keyword in (poc.get("author") or "").lower(),
        keyword in (poc.get("references") or "").lower()
    ])

#lấy dữ liệu để hiện thị list POCs
@blueprint.route('/api/fetch-pocs', methods=['GET'])
def fetch_pocs():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('limit', 10))
    keyword = request.args.get('search', '').strip().lower()

    listModules = poc_core.get_all_modules()
    allPocs = []
    count = 0
    for module in listModules:
        count += 1
        oneRow = {
            "id": str(count),
            "appversion": module["appversion"],
            "name": module["name"],
            "appname": module["appname"],
            "path": module["path"],
            "author": module["author"],
            "references": module["references"],
            "vulType": module["vulType"]
        }
        allPocs.append(oneRow)

    # ✳️ Lọc theo từ khóa nếu có
    if keyword:
        allPocs = [poc for poc in allPocs if matches_search_poc(poc, keyword)]

    total_items = len(allPocs)
    total_pages = max((total_items + per_page - 1) // per_page, 1)

    # Cắt theo trang
    start = (page - 1) * per_page
    end = start + per_page
    current_pocs = allPocs[start:end]

    html = render_template("pocs/partial-list-pocs.html", pocs=current_pocs)

    return jsonify({
        'html': html,
        'total_pages': total_pages,
        'current_page': page
    })

# xem thông tin của `1 poc
@blueprint.route('/view-poc', methods = ['GET'])
def poc():
    poc_path=request.args.get('poc_path')
    return render_template('poc/view-poc.html', segment='view_poc', poc_path=poc_path)

@blueprint.route('/get-poc-info', methods = ['POST'])
def get_poc_info():
    if not 'poc_path' in request.form:
        return jsonify({'status': -1, 'msg': 'poc-path is required'})

    poc_path = request.form['poc_path']
    if not ('pocs' in poc_path):
        poc_path = os.path.join('pocs', poc_path)
    try:
        poc_core.command_use(poc_path)
    except:
        return jsonify({'status': -1, 'msg': 'No poc is available by that poc-path'})
    if not poc_core.current_module:
        return jsonify({'status': -1, 'msg': 'No poc is available by that poc-path'})
    modeString = ''
    if hasattr(poc_core.current_module, '_shell'):
        modeString +=  'shell '
    if hasattr(poc_core.current_module, '_verify'):
        modeString +=  'verify '
    if hasattr(poc_core.current_module, '_attack'):
        modeString +=  'attack '
    currentPoC = poc_core.current_module

    isServerOnline = []
    if(server.is_active):
        isServerOnline = [session['ip'],session['port']]
    data = {
        'info': get_info_poc_as_dict(),
        'modes':modeString,
        'global_options': get_detail_options(currentPoC.global_options),
        'payload_options': get_detail_options(currentPoC.payload_options),
        'poc-path':poc_path,
        'isServerOnline':isServerOnline
    }
    if(hasattr(currentPoC,'options')):
        data['options'] =  get_detail_options(currentPoC.options)
    #print(data)
    return jsonify({'status': 0, 'data': data})

def get_info_poc_as_dict():
    if not poc_core.current_module:
        return {}
    fields = ["name", "VulID", "version", "author", "vulDate", "createDate", "updateDate", "references",
                  "appPowerLink", "appName", "appVersion", "vulType", "desc"]
    displayFields = ["Name", "Vulnerable ID", "PoC version", "Author", "Vulnerability Data", "Created Data", "Updated date", "References",
                  "Platform Homepage", "Platform", "Platform Version", "Vulnerability Type", "PoC Description"]
    ret = {}
    # for field in fields:
    for i in range(len(fields)):
            value = getattr(poc_core.current_module, fields[i], None)
            if value:
                ret[displayFields[i]] = str(value).strip()
    return ret

def get_detail_options(options):
    ret = []
    try:
        for name, opt in options.items():
            value = opt.value
            ret.append([name, value, opt.type, opt.description])
    except:
        print("error in get_detail_options")
            
    return ret

@blueprint.route('/verify-mode', methods = ['POST'])
def VerifyMode():
    params = {}
    for key in request.form:
        params[key] = request.form[key]
    #Set params to pocsuite3
    for key,val in params.items():
        key = key.replace('-value','')
        command = key + ' ' + val
        print(command)
        poc_core.command_set(command)
        
    #Realise MODE command --> VERIFY
    poc_core.command_show('options')
    result = {}
    report = {}
    try:
        # _cleanup_options()
        poc_core.command_verify()
        tmp = poc_core.current_module.result
        if(isinstance(tmp,dict)):
            for key,val in tmp.items():
                result[key] = val
        else:
            result['Result'] = str(tmp)
        report['status'] = 'success'
    except:
        report['status'] = 'Fail'
        result['Result'] = 'No result'   
    
    # newwww = html_report.HtmlReport()
    # newwww.start()

    result['Target'] = params['target-value']
    # x = kb.plugins
    result['Mode'] = 'Verified'
    # result['target'] = params['target-value']
    
    
    report['poc_name'] = poc_core.current_module.pocsuite3_module_path
    report['vul_id'] = poc_core.current_module.vulID
    report['app_name'] = poc_core.current_module.appName
    report['app_version'] = poc_core.current_module.appVersion
    
    result['report'] = report
    return jsonify({'status': 0, 'data': result})

@blueprint.route('/attack-mode', methods = ['POST'])
def AttackMode():
    params = {}
    for key in request.form:
        params[key] = request.form[key]
    #Set params to pocsuite3
    for key,val in params.items():
        key = key.replace('-value','')
        command = key + ' ' + val
        print(command)
        poc_core.command_set(command)
        
    #Realise MODE command --> VERIFY
    poc_core.command_show('options')
    result = {}
    try:
        poc_core.command_attack()
        tmp = poc_core.current_module.result
        if(isinstance(tmp,dict)):
            for key,val in tmp.items():
                result[key] = val
        else:
            result['Result'] = str(tmp)
    except:
        result['Result'] = 'No result'   
    
    # newwww = html_report.HtmlReport()
    # newwww.start()

    result['Target'] = params['target-value']
    # x = kb.plugins
    result['Mode'] = 'Attacked'
    return jsonify({'status': 0, 'data': result})



    






























































@blueprint.route('/')
@blueprint.route('/index')
def index():
    return render_template('pages/index.html', segment='dashboard', parent="dashboard")

@blueprint.route('/billing')
def billing():
    return render_template('pages/billing.html', segment='billing')

@blueprint.route('/rtl')
def rtl():
    return render_template('pages/rtl.html', segment='rtl')

@blueprint.route('/tables')
def tables():
    return render_template('pages/tables.html', segment='tables')

@blueprint.route('/virtual_reality')
def virtual_reality():
    return render_template('pages/virtual-reality.html', segment='virtual_reality')



def getField(column): 
    if isinstance(column.type, db.Text):
        return wtforms.TextAreaField(column.name.title())
    if isinstance(column.type, db.String):
        return wtforms.StringField(column.name.title())
    if isinstance(column.type, db.Boolean):
        return wtforms.BooleanField(column.name.title())
    if isinstance(column.type, db.Integer):
        return wtforms.IntegerField(column.name.title())
    if isinstance(column.type, db.Float):
        return wtforms.DecimalField(column.name.title())
    if isinstance(column.type, db.LargeBinary):
        return wtforms.HiddenField(column.name.title())
    return wtforms.StringField(column.name.title()) 


@blueprint.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():

    class ProfileForm(FlaskForm):
        pass

    readonly_fields = Users.readonly_fields
    full_width_fields = {"bio"}

    for column in Users.__table__.columns:
        if column.name == "id":
            continue

        field_name = column.name
        if field_name in full_width_fields:
            continue

        field = getField(column)
        setattr(ProfileForm, field_name, field)

    for field_name in full_width_fields:
        if field_name in Users.__table__.columns:
            column = Users.__table__.columns[field_name]
            field = getField(column)
            setattr(ProfileForm, field_name, field)

    form = ProfileForm(obj=current_user)

    if form.validate_on_submit():
        readonly_fields.append("password")
        excluded_fields = readonly_fields
        for field_name, field_value in form.data.items():
            if field_name not in excluded_fields:
                setattr(current_user, field_name, field_value)

        db.session.commit()
        return redirect(url_for('home_blueprint.profile'))
    
    context = {
        'segment': 'profile',
        'form': form,
        'readonly_fields': readonly_fields,
        'full_width_fields': full_width_fields,
    }
    return render_template('pages/profile.html', **context)


# Helper - Extract current page name from request
@blueprint.app_template_filter('replace_value')
def replace_value(value, args):
  return value.replace(args, " ").title()

def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'index'

        return segment

    except:
        return None
