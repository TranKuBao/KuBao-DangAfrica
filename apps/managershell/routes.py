# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import datetime as dt
from apps.managershell import blueprint
from apps import db
from apps.models import Targets, VerificationResults
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
import uuid
import psutil
import logging

from flask_socketio import SocketIO
from apps import socketio

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lazy import shell_manager để tránh circular dependency
def get_shell_manager():
    from apps import shell_manager
    return shell_manager

# Thiết lập socketio cho shell_manager (sẽ được gọi sau khi app khởi tạo)
def setup_shell_manager():
    shell_manager = get_shell_manager()
    shell_manager.socketio = socketio

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
def view_shell(shell_id):
    """Trang xem chi tiết shell và tương tác"""
    try:
        shell = ShellConnection.get_by_id(shell_id)
        if not shell:
            return render_template('error/404.html'), 404
        
        # Lấy tất cả targets cho dropdown
        targets = Targets.query.all()
        
        return render_template(
            'shells/view-shell.html',
            segment='view_shell',
            shell_id=shell_id,
            shell_name=shell.name,
            shell=shell,
            targets=targets  # QUAN TRỌNG: Thêm targets vào context
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
        
        interface = data.get('interface') or '0.0.0.0'
        ip = data.get('ip')
        target_id = data.get('target_id')
        name = data.get('name')
        url = data.get('url')

        result, status = handle_create_shell(
            shell_type=shell_type,
            port=port,
            interface=interface,
            ip=ip,
            target_id=target_id,
            name=name,
            url=url
        )

        return jsonify(result), status

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({'status': 'fail', 'msg': str(e)}), 500

# hàm xử lý tạo shell, tách riêng để dễ quản lý khi api được gọi xong
def handle_create_shell(shell_type, port, interface='0.0.0.0', ip=None, target_id=None, name=None, url=None):
    try:
        port = int(port)
        if port < 1 or port > 65535:
            return {'status': 'fail', 'msg': 'Port must be between 1 and 65535'}, 400
    except (TypeError, ValueError):
        return {'status': 'fail', 'msg': 'Invalid port'}, 400

    target = Targets.query.get(target_id) if target_id else None
    name = name or f'{shell_type}_{uuid.uuid4().hex[:8]}'

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
            return {
                'status': 'fail', 
                'msg': f'IP {interface}:{port} is already in use for a reverse shell!'
            }, 400

    elif shell_type == 'bind':
        if not ip:
            return {'status': 'fail', 'msg': 'Missing IP for bind shell'}, 400

        exists = ShellConnection.query.filter_by(
            shell_type=ShellType.BIND, 
            remote_ip=ip, 
            remote_port=port
        ).filter(
            (ShellConnection.status == ShellStatus.LISTENING) | 
            (ShellConnection.status == ShellStatus.CONNECTED)
        ).first()
        if exists:
            return {
                'status': 'fail', 
                'msg': f'IP {ip}:{port} is already in use for a bind shell!'
            }, 400

    try:
        conn = ShellConnection(
            connection_id=str(uuid.uuid4()),
            name=name,
            shell_type=ShellType.REVERSE if shell_type == 'reverse' else ShellType.BIND,
            local_ip=interface if shell_type == 'reverse' else None,
            local_port=port if shell_type == 'reverse' else None,
            remote_ip=ip if shell_type == 'bind' else None,
            remote_port=port if shell_type == 'bind' else None,
            target_id=target_id,
            hostname=target.hostname if target else None,
            url=url
        )
        conn.status = ShellStatus.CLOSED
        db.session.add(conn)
        db.session.commit()

        return {'status': 'success', 'data': conn.to_dict()}, 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating shell: {e}")
        return {'status': 'fail', 'msg': str(e)}, 500



@blueprint.route('/api/shells/<shell_id>', methods=['GET'])
# API: Xem chi tiết một shell
def get_shell(shell_id):
    """Lấy thông tin chi tiết shell"""
    try:
        shell = ShellConnection.get_by_id(shell_id)
        if not shell:
            return jsonify({'status': 'fail', 'msg': 'Shell not found'}), 404
        
        logger.info(f"[DEBUG] Getting shell {shell_id} status: {shell.status}")
        
        return jsonify({
            'status': 'success',
            'data': {
                'connection_id': shell.connection_id,
                'shell_type': shell.shell_type.value if hasattr(shell.shell_type, 'value') else str(shell.shell_type),
                'status': shell.status.value if hasattr(shell.status, 'value') else str(shell.status),
                'local_ip': shell.local_ip,
                'local_port': shell.local_port,
                'remote_ip': shell.remote_ip,
                'remote_port': shell.remote_port,
                'user': shell.user,
                'privilege_level': shell.privilege_level,
                'hostname': shell.hostname,
                'notes': shell.notes,
                'created_at': shell.created_at.isoformat() if shell.created_at else None,
                'updated_at': shell.updated_at.isoformat() if shell.updated_at else None
            }
        })
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
        
        # Gửi lệnh vào shell qua PTY (output sẽ được gửi qua socket tự động)
        success = get_shell_manager().send_input_to_shell(shell_id, command + '\n')
        
        # Lưu lệnh vào database
        cmd = ShellCommand.create_command(shell_id, command, output="", success=success)

        logger.info(f"Command sent to shell {shell_id}: {command}")
        return jsonify({
            'status': 'success' if success else 'fail', 
            'data': {
                'command_id': cmd.command_id,
                'success': success,
                'message': 'Command sent via PTY, output will be received via socket'
            }
        })
    except Exception as e:
        logger.error(f"Error sending command to shell {shell_id}: {e}")

        # test socketio 
        socketio.emit('shell_status_update', {
            'shell_id': shell_id,
            'status': 'ERROR'
        }, room=shell_id)

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

@blueprint.route('/api/shells/create-sample', methods=['POST'])
# API: Tạo shell mẫu để test
def create_sample_shell():
    """Tạo shell mẫu để test"""
    try:
        # Tạo shell reverse mẫu
        shell_id = str(uuid.uuid4())
        sample_shell = ShellConnection(
            connection_id=shell_id,
            name='Test Reverse Shell',
            shell_type=ShellType.REVERSE,
            local_ip='0.0.0.0',
            local_port=4444,
            status=ShellStatus.CLOSED
        )
        
        db.session.add(sample_shell)
        db.session.commit()
        
        logger.info(f"Created sample shell: {shell_id}")
        return jsonify({
            'status': 'success', 
            'msg': 'Sample shell created',
            'shell_id': shell_id
        })
    except Exception as e:
        logger.error(f"Error creating sample shell: {e}")
        db.session.rollback()
        return jsonify({'status': 'fail', 'msg': str(e)}), 500

@blueprint.route('/api/shells/list-all', methods=['GET'])
# API: Liệt kê tất cả shell trong database
def list_all_shells():
    """Liệt kê tất cả shell trong database"""
    try:
        shells = ShellConnection.query.all()
        shell_list = []
        for shell in shells:
            shell_list.append({
                'connection_id': shell.connection_id,
                'name': shell.name,
                'shell_type': str(shell.shell_type),
                'shell_type_value': shell.shell_type.value if hasattr(shell.shell_type, 'value') else None,
                'status': str(shell.status),
                'status_value': shell.status.value if hasattr(shell.status, 'value') else None,
                'local_ip': shell.local_ip,
                'local_port': shell.local_port,
                'remote_ip': shell.remote_ip,
                'remote_port': shell.remote_port,
                'created_at': shell.created_at.isoformat() if shell.created_at else None
            })
        
        return jsonify({
            'status': 'success',
            'count': len(shell_list),
            'shells': shell_list
        })
    except Exception as e:
        logger.error(f"Error listing all shells: {e}")
        return jsonify({'status': 'fail', 'msg': str(e)}), 500

@blueprint.route('/api/shells/<shell_id>/debug', methods=['GET'])
# API: Debug thông tin shell
def debug_shell(shell_id):
    """Debug thông tin shell"""
    try:
        conn = ShellConnection.get_by_id(shell_id)
        if not conn:
            return jsonify({'status': 'fail', 'msg': 'Shell not found'}), 404
        
        debug_info = {
            'connection_id': conn.connection_id,
            'name': conn.name,
            'shell_type': str(conn.shell_type),
            'shell_type_value': conn.shell_type.value if hasattr(conn.shell_type, 'value') else None,
            'status': str(conn.status),
            'status_value': conn.status.value if hasattr(conn.status, 'value') else None,
            'local_ip': conn.local_ip,
            'local_port': conn.local_port,
            'remote_ip': conn.remote_ip,
            'remote_port': conn.remote_port,
            'target_id': conn.target_id,
            'hostname': conn.hostname,
            'url': conn.url,
            'created_at': conn.created_at.isoformat() if conn.created_at else None,
            'updated_at': conn.updated_at.isoformat() if conn.updated_at else None
        }
        
        return jsonify({'status': 'success', 'data': debug_info})
    except Exception as e:
        logger.error(f"Error debugging shell {shell_id}: {e}")
        return jsonify({'status': 'fail', 'msg': str(e)}), 500

# Thêm function riêng để khởi động shell (không phải API endpoint)
def start_shell_function(shell_id):
    """Function để khởi động shell (không phải API endpoint)"""
    try:
        conn = ShellConnection.get_by_id(shell_id)
        if not conn:
            print(f"Shell {shell_id} not found in database")
            return False

        if conn.status in [ShellStatus.LISTENING, ShellStatus.CONNECTED]:
            print(f"Shell {shell_id} is already running with status {conn.status}")
            return True  # Đã chạy rồi thì coi như thành công

        # Debug: Log thông tin shell để kiểm tra
        print(f"Starting shell {shell_id}: type={conn.shell_type}, status={conn.status}")
        
        # Sửa: Lấy shell_type dạng string và so sánh chính xác
        shell_type = conn.shell_type.value if hasattr(conn.shell_type, 'value') else str(conn.shell_type)
        shell_type = shell_type.lower()
        
        print(f"Shell type after processing: {shell_type}")
        
        # Kiểm tra shell_type hợp lệ
        if shell_type not in ['reverse', 'bind']:
            print(f"Invalid shell type: {shell_type}")
            return False
        
        port = conn.local_port if shell_type == 'reverse' else conn.remote_port
        name = conn.name
        url = conn.url
        # Sửa: interface luôn là '0.0.0.0' cho reverse, không cần chọn giao diện
        interface = '0.0.0.0' if shell_type == 'reverse' else None
        ip = conn.remote_ip if shell_type == 'bind' else None

        print(f"Starting {shell_type} shell: port={port}, ip={ip}, interface={interface}")

        # Khởi động shell trong pwncat manager
        if shell_type == 'reverse':
            new_shell_id = get_shell_manager().start_listener(port, name=conn.connection_id, url=url, listen_ip=interface)
        elif shell_type == 'bind':
            new_shell_id = get_shell_manager().connect_shell(ip, port, name=conn.connection_id, url=url)
        else:
            return False

        if not new_shell_id:
            print(f"Failed to start shell {shell_id} - shell_manager returned None")
            return False

        # Cập nhật trạng thái trong database (backup)
        new_status = ShellStatus.LISTENING if shell_type == 'reverse' else ShellStatus.CONNECTED
        conn.update_status(new_status)
        
        # Đảm bảo database được commit
        db.session.commit()
        print(f"Updated shell {shell_id} status to {new_status} in database")

        # Emit socket event để cập nhật realtime
        try:
            from flask_socketio import emit
            emit('shell_status_update', {
                'shell_id': shell_id,
                'status': new_status.name,
                'timestamp': dt.datetime.utcnow().isoformat()
            }, room=shell_id, namespace='/')
        except Exception as e:
            logger.warning(f"Failed to emit socket event: {e}")
        
        print(f"Started shell {shell_id} with status {new_status}")
        return True

    except Exception as e:
        print(f"Error starting shell {shell_id}: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

@blueprint.route('/api/shells/<shell_id>/start', methods=['POST'])
# API: Khởi động shell (listener hoặc bind)
def start_shell(shell_id):
    """Khởi động shell - API endpoint"""
    success = start_shell_function(shell_id)
    
    if success:
        return jsonify({'status': 'success', 'msg': f'Shell started successfully'})
    else:
        return jsonify({'status': 'fail', 'msg': 'Failed to start shell'}), 500

@blueprint.route('/api/shells/<shell_id>/close', methods=['POST'])
def close_shell(shell_id):
    """API: Đóng shell (có thể được gọi từ beforeunload)"""
    try:
        # Lấy thông tin shell
        shell = ShellConnection.get_by_id(shell_id)
        if not shell:
            return jsonify({
                'status': 'error',
                'message': f'Shell {shell_id} not found'
            }), 404
        
        # Kiểm tra action từ request
        action = request.form.get('action') or request.json.get('action', 'normal')
        
        logger.info(f"Closing shell {shell_id} (action: {action})")
        
        # Nếu là close_completely, đóng shell hoàn toàn
        if action == 'close_completely':
            # Đóng shell trong manager
            success = get_shell_manager().close_shell(shell_id)
            
            if success:
                # Cập nhật trạng thái trong database
                shell.status = ShellStatus.CLOSED
                shell.updated_at = dt.datetime.utcnow()
                db.session.commit()
                logger.info(f"Shell {shell_id} closed completely")
                
                # Emit socket event để cập nhật realtime
                try:
                    from flask_socketio import emit
                    emit('shell_status_update', {
                        'shell_id': shell_id,
                        'status': 'CLOSED',
                        'timestamp': dt.datetime.utcnow().isoformat()
                    }, room=shell_id, namespace='/')
                except Exception as e:
                    logger.warning(f"Failed to emit socket event: {e}")
                
                return jsonify({
                    'status': 'success',
                    'message': f'Shell {shell_id} closed completely',
                    'action': action
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'Failed to close shell {shell_id} completely'
                }), 500
        
        # Đóng shell trong manager (action bình thường)
        success = get_shell_manager().close_shell(shell_id)
        
        if success:
            # Cập nhật trạng thái trong database (backup)
            shell.status = ShellStatus.CLOSED
            shell.updated_at = dt.datetime.utcnow()
            db.session.commit()
            logger.info(f"Updated shell {shell_id} status to CLOSED in database")
            
            # Emit socket event để cập nhật realtime
            try:
                from flask_socketio import emit
                emit('shell_status_update', {
                    'shell_id': shell_id,
                    'status': 'CLOSED',
                    'timestamp': dt.datetime.utcnow().isoformat()
                }, room=shell_id, namespace='/')
            except Exception as e:
                logger.warning(f"Failed to emit socket event: {e}")
            
            return jsonify({
                'status': 'success',
                'message': f'Shell {shell_id} closed successfully',
                'action': action
            })
        else:
            # Nếu shell manager không đóng được, vẫn cập nhật database
            shell.status = ShellStatus.CLOSED
            shell.updated_at = dt.datetime.utcnow()
            db.session.commit()
            logger.warning(f"Shell manager failed to close {shell_id}, but updated database status")
            
            return jsonify({
                'status': 'success',
                'message': f'Shell {shell_id} marked as closed',
                'action': action
            })
            
    except Exception as e:
        logger.error(f"Error closing shell {shell_id}: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error closing shell: {str(e)}'
        }), 500

@blueprint.route('/api/shells/<shell_id>', methods=['DELETE'])
# API: Xóa shell khỏi hệ thống
def delete_shell(shell_id):
    """Xóa shell"""
    try:
        conn = ShellConnection.get_by_id(shell_id)
        if not conn:
            return jsonify({'status': 'fail', 'msg': 'Shell not found'}), 404
        
        # Đảm bảo process shell bị kill nếu còn
        get_shell_manager().close_shell(shell_id)
        
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
        
        ok = get_shell_manager().upload_file(shell_id, local_path, remote_path)
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
        
        ok = get_shell_manager().download_file(shell_id, remote_path, local_path)
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
        
        ok = get_shell_manager().escalate_privilege(shell_id, user)
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

@blueprint.route('/api/shells/<shell_id>/sync-status', methods=['POST'])
def sync_shell_status(shell_id):
    """API: Đồng bộ trạng thái shell giữa manager và database"""
    try:
        # Lấy thông tin shell từ database
        shell = ShellConnection.get_by_id(shell_id)
        if not shell:
            return jsonify({
                'status': 'error',
                'message': f'Shell {shell_id} not found'
            }), 404
        
        # Kiểm tra trạng thái trong shell manager
        shell_info = get_shell_manager().shells.get(shell_id)
        
        if shell_info:
            # Shell đang chạy trong manager
            manager_status = shell_info.get('status', 'unknown')
            logger.info(f"Shell {shell_id} status in manager: {manager_status}")
            
            # Cập nhật database theo trạng thái manager
            if manager_status == 'listening':
                shell.status = ShellStatus.LISTENING
            elif manager_status == 'connected':
                shell.status = ShellStatus.CONNECTED
            elif manager_status == 'closed':
                shell.status = ShellStatus.CLOSED
            elif manager_status == 'disconnected':
                shell.status = ShellStatus.DISCONNECTED
            else:
                shell.status = ShellStatus.ERROR
            
            shell.updated_at = dt.datetime.utcnow()
            db.session.commit()
            
            logger.info(f"Synced shell {shell_id} status to {shell.status}")
            
            return jsonify({
                'status': 'success',
                'message': f'Shell status synced: {shell.status}',
                'manager_status': manager_status,
                'database_status': shell.status.name
            })
        else:
            # Shell không có trong manager, đánh dấu là CLOSED
            shell.status = ShellStatus.CLOSED
            shell.updated_at = dt.datetime.utcnow()
            db.session.commit()
            
            logger.info(f"Shell {shell_id} not found in manager, marked as CLOSED")
            
            return jsonify({
                'status': 'success',
                'message': 'Shell not found in manager, marked as CLOSED',
                'manager_status': 'not_found',
                'database_status': 'CLOSED'
            })
            
    except Exception as e:
        logger.error(f"Error syncing shell status {shell_id}: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error syncing shell status: {str(e)}'
        }), 500

@blueprint.route('/api/shells/sync-all-status', methods=['POST'])
def sync_all_shell_status():
    """API: Đồng bộ trạng thái tất cả shell"""
    try:
        # Lấy tất cả shell từ database
        shells = ShellConnection.query.all()
        synced_count = 0
        errors = []
        
        for shell in shells:
            try:
                shell_id = shell.connection_id
                shell_info = get_shell_manager().shells.get(shell_id)
                
                if shell_info:
                    # Shell đang chạy trong manager
                    manager_status = shell_info.get('status', 'unknown')
                    
                    # Cập nhật database theo trạng thái manager
                    if manager_status == 'listening':
                        shell.status = ShellStatus.LISTENING
                    elif manager_status == 'connected':
                        shell.status = ShellStatus.CONNECTED
                    elif manager_status == 'closed':
                        shell.status = ShellStatus.CLOSED
                    elif manager_status == 'disconnected':
                        shell.status = ShellStatus.DISCONNECTED
                    else:
                        shell.status = ShellStatus.ERROR
                    
                    shell.updated_at = dt.datetime.utcnow()
                    synced_count += 1
                    
                else:
                    # Shell không có trong manager, đánh dấu là CLOSED
                    shell.status = ShellStatus.CLOSED
                    shell.updated_at = dt.datetime.utcnow()
                    synced_count += 1
                    
            except Exception as e:
                errors.append(f"Error syncing shell {shell.connection_id}: {str(e)}")
        
        # Commit tất cả thay đổi
        db.session.commit()
        
        logger.info(f"Synced {synced_count} shells, {len(errors)} errors")
        
        return jsonify({
            'status': 'success',
            'message': f'Synced {synced_count} shells',
            'synced_count': synced_count,
            'errors': errors
        })
        
    except Exception as e:
        logger.error(f"Error syncing all shell status: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error syncing all shell status: {str(e)}'
        }), 500

@blueprint.route('/api/shells/debug-status', methods=['GET'])
def debug_shell_status():
    """Debug API để kiểm tra trạng thái shell"""
    try:
        # Lấy tất cả shell từ database
        db_shells = ShellConnection.query.all()
        db_shell_info = []
        for shell in db_shells:
            db_shell_info.append({
                'connection_id': shell.connection_id,
                'name': shell.name,
                'status': shell.status.value if shell.status else None,
                'local_ip': shell.local_ip,
                'local_port': shell.local_port,
                'created_at': shell.created_at.isoformat() if shell.created_at else None
            })
        
        # Lấy shell từ memory
        shell_manager = get_shell_manager()
        memory_shells = {}
        with shell_manager.lock:
            for shell_id, info in shell_manager.shells.items():
                memory_shells[shell_id] = {
                    'status': info.get('status'),
                    'type': info.get('type'),
                    'port': info.get('port'),
                    'ip': info.get('ip'),
                    'last_active': info.get('last_active')
                }
        
        return jsonify({
            'status': 'success',
            'database_shells': db_shell_info,
            'memory_shells': memory_shells,
            'total_db_shells': len(db_shell_info),
            'total_memory_shells': len(memory_shells)
        })
        
    except Exception as e:
        logger.error(f"Error in debug_shell_status: {e}")
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@blueprint.route('/api/shells/<shell_id>/force-sync', methods=['POST'])
def force_sync_shell_status(shell_id):
    """Force sync shell status từ memory về database"""
    try:
        print(f"[DEBUG] Force sync requested for shell: {shell_id}")
        
        # Lấy shell từ database
        shell = ShellConnection.get_by_id(shell_id)
        if not shell:
            print(f"[DEBUG] Shell {shell_id} not found in database")
            return jsonify({'status': 'fail', 'msg': 'Shell not found'}), 404
        
        print(f"[DEBUG] Found shell in database: {shell.connection_id}, status: {shell.status}")
        
        # Lấy status từ memory
        shell_manager = get_shell_manager()
        with shell_manager.lock:
            shell_info = shell_manager.shells.get(shell_id)
        
        if shell_info:
            memory_status = shell_info.get('status', 'unknown')
            print(f"[DEBUG] Shell {shell_id} memory status: {memory_status}")
            
            # Map memory status to database status
            status_mapping = {
                'listening': ShellStatus.LISTENING,
                'connected': ShellStatus.CONNECTED,
                'closed': ShellStatus.CLOSED,
                'disconnected': ShellStatus.DISCONNECTED,
                'error': ShellStatus.ERROR
            }
            
            if memory_status in status_mapping:
                shell.status = status_mapping[memory_status]
                shell.updated_at = dt.datetime.utcnow()
                db.session.commit()
                print(f"[DEBUG] Updated shell {shell_id} status to {memory_status} in database")
                
                # Emit socket event
                try:
                    from flask import current_app
                    from flask_socketio import emit
                    
                    with current_app.app_context():
                        emit('shell_status_update', {
                            'shell_id': shell_id,
                            'status': memory_status.upper(),
                            'timestamp': dt.datetime.utcnow().isoformat()
                        }, room=shell_id, namespace='/')
                    print(f"[DEBUG] Emitted shell status update for {shell_id}")
                except Exception as e:
                    print(f"[WARNING] Failed to emit socket event: {e}")
                
                return jsonify({
                    'status': 'success',
                    'msg': f'Shell status synced to {memory_status}',
                    'memory_status': memory_status,
                    'database_status': shell.status.name
                })
            else:
                return jsonify({
                    'status': 'fail',
                    'msg': f'Unknown memory status: {memory_status}'
                }), 400
        else:
            print(f"[DEBUG] Shell {shell_id} not found in memory, updating database status to CLOSED")
            
            # Nếu shell không có trong memory, đánh dấu là CLOSED
            shell.status = ShellStatus.CLOSED
            shell.updated_at = dt.datetime.utcnow()
            db.session.commit()
            
            # Emit socket event
            try:
                from flask import current_app
                from flask_socketio import emit
                
                with current_app.app_context():
                    emit('shell_status_update', {
                        'shell_id': shell_id,
                        'status': 'CLOSED',
                        'timestamp': dt.datetime.utcnow().isoformat()
                    }, room=shell_id, namespace='/')
                print(f"[DEBUG] Emitted shell status update for {shell_id}")
            except Exception as e:
                print(f"[WARNING] Failed to emit socket event: {e}")
            
            return jsonify({
                'status': 'success',
                'msg': 'Shell not found in memory, marked as CLOSED',
                'memory_status': 'not_found',
                'database_status': 'CLOSED'
            })
            
    except Exception as e:
        logger.error(f"Error force syncing shell {shell_id}: {e}")
        return jsonify({'status': 'fail', 'msg': str(e)}), 500
