# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
import json
import wtforms
import datetime as dt
from apps.home import blueprint
from apps import db
from apps.models import Targets, Incidents, Credentials, VulInTarget, Collections, CollectedFiles, VerificationResults
from apps.authentication.models import Users
from jinja2 import TemplateNotFound
from flask_wtf import FlaskForm
from flask_login import login_required, current_user
from flask import render_template, request, redirect, url_for, jsonify, session

import requests

from lib.server.server import Server
from lib import database, const

import os
from os import urandom,path as ospath,remove as osremove

import subprocess
import re
import sys,types
import random


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
from pocsuite3.lib.core.common import extract_regex_result
from pocsuite3.lib.core.enums import VUL_TYPE
# from pocsuite3.modules.listener.reverse_tcp import  WebServer
#Running Poc_core
check_environment()
set_paths(module_path())
init_options()
poc_core = PocsuiteInterpreter()
## Ending IMPORTING POCSUITE#
server = Server()
db = database.Database()
listJobs = []

# Chố này là route dành cho Pocsuite3
#,------.                        ,--. ,--.       ,----.   {1.5.9-nongit-20250620}
#|  .--. ',---. ,---.,---.,--.,--`--,-'  '-.,---.'.-.  | 
#|  '--' | .-. | .--(  .-'|  ||  ,--'-.  .-| .-. : .' <  
#|  | --'' '-' \ `--.-'  `'  ''  |  | |  | \   --/'-'  | 
#`--'     `---' `---`----' `----'`--' `--'  `----`----'   http://pocsuite.org
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
        keyword in (poc.get("references") or "").lower(),
        keyword in (poc.get("path") or "").lower(),
    ])

#lấy tất cả các thông tin về POC / Lấy tất cả POC từ pocsuite3
@blueprint.route('/api/pocs', methods=['GET'])
def api_pocs():
    '''Lấy tất cả POC từ pocsuite3'''
    listModules = poc_core.get_all_modules()
    allPocs = []
    count = 0
    for module in listModules:
        count += 1
        oneRow = {
            "id": str(count),
            "name": module.get("name"),
            "description": module.get("desc") or "",
            "cve": module.get("VulID") or "",
            "category": module.get("vulType") or "",
            "risk_level": "high",  # Nếu có trường risk_level thì lấy, không thì hardcode
            "status": "pending",   # Nếu có trạng thái thì lấy, không thì hardcode
            "source_code": ""      # Sẽ lấy sau bằng API khác nếu cần
        }
        allPocs.append(oneRow)
    return jsonify({"pocs": allPocs})


def normalize_vultype(vt):
    if isinstance(vt, list):
        return vt[0] if vt else ""
    if hasattr(vt, "value"):
        return vt.value
    if vt is None:
        return ""
    return str(vt)
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
        # Debug: In ra đường dẫn module để kiểm tra
        #print(f"Module path: {module['path']}")
        
        oneRow = {
            "id": str(count),
            "appversion": module["appversion"],
            "name": module["name"],
            "appname": module["appname"],
            "path": module["path"],
            "author": module["author"],
            "references": module["references"],
            "vulType": normalize_vultype(module.get("vulType")),
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
        'current_page': page,
        'pocs':current_pocs
    })

#lấy tất cả danh sách loại lỗ hổng
@blueprint.route('/api/poc-categories', methods=['GET'])
def api_poc_categories():
    """API trả về tất cả vultype (category) chuẩn từ class VUL_TYPE"""
    categories = []
    for attr in dir(VUL_TYPE):
        if not attr.startswith('__') and not callable(getattr(VUL_TYPE, attr)):
            categories.append({
                "name": attr,
                "value": getattr(VUL_TYPE, attr)
            })
    # Loại bỏ trùng lặp theo value (nếu cần)
    unique = {}
    for cat in categories:
        unique[cat["value"]] = cat  # Nếu value trùng thì giữ cái cuối
    categories = sorted(unique.values(), key=lambda x: x["value"])
    return jsonify({'categories': categories})

# xem thông tin của `1 poc
@blueprint.route('/view-poc', methods = ['GET'])
def poc():
    poc_path=request.args.get('poc_path')
    return render_template('poc/view-poc.html', segment='view_poc', poc_path=poc_path)

#lấy các toàn bộ thông tin của 1 POC
@blueprint.route('/get-poc-info', methods = ['POST'])
def get_poc_info():
    if not 'poc_path' in request.form:
        return jsonify({'status': -1, 'msg': 'poc-path is required'})

    poc_path = request.form['poc_path']
    print(f"Received poc_path: '{poc_path}'")  # Debug log
    #print(f"[+] first poc_path: '{poc_path}'")  # Debug log

    if not ('pocs' in poc_path):
        poc_path = os.path.join('pocs', poc_path)
    
    print(f"[+] Final poc_path: '{poc_path}'")  # Debug log
    
    try:
        #để load PoC tương ứng.
        poc_core.command_use(poc_path)
    except:
        return jsonify({'status': -1, 'msg': 'No poc is available by that poc-path'})
    if not poc_core.current_module:
        return jsonify({'status': -1, 'msg': 'No poc is available by that poc-path'})
    modeString = ''

    #Xác định các chế độ hỗ trợ (mode)
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
        'info': get_info_poc_as_dict(), # lấy toàn bộ thông tin từ casdc trường 
        'modes':modeString, # xem thử có những mode gì đây này
        'global_options': get_detail_options(currentPoC.global_options),
        'payload_options': get_detail_options(currentPoC.payload_options),
        'poc-path':poc_path,
        'isServerOnline':isServerOnline
    }
    if(hasattr(currentPoC,'options')):
        data['options'] =  get_detail_options(currentPoC.options)
    
    print(f"[x] Options's POC {data['options']}")
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

@blueprint.route('/api/verify-mode', methods = ['POST'])
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
        
    #kiểm tra và hiển thị cấu hình cuối cùng trước khi thực hiện chức năng verify, 
    # giúp đảm bảo tất cả tham số đã được thiết lập đúng và có thể debug nếu có vấn đề.
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

@blueprint.route('/api/attack-mode', methods = ['POST'])
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


@blueprint.route('/api/save-verification-results', methods=['POST'])
def save_verification_results():
    """Save verification results to database"""
    try:
        data = request.get_json()
        
        if not data or 'results' not in data:
            return jsonify({'status': -1, 'message': 'No results data provided'}), 400
        
        poc_id = data.get('poc_id')
        poc_path = data.get('poc_path')
        results = data.get('results', [])
        
        saved_count = 0
        for result_item in results:
            target = result_item.get('target', 'Unknown')
            result_data = result_item.get('result', {})
            
            # Convert result_data to JSON string
            result_json = json.dumps(result_data, indent=2) if result_data else None
            
            # Get target IP if available
            target_ip = None
            if isinstance(result_data, dict) and 'Target' in result_data:
                # Try to extract IP from target info
                target_info = result_data.get('Target', '')
                # You might need to adjust this based on your target format
                if ':' in target_info:
                    target_ip = target_info.split(':')[0]
            
            # Create verification result
            VerificationResults.create_result(
                target_hostname=target,
                poc_id=poc_id,
                poc_path=poc_path,
                target_ip=target_ip,
                result_data=result_json,
                status='completed',
                notes=f'Verification completed at {dt.datetime.utcnow().isoformat()}'
            )
            saved_count += 1
        
        return jsonify({
            'status': 0, 
            'message': f'Successfully saved {saved_count} verification results',
            'saved_count': saved_count
        })
        
    except Exception as e:
        print(f"Error saving verification results: {str(e)}")
        return jsonify({'status': -1, 'message': f'Error saving results: {str(e)}'}), 500


@blueprint.route('/api/get-verification-results', methods=['GET'])
def get_verification_results():
    """Get verification results from database"""
    try:
        # Get query parameters
        target = request.args.get('target')
        poc_id = request.args.get('poc_id')
        limit = request.args.get('limit', 50, type=int)
        
        if target:
            results = VerificationResults.get_by_target(target)
        elif poc_id:
            results = VerificationResults.get_by_poc(poc_id)
        else:
            results = VerificationResults.get_recent_results(limit)
        
        # Convert to list of dictionaries
        results_list = []
        for result in results:
            result_dict = result.to_dict()
            # Parse JSON data back to object
            if result_dict.get('result_data'):
                try:
                    result_dict['result_data'] = json.loads(result_dict['result_data'])
                except:
                    pass  # Keep as string if parsing fails
            results_list.append(result_dict)
        
        return jsonify({
            'status': 0,
            'results': results_list,
            'count': len(results_list)
        })
        
    except Exception as e:
        print(f"Error getting verification results: {str(e)}")
        return jsonify({'status': -1, 'message': f'Error getting results: {str(e)}'}), 500

#các hàm của server shell
@blueprint.route('/server-status', methods = ['GET'])
@login_required
def server_status():
    status = {
        'isActive': server.is_active,
    }

    if server.is_active:
        status['ip'] = server.ip
        status['port'] = server.port

    return jsonify(status)

@blueprint.route('/start-server', methods = ['POST'])
@login_required
def start_server():
    if not 'ip' in request.form or not 'port' in request.form:
        return jsonify({'status': -1, 'msg': 'Provide an IP and a Port'})

    ip = request.form['ip']
    port = request.form['port']

    if not valid_ip(ip):
        return jsonify({'status': -1, 'msg': 'Invalid IP'})

    if not valid_port(port):
        return jsonify({'status': -1, 'msg': 'Invalid port'})

    if not server.is_active or not session['server_active']:
        if server_start(ip, port):
            return jsonify({'status': 0, 'msg': 'Successfully started server'})
        return jsonify({'status': -1, 'msg': 'Failed to start server'})

    return jsonify({'status': -1, 'msg': 'Server is already active'})


@blueprint.route('/stop-server', methods = ['POST'])
@login_required
def stop_server():
    if server.is_active or session['server_active']:
        if server_stop():
            return jsonify({'status': 0, 'msg': 'Successfully stopped server'})
        return jsonify({'status': -1, 'msg': 'Failed to stop server'})

    return jsonify({'status': -1, 'msg': 'Server is already inactive'})

def server_start(ip, port):
    if not valid_ip(ip):
        return 
    if not valid_port(port):
        return 
    session['ip'] = ip
    session['port'] = port
    session['server_active'] = True
    return server.start(ip, port)


def server_stop():
    session['ip'] = None
    session['port'] = None
    session['server_active'] = False
    return not server.stop()


@blueprint.route('/shell-mode', methods = ['POST'])
def ShellMode():
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
        
        #Phần này có thể thiết lập để Server bật sẵn, và module chạy tự lấy IP và Port từ server
        if not server.is_active or not session['server_active']:
            lhost =  poc_core.current_module.getp_option("lhost")
            lport =  poc_core.current_module.getp_option("lport")
            if server_start(lhost, lport):
                print( 'Successfully started server when exploit shellmode')
            else:
                result['Server-Error'] = "Cant open server on "+lhost+':'+lport
                return jsonify({'status': 0, 'data': result})

            poc_core.current_module.lhost = server.ip
            poc_core.current_module.lport = str(server.port)
        else:
            poc_core.current_module.lhost = server.ip
            poc_core.current_module.lport = str(server.port)
        conf.api = 1
        oldCilents = server.total_clients()
        poc_core.command_shell()
        tmp = poc_core.current_module.result
        if(isinstance(tmp,dict)):
            for key,val in tmp.items():
                result[key] = val
        else:
            result['result'] = str(tmp)
        currentCilents = server.total_clients()
        if(oldCilents<currentCilents):
            result['session'] = 'New Bot detected, move to Shell page'
        else:
            result['session'] = 'Failed. Payload executed nut no session established'      

    except:
        result['result'] = 'No result'   

   
    # x = kb.plugins
    result['target'] = params['target-value']
    result['mode'] = 'Shelled'
    return jsonify({'status': 0, 'data': result})

###-----Điều khiển bot-----
#Trả về danh sách các bot (client) đang online/kết nối tới server.
@blueprint.route('/fetch-bots', methods = ['GET'])
@login_required
def fetch_bots():
    # print("kika.py fetchbots called")
    online_bots = []

    bots = server.list_clients()
    # print("bots found")
    # print(bots)
    for bot in bots:
        online_bots.append({
            'id': bot['bot_id'],
            'ip': bot['ip'],
            'os': bot['system'],

            'country': 'VN',
        })

    return jsonify({
        'bots': online_bots,
    })

#Nhận vào bot-id từ client, trả về thông tin chi tiết về bot đó (ip, hệ điều hành).
@blueprint.route('/get-bot-info', methods = ['POST'])
@login_required
def get_bot_info():
    if not 'bot-id' in request.form:
        return jsonify({'status': -1, 'msg': 'bot-id is required'})

    bot_id = request.form['bot-id']
    bot = server.get_bot(bot_id)

    if not bot:
        return jsonify({'status': -1, 'msg': 'No bot is available by that id'})


    data = {
        'system': {
            'ip': bot['ip'],
            'OS': bot['OS']
        }
    }

    return jsonify({'status': 0, 'data': data})

#Nhận một lệnh (cmd) từ client, 
# gửi lệnh này tới bot (client) hiện tại thông qua server, 
# và trả về kết quả thực thi lệnh đó.
@blueprint.route('/control/cmd', methods = ['POST'])
@login_required
# @bot_required
def control_cmd():
    if not 'cmd' in request.form:
        return jsonify({'resp': 'No cmd found'})

    cmd = request.form['cmd']

    if not server.client:
        return jsonify({'resp': ''})
    resp = ''
    resp = server.execute_cmd_console(server.client,cmd)
    return jsonify({'resp': resp})




#lấy poc theo Source
@blueprint.route('/api/get-source-poc', methods=['POST', 'GET'])
def source_poc():
    poc_path = request.form.get('poc_path') or request.args.get('poc_path')
    if not poc_path:
        return jsonify({'status': -1, 'msg': 'poc-path is required'})
    poc_path = poc_path + '.py'
    #print(f"xx] {poc_path}")
    # Đảm bảo chỉ lấy file trong thư mục pocsuite3/pocs/
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'pocsuite3'))
    file_path = os.path.abspath(os.path.join(base_dir, poc_path))
    if not file_path.startswith(base_dir):
        return jsonify({'status': -1, 'msg': 'Invalid path'})

    if not os.path.isfile(file_path):
        return jsonify({'status': -1, 'msg': 'File not found'})

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        return jsonify({'status': 0, 'data': {'source_code': source_code}})
    except Exception as e:
        return jsonify({'status': -1, 'msg': str(e)})

#save edit source POC
@blueprint.route("/api/save-edit-source-poc", methods=['POST'])
def save_edit_source_poc():
    poc_path = request.form.get('poc_path') or request.args.get('poc_path')
    source_code = request.form.get('source_code')

    if not poc_path or not source_code:
        return jsonify({'status': -1, 'msg': 'source_code OR poc-path is required'})
    poc_path = poc_path + '.py'
    #lấy đường dẫn
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'pocsuite3'))
    file_path = os.path.abspath(os.path.join(base_dir, poc_path))
    if not file_path.startswith(base_dir):
        return jsonify({'status':-1, 'msg':'Invalid path'})

    try:
        with open(file_path,'w',encoding='utf-8') as f:
            f.write(source_code)
        return jsonify({'status':0, 'msg':'Save successfully'})
    except Exception as e:
        return jsonify({'status':-1, 'msg':str(e)})


def LogLastStatus(status):
    """
    status -1,0,1 fail,running, success
    """
    global listJobs
    if len(listJobs)<1:
        return
    
    listJobs[0]['status'] = status

#hàm upload POC
@blueprint.route("/api/upload-poc", methods=['POST'])
def upload_poc():
    #kiểm tra xem file upload tồn tại
    if 'poc_file' not in request.files:
        return jsonify({"status":-1, 'msg':"No file in request data"}),400
    
    poc_file = request.files['poc_file']
    if poc_file.filename == '':
        return jsonify({'status':-1,'msg': 'No selected file'}), 400
    
    #kt tên và cài lấy tên file
    # 
    code = poc_file.read().decode('utf-8')
    poc_name = extract_regex_result(r'''(?sm)POCBase\):.*?name\s*=\s*['"](?P<result>.*?)['"]''', code)
    print(f"pocname: {poc_name}")
    if not poc_name:
        return jsonify({'status':-1, 'msg':'Cannot extract POC name from file'}), 400

    # Chuẩn hóa tên file
    safe_name = "".join([c if c.isalnum() or c in ('_', '-') else '_' for c in poc_name])
    UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'pocsuite3','pocs'))
    file_path = os.path.join(UPLOAD_FOLDER, f"{safe_name}.py")
    print(f"{file_path}")
    # Kiểm tra trùng tên
    if os.path.exists(file_path):
        return jsonify({'status':-1, 'msg':'A POC with this name already exists!'}), 400

    # Lưu file
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
    except Exception as e:
        return jsonify({'status':-1, 'msg':f"{str(e)}"})

    # reload Pocsuite3 // Reload core
    global poc_core
    poc_core = PocsuiteInterpreter()
    LogLastStatus(1)
    
    return jsonify({'status': 0, 'msg': 'File uploaded and POC core reloaded successfully'}), 200




























































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


