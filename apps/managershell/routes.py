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
from apps.models import Targets
import psutil


shell_manager = PwncatManager()

#bắt đầu code từ đây
@blueprint.route('/shells')
def shells():
    """Hàm gửi request tới shell"""
    def get_server_interfaces():
        interfaces = set()
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if getattr(addr, 'family', None) == 2:  # IPv4
                    interfaces.add(addr.address)
        interfaces.update(['0.0.0.0', '127.0.0.1'])
        return sorted(interfaces)

    targets = Targets.query.all()
    interfaces = get_server_interfaces()
    return render_template(
        'shells/index-shell.html',
        segment='index_shell',
        targets=targets,
        interfaces=interfaces
    )



# 1. Danh sách shell (có filter, search, sort)
@blueprint.route('/api/shells', methods=['GET'])
def list_shells():
    """Danh sách shell với phân trang, tìm kiếm, sắp xếp"""
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
        'total_pages': total_pages
    })

# 2. Tạo mới shell (listener/bind)
@blueprint.route('/api/shells', methods=['POST'])
def create_shell():
    data = request.get_json() or {}
    shell_type = data.get('shell_type')
    if not shell_type:
        return jsonify({'status': 'fail', 'msg': 'Missing shell_type'}), 400
    port = data.get('port')
    if port is None:
        return jsonify({'status': 'fail', 'msg': 'Missing port'}), 400
    try:
        port = int(port)
    except (TypeError, ValueError):
        return jsonify({'status': 'fail', 'msg': 'Invalid port'}), 400
    interface = data.get('interface') or '0.0.0.0'
    ip = data.get('ip')
    target_id = data.get('target_id')
    target = Targets.query.get(target_id) if target_id else None
    name = data.get('name') or f'{shell_type}_{uuid.uuid4().hex[:8]}'
    url = data.get('url')

    # Kiểm tra shell đã tồn tại (LISTENING/CONNECTED)
    if shell_type == 'reverse':
        exists = ShellConnection.query.filter_by(
            shell_type=ShellType.REVERSE,
            local_ip=interface,
            local_port=port
        ).filter(
            (ShellConnection.status == ShellStatus.LISTENING) | (ShellConnection.status == ShellStatus.CONNECTED)
        ).first()
        if exists:
            return jsonify({'status': 'fail', 'msg': f'IP {interface}:{port} is already in use for a reverse shell!'}), 400
    elif shell_type == 'bind':
        exists = ShellConnection.query.filter_by(shell_type=ShellType.BIND, remote_ip=ip, remote_port=port).filter(
            (ShellConnection.status == ShellStatus.LISTENING) | (ShellConnection.status == ShellStatus.CONNECTED)
        ).first()
        if exists:
            return jsonify({'status': 'fail', 'msg': f'IP {ip}:{port} is already in use for a bind shell!'}), 400

    # Tạo shell mới trong DB, trạng thái CLOSED (chưa chạy)
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

# 3. Xem chi tiết shell
@blueprint.route('/api/shells/<shell_id>', methods=['GET'])
def get_shell(shell_id):
    conn = ShellConnection.get_by_id(shell_id)
    if not conn:
        return jsonify({'status': 'fail', 'msg': 'Not found'}), 404
    return jsonify({'status': 'success', 'data': conn.to_dict()})

# 4. Gửi lệnh tới shell
@blueprint.route('/api/shells/<shell_id>/command', methods=['POST'])
def send_command(shell_id):
    data = request.get_json() or {}
    command = data.get('command')
    if not command:
        return jsonify({'status': 'fail', 'msg': 'No command'}), 400
    output = shell_manager.send_command(shell_id, command)
    cmd = ShellCommand.create_command(shell_id, command, output=output, success=output is not None)
    return jsonify({'status': 'success', 'data': {'output': output, 'command_id': cmd.command_id}})

# 5. Lấy lịch sử lệnh
@blueprint.route('/api/shells/<shell_id>/history', methods=['GET'])
def shell_history(shell_id):
    limit = int(request.args.get('limit', 50))
    cmds = ShellCommand.get_by_connection(shell_id, limit=limit)
    return jsonify({'status': 'success', 'data': [c.to_dict() for c in cmds]})

# 6. Đóng shell
@blueprint.route('/api/shells/<shell_id>/close', methods=['POST'])
def close_shell(shell_id):
    ok = shell_manager.close_shell(shell_id)
    conn = ShellConnection.get_by_id(shell_id)
    if conn:
        conn.update_status(ShellStatus.CLOSED)
    return jsonify({'status': 'success' if ok else 'fail'})

# 7. action shell:  thực hiện khởi động và đóng mấy con shell lại
@blueprint.route('/api/shells/<shell_id>/start', methods=['POST'])
def action_shell(shell_id):
    try:
        conn = ShellConnection.get_by_id(shell_id)
        if not conn:
            return jsonify({'status': 'fail', 'msg': 'Not found'}), 404

        shell_type = conn.shell_type
        port = conn.local_port if shell_type == ShellType.REVERSE else conn.remote_port
        name = conn.name
        url = conn.url
        interface = conn.local_ip if shell_type == ShellType.REVERSE else None
        ip = conn.remote_ip if shell_type == ShellType.BIND else None

        # Khởi động shell
        if shell_type == ShellType.REVERSE:
            new_shell_id = shell_manager.start_listener(port, name=name, url=url, listen_ip=str(interface))
        elif shell_type == ShellType.BIND:
            new_shell_id = shell_manager.connect_shell(ip, port, name=name, url=url)
        else:
            return jsonify({'status': 'fail', 'msg': 'Invalid shell_type'}), 400

        if not new_shell_id:
            return jsonify({'status': 'fail', 'msg': 'Failed to start shell'}), 500

        # Cập nhật trạng thái
        conn.update_status(ShellStatus.LISTENING if shell_type == ShellType.REVERSE else ShellStatus.CONNECTED)
        return jsonify({'status': 'success'})

    except Exception as e:
        return jsonify({'status': 'fail', 'msg': str(e)})

# 8. Upload file
@blueprint.route('/api/shells/<shell_id>/upload', methods=['POST'])
def upload_file(shell_id):
    data = request.get_json() or {}
    local_path = data.get('local_path')
    remote_path = data.get('remote_path')
    ok = shell_manager.upload_file(shell_id, local_path, remote_path)
    return jsonify({'status': 'success' if ok else 'fail'})

# 9. Download file
@blueprint.route('/api/shells/<shell_id>/download', methods=['POST'])
def download_file(shell_id):
    data = request.get_json() or {}
    remote_path = data.get('remote_path')
    local_path = data.get('local_path')
    ok = shell_manager.download_file(shell_id, remote_path, local_path)
    return jsonify({'status': 'success' if ok else 'fail'})

# 10. Privilege escalation
@blueprint.route('/api/shells/<shell_id>/escalate', methods=['POST'])
def escalate(shell_id):
    data = request.get_json() or {}
    user = data.get('user')
    ok = shell_manager.escalate_privilege(shell_id, user)
    return jsonify({'status': 'success' if ok else 'fail'})

# 11. Thống kê
@blueprint.route('/api/shells/statistics', methods=['GET'])
def shell_stats():
    total = ShellConnection.query.count()
    active = ShellConnection.query.filter_by(is_active=True).count()
    closed = ShellConnection.query.filter_by(status=ShellStatus.CLOSED).count()
    return jsonify({'status': 'success', 'data': {'total': total, 'active': active, 'closed': closed}})

# 12. Ghi chú cho shell
@blueprint.route('/api/shells/<shell_id>/note', methods=['POST'])
def update_note(shell_id):
    data = request.get_json() or {}
    note = data.get('note')
    conn = ShellConnection.get_by_id(shell_id)
    if not conn:
        return jsonify({'status': 'fail', 'msg': 'Not found'}), 404
    conn.notes = note
    db.session.commit()
    return jsonify({'status': 'success'})
