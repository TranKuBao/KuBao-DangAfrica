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

blueprint = Blueprint('managershell', __name__)
shell_manager = PwncatManager()

# 1. Danh sách shell (có filter, search, sort)
@blueprint.route('/api/shells', methods=['GET'])
@login_required
def list_shells():
    query = ShellConnection.query
    # Filter
    status = request.args.get('status')
    shell_type = request.args.get('shell_type')
    target_id = request.args.get('target_id')
    search = request.args.get('search')
    sort = request.args.get('sort', 'last_active')
    order = request.args.get('order', 'desc')
    if status:
        query = query.filter_by(status=status)
    if shell_type:
        query = query.filter_by(shell_type=shell_type)
    if target_id:
        query = query.filter_by(target_id=target_id)
    if search:
        query = query.filter(ShellConnection.name.ilike(f'%{search}%'))
    # Sort
    if hasattr(ShellConnection, sort):
        if order == 'desc':
            query = query.order_by(getattr(ShellConnection, sort).desc())
        else:
            query = query.order_by(getattr(ShellConnection, sort).asc())
    shells = query.all()
    return jsonify({'status': 'success', 'data': [s.to_dict() for s in shells]})

# 2. Tạo mới shell (listener/bind)
@blueprint.route('/api/shells', methods=['POST'])
@login_required
def create_shell():
    data = request.json
    shell_type = data.get('shell_type')
    port = data.get('port')
    target_id = data.get('target_id')
    target = Targets.query.get(target_id) if target_id else None
    name = data.get('name') or f'{shell_type}_{uuid.uuid4().hex[:8]}'
    url = data.get('url')
    # Tạo shell
    if shell_type == 'reverse':
        shell_id = shell_manager.start_listener(port, name=name, url=url)
    elif shell_type == 'bind':
        ip = data.get('ip') or (target.ip_address if target else None)
        shell_id = shell_manager.connect_shell(ip, port, name=name, url=url)
    else:
        return jsonify({'status': 'fail', 'msg': 'Invalid shell_type'}), 400
    if not shell_id:
        return jsonify({'status': 'fail', 'msg': 'Failed to create shell'}), 500
    # Lưu DB
    conn = ShellConnection.create_connection(
        connection_id=shell_id,
        name=name,
        shell_type=ShellType.REVERSE if shell_type=='reverse' else ShellType.BIND,
        local_port=port if shell_type=='reverse' else None,
        remote_ip=ip if shell_type=='bind' else None,
        remote_port=port if shell_type=='bind' else None,
        target_id=target_id,
        hostname=target.hostname if target else None,
        url=url
    )
    return jsonify({'status': 'success', 'data': conn.to_dict()})

# 3. Xem chi tiết shell
@blueprint.route('/api/shells/<shell_id>', methods=['GET'])
@login_required
def get_shell(shell_id):
    conn = ShellConnection.get_by_id(shell_id)
    if not conn:
        return jsonify({'status': 'fail', 'msg': 'Not found'}), 404
    return jsonify({'status': 'success', 'data': conn.to_dict()})

# 4. Gửi lệnh tới shell
@blueprint.route('/api/shells/<shell_id>/command', methods=['POST'])
@login_required
def send_command(shell_id):
    data = request.json
    command = data.get('command')
    if not command:
        return jsonify({'status': 'fail', 'msg': 'No command'}), 400
    output = shell_manager.send_command(shell_id, command)
    cmd = ShellCommand.create_command(shell_id, command, output=output, success=output is not None)
    return jsonify({'status': 'success', 'data': {'output': output, 'command_id': cmd.command_id}})

# 5. Lấy lịch sử lệnh
@blueprint.route('/api/shells/<shell_id>/history', methods=['GET'])
@login_required
def shell_history(shell_id):
    limit = int(request.args.get('limit', 50))
    cmds = ShellCommand.get_by_connection(shell_id, limit=limit)
    return jsonify({'status': 'success', 'data': [c.to_dict() for c in cmds]})

# 6. Đóng shell
@blueprint.route('/api/shells/<shell_id>/close', methods=['POST'])
@login_required
def close_shell(shell_id):
    ok = shell_manager.close_shell(shell_id)
    conn = ShellConnection.get_by_id(shell_id)
    if conn:
        conn.update_status(ShellStatus.CLOSED)
    return jsonify({'status': 'success' if ok else 'fail'})

# 7. Xóa shell
@blueprint.route('/api/shells/<shell_id>', methods=['DELETE'])
@login_required
def delete_shell(shell_id):
    conn = ShellConnection.get_by_id(shell_id)
    if not conn:
        return jsonify({'status': 'fail', 'msg': 'Not found'}), 404
    shell_manager.close_shell(shell_id)
    conn.delete()
    return jsonify({'status': 'success'})

# 8. Upload file
@blueprint.route('/api/shells/<shell_id>/upload', methods=['POST'])
@login_required
def upload_file(shell_id):
    data = request.json
    local_path = data.get('local_path')
    remote_path = data.get('remote_path')
    ok = shell_manager.upload_file(shell_id, local_path, remote_path)
    return jsonify({'status': 'success' if ok else 'fail'})

# 9. Download file
@blueprint.route('/api/shells/<shell_id>/download', methods=['POST'])
@login_required
def download_file(shell_id):
    data = request.json
    remote_path = data.get('remote_path')
    local_path = data.get('local_path')
    ok = shell_manager.download_file(shell_id, remote_path, local_path)
    return jsonify({'status': 'success' if ok else 'fail'})

# 10. Privilege escalation
@blueprint.route('/api/shells/<shell_id>/escalate', methods=['POST'])
@login_required
def escalate(shell_id):
    data = request.json
    user = data.get('user')
    ok = shell_manager.escalate_privilege(shell_id, user)
    return jsonify({'status': 'success' if ok else 'fail'})

# 11. Thống kê
@blueprint.route('/api/shells/statistics', methods=['GET'])
@login_required
def shell_stats():
    total = ShellConnection.query.count()
    active = ShellConnection.query.filter_by(is_active=True).count()
    closed = ShellConnection.query.filter_by(status=ShellStatus.CLOSED).count()
    return jsonify({'status': 'success', 'data': {'total': total, 'active': active, 'closed': closed}})

# 12. Ghi chú cho shell
@blueprint.route('/api/shells/<shell_id>/note', methods=['POST'])
@login_required
def update_note(shell_id):
    data = request.json
    note = data.get('note')
    conn = ShellConnection.get_by_id(shell_id)
    if not conn:
        return jsonify({'status': 'fail', 'msg': 'Not found'}), 404
    conn.notes = note
    db.session.commit()
    return jsonify({'status': 'success'})
