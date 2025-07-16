# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import datetime as dt
from apps.targets import blueprint
from apps import db
from apps.models import Targets, Reports
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




#bắt đầu code từ đây
@blueprint.route('/targets')
def targets():
    return render_template('targets/index-targets.html', segment='index_targets')

#lấy và search ở hàm này
@blueprint.route('/api/targets', methods=['GET'])
def get_targets():
    '''Tìm kiếm và sort targets LIST'''
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '', type=str).strip()
    sort_type = request.args.get('sort', '', type=str).strip()
    per_page = 7
    print(f"[x] page: {page} & search_query={search_query} & sort_type={sort_type}")
    targets_paginated, total_pages = Targets.search(search_query, page, per_page, sort_type)

    html = render_template('partials/partial_list_targets.html', targets=targets_paginated, loader=0)

    return jsonify({
        'html': html,
        'total_pages': total_pages
    })

#kiểm target có còn được online ko
@blueprint.route('/api/checkstatussite',methods=['POST'])
def check_status_website():
    '''kiểm tra url theo status code trả về'''
    data = request.get_json()
    
    if not data or 'url' not in data:
        return jsonify({"status":-1,"error": "Thiếu tham số 'url' trong request body"}), 400

    url = data['url']
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url  # Thêm mặc định http nếu thiếu

    try:
        response = requests.get(url, timeout=5, stream=True)
        if response.status_code < 400:
            return jsonify({
                "url": url,
                "status": "online",
                "http_status": response.status_code
            }), 200
        else:
            return jsonify({
                "url": url,
                "status": "offline",
                "http_status": response.status_code
            }), 200
    except requests.RequestException:
        return jsonify({
            "url": url,
            "status": "offline"
        }), 200

#lấy toàn bọ target
@blueprint.route('/api/getalltarget',methods=['GET'])
def get_all_targets():
    try:
        targets = Targets.query.all()
        #print(f"{targets}")
        targets_list = [t.to_dict() for t in targets]
        return jsonify({'targets': targets_list}), 200
    except Exception as e:
        return jsonify({'error': 'Server error', 'details': str(e)}), 500

@blueprint.route('/api/add_targets', methods=['POST'])
def add_targets():
    """API để thêm một hoặc nhiều target mới theo kiểu thủ công"""
    try:
        data = request.get_json()
        print(f"Data: {data}")
        if not data:
            return jsonify({'error': 'No input data provided'}), 400

        # Nếu là gửi nhiều target (dưới key 'targets')
        targets_data = data.get('targets')
        if targets_data and isinstance(targets_data, list):
            created_ids = []
            for t in targets_data:
                new_target = Targets.create_target(
                    hostname=t.get('Hostname'),
                    ip_address=t.get('Ip_address'),
                    server_type=t.get('Server_type'),
                    #os=t.get('Operating_system'),
                    location=t.get('Location'),
                    status=t.get('Status'),
                    #privilege_escalation=t.get('Privilege_escalation'),
                    #exploitation_level=t.get('Exploitation_level'),
                    #incident_id=t.get('Id_vul_in_target'),
                    notes=t.get('Notes')
                )
                created_ids.append(new_target.server_id)
            return jsonify({
                'msg': f'{len(created_ids)} targets added successfully',
                'target_ids': created_ids
            }), 201
        else:
            # Nếu chỉ gửi 1 target (giữ lại backward compatibility)
            new_target = Targets.create_target(
                hostname=data.get('Hostname'),
                ip_address=data.get('Ip_address'),
                server_type=data.get('Server_type'),
                #os=data.get('Operating_system'),
                location=data.get('Location'),
                status=data.get('Status'),
                #privilege_escalation=data.get('Privilege_escalation'),
                #exploitation_level=data.get('Exploitation_level'),
                #incident_id=data.get('Id_vul_in_target'),
                notes=data.get('Notes')
            )
            return jsonify({
                'msg': 'Target added successfully',
                'target_id': new_target.server_id
            }), 201
    except Exception as e:
        return jsonify({'error': 'Server error', 'details': str(e)}), 500

@blueprint.route('/api/add_targets_from_file', methods=['POST'])
def add_targets_from_file():
    '''Thêm Target từ file'''
    try:
        if 'file' not in request.files:
            return jsonify({'status': -1, 'msg': 'No file uploaded'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'status': -1, 'msg': 'No selected file'}), 400

        import io
        stream = io.StringIO(file.stream.read().decode('utf-8'))
        created_ids = []
        for line in stream:
            hostname = line.strip()
            #print(f"Read line: '{hostname}'")  # Thêm log
            if hostname:
                try:
                    new_target = Targets.create_target(
                                                hostname=hostname,
                                                ip_address='None',
                                                server_type='web_server',
                                                location='None',
                                                status='online',
                                                notes=''
                                            )
                    created_ids.append(new_target.server_id)
                except Exception as e:
                    print(f"Error creating target for '{hostname}': {e}")
        if not created_ids:
            return jsonify({'status': -1, 'msg': 'No valid hostnames found or all failed to add.'})
        return jsonify({'status': 0, 'msg': f'Add {len(created_ids)} targets with file upload Success.', 'target_ids': created_ids, 'count': len(created_ids)})
    except Exception as e:
        print(f"Exception: {e}")
        return jsonify({'status':-1, 'msg':str(e)})

@blueprint.route('/api/update_target', methods=['POST'])
def update_target():
    '''Sửa thông tin của target'''
    data = request.get_json()
    print(f"data edit target: {data}")
    
    try:
        # Lấy target instance trước
        target = Targets.get_by_id(data.get('server_id'))
        if not target:
            return jsonify({'status': -1, 'msg': 'Target not found'})
        
        # Cập nhật target với dữ liệu mới
        target.update(
            hostname=data.get('hostname'),
            ip_address=data.get('ip_address'),
            server_type=data.get('server_type'),
            os=data.get('os'),
            location=data.get('location'),
            status=data.get('status'),
            notes=data.get('notes')
        )
        
        return jsonify({'status': 0, 'msg': 'Updated successfully'})
        
    except Exception as e:
        print(f"Error updating target: {str(e)}")
        return jsonify({'status': -1, 'msg': str(e)})

@blueprint.route('/api/delete_target',methods=['POST'])
def delete_target():
    """API để xóa một hoặc nhiều target"""
    try:
        data = request.get_json()
        print(f"Delete data: {data}")
        
        if not data:
            return jsonify({'status': -1, 'msg': 'No data provided'}), 400
        
        # Nếu gửi danh sách target IDs
        target_ids = data.get('target_ids', [])
        if isinstance(target_ids, list) and target_ids:
            deleted_count = 0
            failed_ids = []
            
            for target_id in target_ids:
                try:
                    target = Targets.get_by_id(target_id)
                    if target:
                        target.delete()
                        deleted_count += 1
                    else:
                        failed_ids.append(target_id)
                except Exception as e:
                    print(f"[-] Error deleting target {target_id}: {e}")
                    failed_ids.append(target_id)
            
            if deleted_count > 0:
                return jsonify({
                    'status': 0, 
                    'msg': f'Successfully deleted {deleted_count} targets',
                    'deleted_count': deleted_count,
                    'failed_ids': failed_ids
                })
            else:
                return jsonify({
                    'status': -1, 
                    'msg': 'No targets were deleted',
                    'failed_ids': failed_ids
                }), 400
        
        # Nếu gửi single target ID
        elif data.get('target_id'):
            target_id = data.get('target_id')
            target = Targets.get_by_id(target_id)
            
            if not target:
                return jsonify({'status': -1, 'msg': f'Target with ID {target_id} not found'}), 404
            
            target.delete()
            return jsonify({
                'status': 0, 
                'msg': f'Target {target_id} deleted successfully'
            })
        
        else:
            return jsonify({'status': -1, 'msg': 'No target_id or target_ids provided'}), 400
            
    except Exception as e:
        print(f"Error in delete_target: {str(e)}")
        return jsonify({'status': -1, 'msg': f'Server error: {str(e)}'}), 500

#xem thông tin của 1 target 
@blueprint.route('/view-target', methods=['GET'])
def view_target():
    idtarget = request.args.get('idtarget')
    # tạm thời không kiểm tra có tồn tại
    #lấy thông tin của CSDL
    target = Targets.get_by_id(idtarget)
    report = Reports.get_by_server_id(server_id=idtarget)
    #lấy thông tin CVE lấy được
    #lấy thông tin về trình sát
    
    list_poc=["Trần Ku em", "Hello Các em", "Nguyễn Mlem Kem"]
    return render_template('targets/view-target.html', segment='view_target',list_poc=list_poc, target = target, report = report)




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

