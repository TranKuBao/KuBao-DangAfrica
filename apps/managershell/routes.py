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

from flask import Blueprint, request, jsonify
from flask_login import login_required
from apps.models import ShellConnection, ShellCommand, ShellStatus, ShellType, Targets, db
from apps.managershell.pwncat import PwncatManager
import uuid
import psutil
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

shell_manager = PwncatManager()

def get_server_interfaces():
    """Lấy danh sách interface mạng của server"""
    try:
        interfaces = set()
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if getattr(addr, 'family', None) == 2:  # IPv4
                    interfaces.add(addr.address)
        interfaces.update(['0.0.0.0', '127.0.0.1'])
        return sorted(interfaces)
    except Exception as e:
        logger.error(f"Error getting server interfaces: {e}")
        return ['0.0.0.0', '127.0.0.1']

# Main routes
@blueprint.route('/shells')
# Trang chính quản lý shell, hiển thị danh sách target và interface mạng
def shells():
    """Trang chính quản lý shell"""
    try:
        targets = Targets.query.all()
        interfaces = get_server_interfaces()
        return render_template(
            'shells/index-shell.html',
            segment='index_shell',
            targets=targets,
            interfaces=interfaces
        )
    except Exception as e:
        logger.error(f"Error in shells route: {e}")
        return render_template('error/500.html'), 500

@blueprint.route('/shells/<shell_id>')
# Trang xem chi tiết shell và tương tác với shell cụ thể
def view_shell(shell_id):
    """Trang xem chi tiết shell và tương tác"""
    try:
        shell = ShellConnection.get_by_id(shell_id)
        if not shell:
            return render_template('error/404.html'), 404
        
        return render_template(
            'shells/view-shell.html',
            segment='view_shell',
            shell_id=shell_id,
            shell_name=shell.name,
            shell=shell
        )
    except Exception as e:
        logger.error(f"Error in view_shell route: {e}")
        return render_template('error/500.html'), 500


# Demo routes
@blueprint.route('/demo/create-sample-shells')
# Tạo shell mẫu cho mục đích demo
def create_sample_shells():
    """Tạo shell mẫu cho demo"""
    try:
        sample_shells = [
            {
                'name': 'web_server_shell',
                'shell_type': ShellType.REVERSE,
                'local_ip': '0.0.0.0',
                'local_port': 4444,
                'hostname': 'web-server-01',
                'status': ShellStatus.LISTENING,
                'user': 'root',
                'privilege_level': 'admin'
            },
            {
                'name': 'db_server_shell',
                'shell_type': ShellType.BIND,
                'remote_ip': '192.168.1.100',
                'remote_port': 5555,
                'hostname': 'db-server-01',
                'status': ShellStatus.CONNECTED,
                'user': 'mysql',
                'privilege_level': 'user'
            },
            {
                'name': 'app_server_shell',
                'shell_type': ShellType.REVERSE,
                'local_ip': '127.0.0.1',
                'local_port': 6666,
                'hostname': 'app-server-01',
                'status': ShellStatus.CLOSED,
                'user': 'www-data',
                'privilege_level': 'user'
            }
        ]
        
        created_count = 0
        for shell_data in sample_shells:
            existing = ShellConnection.query.filter_by(name=shell_data['name']).first()
            
            if not existing:
                conn = ShellConnection(
                    connection_id=str(uuid.uuid4()),
                    name=shell_data['name'],
                    shell_type=shell_data['shell_type'],
                    local_ip=shell_data.get('local_ip'),
                    local_port=shell_data.get('local_port'),
                    remote_ip=shell_data.get('remote_ip'),
                    remote_port=shell_data.get('remote_port'),
                    hostname=shell_data['hostname']
                )
                # Set additional fields after creation
                conn.user = shell_data.get('user')
                conn.privilege_level = shell_data.get('privilege_level')
                conn.status = shell_data['status']
                db.session.add(conn)
                created_count += 1
        
        db.session.commit()
        logger.info(f"Created {created_count} sample shells")
        
        return jsonify({
            'status': 'success',
            'msg': f'Created {created_count} sample shells',
            'created_count': created_count
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating sample shells: {e}")
        return jsonify({
            'status': 'fail',
            'msg': str(e)
        }), 500

# 1. Danh sách shell (có filter, search, sort)
@blueprint.route('/api/shells', methods=['GET'])
# API: Lấy danh sách shell (có phân trang, tìm kiếm, sắp xếp)
def list_shells():
    """Danh sách shell với phân trang, tìm kiếm, sắp xếp"""
    try:
        page = request.args.get('page', default=1, type=int) or 1
        search_query = request.args.get('search', '', type=str).strip()
        sort_type = request.args.get('sort', '', type=str).strip()
        per_page = request.args.get('per_page', default=6, type=int) or 6

        # Xây dựng query
        print(f"[x]LIST-SHELL page: {page} & search_query={search_query} & sort_type={sort_type}")   
        shells_paginated, total_pages = ShellConnection.search(keyword=search_query, page=page, per_page=per_page, sort_type=sort_type)
        
        html = render_template('shells/partial-list-shell.html', shells=shells_paginated)

        return jsonify({
                'html': html,
                'total_pages': total_pages,
                'current_page': page
            })
    except Exception as e:
        logger.error(f"Error in list_shells: {e}")
        return jsonify({
            'status': 'fail',
            'msg': 'Internal server error'
        }), 500

# lấy Danh sách shell dưới dạng JSON cho modal tương tác
@blueprint.route('/api/shells/list', methods=['GET'])
# API: Lấy danh sách shell dưới dạng JSON (cho modal tương tác)
def list_shells_json():
    """Danh sách shell dưới dạng JSON cho modal tương tác"""
    try:
        # Lấy tất cả shell
        shells = ShellConnection.query.all()
        shell_list = []
        
        for shell in shells:
            shell_data = {
                'connection_id': shell.connection_id,
                'name': shell.name,
                'shell_type': shell.shell_type.value if hasattr(shell.shell_type, 'value') else str(shell.shell_type),
                'status': shell.status.value if hasattr(shell.status, 'value') else str(shell.status),
                'hostname': shell.hostname,
                'local_ip': shell.local_ip,
                'local_port': shell.local_port,
                'remote_ip': shell.remote_ip,
                'remote_port': shell.remote_port,
                'target_id': shell.target_id,
                'url': shell.url,
                'user': shell.user,
                'privilege_level': shell.privilege_level,
                'created_at': shell.created_at.isoformat() if shell.created_at else None,
                'updated_at': shell.updated_at.isoformat() if shell.updated_at else None
            }
            shell_list.append(shell_data)
        
        return jsonify({
            'status': 'success',
            'data': shell_list
        })
    except Exception as e:
        return jsonify({
            'status': 'fail',
            'msg': str(e)
        }), 500

# 2. Tạo mới shell (listener/bind)
@blueprint.route('/api/shells', methods=['POST'])
# API: Tạo mới shell (listener hoặc bind)
def create_shell():
    """Tạo mới shell (listener/bind)"""
    try:
        data = request.get_json() or {}
        shell_type = data.get('shell_type')
        if not shell_type:
            return jsonify({'status': 'fail', 'msg': 'Missing shell_type'}), 400
        
        port = data.get('port')
        if port is None:
            return jsonify({'status': 'fail', 'msg': 'Missing port'}), 400
        
        try:
            port = int(port)
            if port < 1 or port > 65535:
                return jsonify({'status': 'fail', 'msg': 'Port must be between 1 and 65535'}), 400
        except (TypeError, ValueError):
            return jsonify({'status': 'fail', 'msg': 'Invalid port'}), 400
        
        interface = data.get('interface') or '0.0.0.0'
        ip = data.get('ip')
        target_id = data.get('target_id')
        target = Targets.query.get(target_id) if target_id else None
        name = data.get('name') or f'{shell_type}_{uuid.uuid4().hex[:8]}'
        url = data.get('url')

        # Kiểm tra shell đã tồn tại
        if shell_type == 'reverse':
            exists = ShellConnection.query.filter_by(
                shell_type=ShellType.REVERSE,
                local_ip=interface,
                local_port=port
            ).filter(
                (ShellConnection.status == ShellStatus.LISTENING) | 
                (ShellConnection.status == ShellStatus.CONNECTED)
            ).first()
            if exists:
                return jsonify({
                    'status': 'fail', 
                    'msg': f'IP {interface}:{port} is already in use for a reverse shell!'
                }), 400
        elif shell_type == 'bind':
            if not ip:
                return jsonify({'status': 'fail', 'msg': 'Missing IP for bind shell'}), 400
            exists = ShellConnection.query.filter_by(
                shell_type=ShellType.BIND, 
                remote_ip=ip, 
                remote_port=port
            ).filter(
                (ShellConnection.status == ShellStatus.LISTENING) | 
                (ShellConnection.status == ShellStatus.CONNECTED)
            ).first()
            if exists:
                return jsonify({
                    'status': 'fail', 
                    'msg': f'IP {ip}:{port} is already in use for a bind shell!'
                }), 400

        # Tạo shell mới
        conn = ShellConnection(
            connection_id=str(uuid.uuid4()),
            name=name,
            shell_type=ShellType.REVERSE if shell_type=='reverse' else ShellType.BIND,
            local_ip=interface if shell_type=='reverse' else None,
            local_port=port if shell_type=='reverse' else None,
            remote_ip=ip if shell_type=='bind' else None,
            remote_port=port if shell_type=='bind' else None,
            target_id=target_id,
            hostname=target.hostname if target else None,
            url=url
        )
        conn.status = ShellStatus.CLOSED
        db.session.add(conn)
        db.session.commit()
        
        return jsonify({'status': 'success', 'data': conn.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating shell: {e}")
        return jsonify({'status': 'fail', 'msg': str(e)}), 500

@blueprint.route('/api/shells/<shell_id>', methods=['GET'])
# API: Xem chi tiết một shell
def get_shell(shell_id):
    """Xem chi tiết shell"""
    try:
        conn = ShellConnection.get_by_id(shell_id)
        if not conn:
            return jsonify({'status': 'fail', 'msg': 'Shell not found'}), 404
        return jsonify({'status': 'success', 'data': conn.to_dict()})
    except Exception as e:
        logger.error(f"Error getting shell {shell_id}: {e}")
        return jsonify({'status': 'fail', 'msg': str(e)}), 500

@blueprint.route('/api/shells/<shell_id>/command', methods=['POST'])
# API: Gửi lệnh tới shell
def send_command(shell_id):
    """Gửi lệnh tới shell"""
    try:
        data = request.get_json() or {}
        command = data.get('command')
        if not command:
            return jsonify({'status': 'fail', 'msg': 'No command provided'}), 400
        
        conn = ShellConnection.get_by_id(shell_id)
        if not conn:
            return jsonify({'status': 'fail', 'msg': 'Shell not found'}), 404
        
        if conn.status == ShellStatus.CLOSED:
            return jsonify({'status': 'fail', 'msg': 'Shell is not connected'}), 400
        
        output = shell_manager.send_command(shell_id, command)
        cmd = ShellCommand.create_command(shell_id, command, output=output, success=output is not None)
        
        logger.info(f"Command executed on shell {shell_id}: {command}")
        return jsonify({
            'status': 'success', 
            'data': {
                'output': output, 
                'command_id': cmd.command_id,
                'success': output is not None
            }
        })
    except Exception as e:
        logger.error(f"Error sending command to shell {shell_id}: {e}")
        return jsonify({'status': 'fail', 'msg': str(e)}), 500

@blueprint.route('/api/shells/<shell_id>/history', methods=['GET'])
# API: Lấy lịch sử lệnh đã gửi tới shell
def shell_history(shell_id):
    """Lấy lịch sử lệnh"""
    try:
        limit = min(int(request.args.get('limit', 50)), 100)  # Max 100 commands
        cmds = ShellCommand.get_by_connection(shell_id, limit=limit)
        return jsonify({
            'status': 'success', 
            'data': [c.to_dict() for c in cmds]
        })
    except Exception as e:
        logger.error(f"Error getting shell history {shell_id}: {e}")
        return jsonify({'status': 'fail', 'msg': str(e)}), 500

@blueprint.route('/api/shells/<shell_id>/start', methods=['POST'])
# API: Khởi động shell (listener hoặc bind)
def start_shell(shell_id):
    """Khởi động shell"""
    try:
        conn = ShellConnection.get_by_id(shell_id)
        if not conn:
            return jsonify({'status': 'fail', 'msg': 'Shell not found'}), 404

        if conn.status in [ShellStatus.LISTENING, ShellStatus.CONNECTED]:
            return jsonify({'status': 'fail', 'msg': 'Shell is already running'}), 400

        shell_type = conn.shell_type
        port = conn.local_port if shell_type == ShellType.REVERSE else conn.remote_port
        name = conn.name
        url = conn.url
        interface = conn.local_ip if shell_type == ShellType.REVERSE else None
        ip = conn.remote_ip if shell_type == ShellType.BIND else None

        # Khởi động shell
        if shell_type == ShellType.REVERSE:
            new_shell_id = shell_manager.start_listener(port, name=conn.connection_id, url=url, listen_ip=str(interface))
        elif shell_type == ShellType.BIND:
            new_shell_id = shell_manager.connect_shell(ip, port, name=conn.connection_id, url=url)
        else:
            return jsonify({'status': 'fail', 'msg': 'Invalid shell type'}), 400

        if not new_shell_id:
            return jsonify({'status': 'fail', 'msg': 'Failed to start shell'}), 500

        # Cập nhật trạng thái
        new_status = ShellStatus.LISTENING if shell_type == ShellType.REVERSE else ShellStatus.CONNECTED
        conn.update_status(new_status)
        
        #logger.info(f"Started shell {shell_id} with status {new_status}")
        return jsonify({'status': 'success', 'msg': f'Shell started successfully'})

    except Exception as e:
        #logger.error(f"Error starting shell {shell_id}: {e}")
        return jsonify({'status': 'fail', 'msg': str(e)}), 500

@blueprint.route('/api/shells/<shell_id>/close', methods=['POST'])
# API: Đóng shell (ngắt kết nối)
def close_shell(shell_id):
    """Đóng shell"""
    try:
        conn = ShellConnection.get_by_id(shell_id)
        if not conn:
            return jsonify({'status': 'fail', 'msg': 'Shell not found'}), 404

        ok = shell_manager.close_shell(shell_id)
        if conn:
            conn.update_status(ShellStatus.CLOSED)
        
        logger.info(f"Closed shell {shell_id}")
        return jsonify({
            'status': 'success' if ok else 'fail',
            'msg': 'Shell closed successfully' if ok else 'Failed to close shell'
        })
    except Exception as e:
        logger.error(f"Error closing shell {shell_id}: {e}")
        return jsonify({'status': 'fail', 'msg': str(e)}), 500

@blueprint.route('/api/shells/<shell_id>', methods=['DELETE'])
# API: Xóa shell khỏi hệ thống
def delete_shell(shell_id):
    """Xóa shell"""
    try:
        conn = ShellConnection.get_by_id(shell_id)
        if not conn:
            return jsonify({'status': 'fail', 'msg': 'Shell not found'}), 404
        
        # Đảm bảo process shell bị kill nếu còn
        shell_manager.close_shell(shell_id)
        
        try:
            conn.delete()
            logger.info(f"Deleted shell {shell_id}")
            return jsonify({'status': 'success', 'msg': 'Shell deleted successfully'})
        except Exception as e:
            logger.error(f"Error deleting shell {shell_id}: {e}")
            return jsonify({'status': 'fail', 'msg': str(e)}), 500
            
    except Exception as e:
        logger.error(f"Error in delete_shell {shell_id}: {e}")
        return jsonify({'status': 'fail', 'msg': str(e)}), 500

# Additional API routes
@blueprint.route('/api/shells/<shell_id>/upload', methods=['POST'])
# API: Upload file lên shell
def upload_file(shell_id):
    """Upload file to shell"""
    try:
        data = request.get_json() or {}
        local_path = data.get('local_path')
        remote_path = data.get('remote_path')
        
        if not local_path or not remote_path:
            return jsonify({'status': 'fail', 'msg': 'Missing local_path or remote_path'}), 400
        
        ok = shell_manager.upload_file(shell_id, local_path, remote_path)
        return jsonify({
            'status': 'success' if ok else 'fail',
            'msg': 'File uploaded successfully' if ok else 'Failed to upload file'
        })
    except Exception as e:
        logger.error(f"Error uploading file to shell {shell_id}: {e}")
        return jsonify({'status': 'fail', 'msg': str(e)}), 500

@blueprint.route('/api/shells/<shell_id>/download', methods=['POST'])
# API: Download file từ shell về server
def download_file(shell_id):
    """Download file from shell"""
    try:
        data = request.get_json() or {}
        remote_path = data.get('remote_path')
        local_path = data.get('local_path')
        
        if not remote_path or not local_path:
            return jsonify({'status': 'fail', 'msg': 'Missing remote_path or local_path'}), 400
        
        ok = shell_manager.download_file(shell_id, remote_path, local_path)
        return jsonify({
            'status': 'success' if ok else 'fail',
            'msg': 'File downloaded successfully' if ok else 'Failed to download file'
        })
    except Exception as e:
        logger.error(f"Error downloading file from shell {shell_id}: {e}")
        return jsonify({'status': 'fail', 'msg': str(e)}), 500

@blueprint.route('/api/shells/<shell_id>/escalate', methods=['POST'])
# API: Thực hiện leo thang đặc quyền trên shell
def escalate_privilege(shell_id):
    """Privilege escalation"""
    try:
        data = request.get_json() or {}
        user = data.get('user')
        
        if not user:
            return jsonify({'status': 'fail', 'msg': 'Missing user parameter'}), 400
        
        ok = shell_manager.escalate_privilege(shell_id, user)
        return jsonify({
            'status': 'success' if ok else 'fail',
            'msg': 'Privilege escalation successful' if ok else 'Failed to escalate privileges'
        })
    except Exception as e:
        logger.error(f"Error escalating privileges for shell {shell_id}: {e}")
        return jsonify({'status': 'fail', 'msg': str(e)}), 500

@blueprint.route('/api/shells/statistics', methods=['GET'])
# API: Thống kê tổng quan về shell (tổng số, trạng thái, loại shell)
def shell_statistics():
    """Thống kê shell"""
    try:
        total = ShellConnection.query.count()
        active = ShellConnection.query.filter_by(is_active=True).count()
        closed = ShellConnection.query.filter_by(status=ShellStatus.CLOSED).count()
        listening = ShellConnection.query.filter_by(status=ShellStatus.LISTENING).count()
        connected = ShellConnection.query.filter_by(status=ShellStatus.CONNECTED).count()
        error_count = ShellConnection.query.filter_by(status=ShellStatus.ERROR).count()
        
        # Thống kê theo loại shell
        reverse_count = ShellConnection.query.filter_by(shell_type=ShellType.REVERSE).count()
        bind_count = ShellConnection.query.filter_by(shell_type=ShellType.BIND).count()
        
        return jsonify({
            'status': 'success', 
            'data': {
                'total': total, 
                'active': active, 
                'closed': closed,
                'listening': listening,
                'connected': connected,
                'error': error_count,
                'reverse_shells': reverse_count,
                'bind_shells': bind_count
            }
        })
    except Exception as e:
        logger.error(f"Error getting shell statistics: {e}")
        return jsonify({'status': 'fail', 'msg': str(e)}), 500

@blueprint.route('/api/shells/<shell_id>/note', methods=['POST'])
# API: Cập nhật ghi chú cho shell
def update_shell_note(shell_id):
    """Cập nhật ghi chú cho shell"""
    try:
        data = request.get_json() or {}
        note = data.get('note', '')
        
        conn = ShellConnection.get_by_id(shell_id)
        if not conn:
            return jsonify({'status': 'fail', 'msg': 'Shell not found'}), 404
        
        conn.notes = note
        db.session.commit()
        
        logger.info(f"Updated note for shell {shell_id}")
        return jsonify({'status': 'success', 'msg': 'Note updated successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating note for shell {shell_id}")
        return jsonify({'status': 'fail', 'msg': str(e)}), 500

@blueprint.route('/api/shells/header-stats', methods=['GET'])
# API: Thống kê shell cho header (số lượng tổng, active, listening, connected)
def shell_header_stats():
    """Thống kê shell cho header"""
    try:
        total = ShellConnection.query.count()
        active = ShellConnection.query.filter_by(is_active=True).count()
        listening = ShellConnection.query.filter_by(status=ShellStatus.LISTENING).count()
        connected = ShellConnection.query.filter_by(status=ShellStatus.CONNECTED).count()
        
        return jsonify({
            'status': 'success',
            'data': {
                'total_shells': total,
                'active_shells': active,
                'listening_shells': listening,
                'connected_shells': connected
            }
        })
    except Exception as e:
        logger.error(f"Error getting shell header stats: {e}")
        return jsonify({'status': 'fail', 'msg': str(e)}), 500


## cái này mới thêm sau
@blueprint.route('/api/shells/<shell_id>/link_target', methods=['POST'])
# API: Liên kết shell với target
def link_target(shell_id):
    """Liên kết shell với target"""
    try:
        data = request.get_json() or {}
        target_id = data.get('target_id')
        
        #tim target và shell
        target = Targets.query.filter_by(server_id=target_id).first()
        if not target:
            return jsonify({'status': 'fail', 'msg': 'Target not found'}), 404

        conn = ShellConnection.get_by_id(shell_id)
        if not conn:
            return jsonify({'status': 'fail', 'msg': 'Shell not found'}), 404
        
        #cập nhật target_id và host name
        conn.target_id = target_id
        conn.hostname = target.hostname
        db.session.commit()

        return jsonify({'status': 'success', 'msg': 'Target linked successfully'})
    except Exception as e:
        logger.error(f"Error linking target to shell {shell_id}: {e}")
        return jsonify({'status': 'fail', 'msg': str(e)}), 500

@blueprint.route('/api/shells/<shell_id>/notes', methods=['POST'])
def update_shell_notes(shell_id):
    """ Cập nhật ghi chú cho shell"""
    try:
        data = request.get_json() or {}
        notes = data.get('notes','')

        #tim shell
        conn = ShellConnection.get_by_id(shell_id)
        if not conn:
            return jsonify({'status': 'fail', 'msg': 'Shell not found'}), 404
        
        #cap nhat notes
        conn.notes = notes
        db.session.commit()

        return jsonify({'status': 'success', 'msg': 'Notes updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'fail', 'msg': str(e)}), 500
