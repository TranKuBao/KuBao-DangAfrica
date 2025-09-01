# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from apps.dashboard import blueprint
from flask import render_template, jsonify
from apps.models import Product, Targets, ShellStatus, ShellConnection, DataFile
from pocsuite3.lib.core.interpreter import PocsuiteInterpreter
from sqlalchemy import func, desc, asc
import datetime as dt
import os
import re
from collections import defaultdict
from apps import db


poc_core = PocsuiteInterpreter()

@blueprint.route('/')
def dashboard_stats():
    """Render dashboard page"""
    return render_template('pages/dashboard.html', segment='dashboard_stats')

@blueprint.route('/header_statictical', methods=['GET'])
def charts():
    
    try: 
        #Số POC
        listModules = poc_core.get_all_modules()
        total_POC = len(listModules)
        
        # số target
        listTarget = Targets.query.all()
        total_target = len(listTarget)
        
        # Só data stolen => đếm từ csdl
        listDataFile = DataFile.query.all()
        total_DataStolen = len(listDataFile)

        # Connection 
        listShellConnection = ShellConnection.query.all()
        total_ShellConnection = len(listShellConnection)
        
        return jsonify({
            'total_POC': total_POC,
            'total_target': total_target,
            'total_DataStolen': total_DataStolen,
            'total_ShellConnection': total_ShellConnection
        })
    except Exception as e:
        print(f"Error in charts: {e}")
        return jsonify({
            'total_POC': 0,
            'total_target': 0,
            'total_DataStolen': 0,
            'total_ShellConnection': 0,
            'error': str(e)
        })

@blueprint.route('/dashboard_stats', methods=['GET'])
def dashboard_sumary():
    """Endpoint chính cho dashboard thống kê chi tiết"""
    try:
        # 1. Thống kê POC theo loại
        poc_stats = get_poc_statistics()
        
        # 2. Thống kê Shell Connections
        shell_stats = get_shell_statistics()
        
        # 3. Thống kê Targets
        target_stats = get_target_statistics()
        
        # 4. Thống kê Data Files
        data_stats = get_data_statistics()
        
        # 5. Thống kê theo thời gian
        time_stats = get_time_based_statistics()
        
        # 6. Log đặc biệt
        special_logs = get_special_logs()
        
        return jsonify({
            'poc_statistics': poc_stats,
            'shell_statistics': shell_stats,
            'target_statistics': target_stats,
            'data_statistics': data_stats,
            'time_statistics': time_stats,
            'special_logs': special_logs,
            'status': 'success'
        })
    except Exception as e:
        print(f"Error in dashboard_stats: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

def get_poc_statistics():
    """Thống kê POC theo loại và CVE"""
    try:
        # Lấy danh sách tất cả POC
        all_modules = poc_core.get_all_modules()
        
        # Phân loại POC theo technology
        poc_categories = defaultdict(int)
        cve_stats = defaultdict(int)
        recent_pocs = []
        
        for module in all_modules:
            module_name = module.get('name', '')
            
            # Phân loại theo technology
            if 'wordpress' in module_name.lower():
                poc_categories['WordPress'] += 1
            elif 'apache' in module_name.lower() or 'struts' in module_name.lower():
                poc_categories['Apache/Struts'] += 1
            elif 'weblogic' in module_name.lower():
                poc_categories['WebLogic'] += 1
            elif 'confluence' in module_name.lower():
                poc_categories['Confluence'] += 1
            elif 'spip' in module_name.lower():
                poc_categories['SPIP'] += 1
            else:
                poc_categories['Other'] += 1
            
            # Thống kê CVE
            cve_match = re.search(r'CVE-\d{4}-\d+', module_name, re.IGNORECASE)
            if cve_match:
                cve_stats[cve_match.group()] += 1
            
            # POC mới (theo tên file)
            if '2024' in module_name or '2023' in module_name:
                recent_pocs.append({
                    'name': module_name,
                    'category': next((cat for cat in poc_categories.keys() if cat.lower() in module_name.lower()), 'Other')
                })
        
        return {
            'total_pocs': len(all_modules),
            'categories': dict(poc_categories),
            'cve_count': len(cve_stats),
            'recent_pocs': recent_pocs[:10],  # Top 10 POC mới
            'cve_examples': list(cve_stats.keys())[:10]  # Top 10 CVE
        }
    except Exception as e:
        print(f"Error in get_poc_statistics: {e}")
        return {}

def get_shell_statistics():
    """Thống kê Shell Connections và trạng thái"""
    try:
        # Thống kê theo trạng thái
        status_stats = db.session.query(
            ShellConnection.status,
            func.count(ShellConnection.connection_id)
        ).group_by(ShellConnection.status).all()
        
        # Thống kê theo loại shell
        type_stats = db.session.query(
            ShellConnection.shell_type,
            func.count(ShellConnection.connection_id)
        ).group_by(ShellConnection.shell_type).all()
        
        # Shell đang hoạt động
        active_shells = ShellConnection.query.filter_by(is_active=True).count()
        
        # Shell theo thời gian (7 ngày gần đây)
        seven_days_ago = dt.datetime.utcnow() - dt.timedelta(days=7)
        recent_shells = ShellConnection.query.filter(
            ShellConnection.created_at >= seven_days_ago
        ).count()
        
        # Top targets có nhiều shell
        target_shell_count = db.session.query(
            ShellConnection.hostname,
            func.count(ShellConnection.connection_id)
        ).group_by(ShellConnection.hostname).order_by(
            desc(func.count(ShellConnection.connection_id))
        ).limit(5).all()
        
        return {
            'total_connections': ShellConnection.query.count(),
            'status_distribution': {str(status): int(count) for status, count in status_stats},
            'type_distribution': {str(shell_type): int(count) for shell_type, count in type_stats},
            'active_shells': active_shells,
            'recent_shells_7days': recent_shells,
            'top_targets': [{'hostname': str(hostname), 'count': int(count)} for hostname, count in target_shell_count]
        }
    except Exception as e:
        print(f"Error in get_shell_statistics: {e}")
        return {}

def get_target_statistics():
    """Thống kê Targets"""
    try:
        # Thống kê theo server type
        server_type_stats = db.session.query(
            Targets.server_type,
            func.count(Targets.server_id)
        ).group_by(Targets.server_type).all()
        
        # Thống kê theo OS
        os_stats = db.session.query(
            Targets.os,
            func.count(Targets.server_id)
        ).filter(Targets.os.isnot(None)).group_by(Targets.os).all()
        
        # Thống kê theo status
        status_stats = db.session.query(
            Targets.status,
            func.count(Targets.server_id)
        ).group_by(Targets.status).all()
        
        # Targets mới (7 ngày gần đây)
        seven_days_ago = dt.datetime.utcnow() - dt.timedelta(days=7)
        recent_targets = Targets.query.filter(
            Targets.created_at >= seven_days_ago
        ).count()
        
        # Targets theo location
        location_stats = db.session.query(
            Targets.location,
            func.count(Targets.server_id)
        ).filter(Targets.location.isnot(None)).group_by(Targets.location).all()
        
        return {
            'total_targets': Targets.query.count(),
            'server_type_distribution': {str(server_type): int(count) for server_type, count in server_type_stats},
            'os_distribution': {str(os): int(count) for os, count in os_stats},
            'status_distribution': {str(status): int(count) for status, count in status_stats},
            'recent_targets_7days': recent_targets,
            'location_distribution': {str(location): int(count) for location, count in location_stats},
            'top_locations': [{'location': str(location), 'count': int(count)} for location, count in sorted(location_stats, key=lambda x: x[1], reverse=True)[:5]]
        }
    except Exception as e:
        print(f"Error in get_target_statistics: {e}")
        return {}

def get_data_statistics():
    """Thống kê Data Files"""
    try:
        print("=== DEBUG: Starting get_data_statistics ===")
        
        # Thống kê theo file type
        file_type_stats = db.session.query(
            DataFile.file_type,
            func.count(DataFile.file_id)
        ).group_by(DataFile.file_type).all()
        print(f"File type stats: {file_type_stats}")
        
        # Thống kê theo connection
        connection_stats = db.session.query(
            DataFile.connection_id,
            func.count(DataFile.file_id)
        ).group_by(DataFile.connection_id).order_by(
            desc(func.count(DataFile.file_id))
        ).limit(5).all()
        print(f"Connection stats: {connection_stats}")
        
        # Tổng dung lượng file - xử lý NULL values
        total_size_raw = db.session.query(func.sum(DataFile.file_size)).scalar()
        print(f"Raw total_size from DB: {total_size_raw} (type: {type(total_size_raw)})")
        
        # Kiểm tra nếu có files nhưng file_size bị NULL
        if total_size_raw is None:
            print("Warning: total_size is None, checking individual files...")
            # Lấy tất cả files để kiểm tra
            all_files = DataFile.query.all()
            files_with_size = [f.file_size for f in all_files if f.file_size is not None and f.file_size > 0]
            files_without_size = [f.file_id for f in all_files if f.file_size is None or f.file_size <= 0]
            
            print(f"Files with valid size: {len(files_with_size)}")
            print(f"Files without size: {len(files_without_size)}")
            
            if files_without_size:
                print(f"Warning: Found {len(files_without_size)} files with NULL or invalid file_size")
                print(f"Files without size: {files_without_size[:5]}")  # Chỉ in 5 file đầu
            
            total_size = sum(files_with_size) if files_with_size else 0
            print(f"Calculated total_size from individual files: {total_size}")
        else:
            total_size = total_size_raw
            print(f"Using total_size from DB: {total_size}")
        
        # Files mới (7 ngày gần đây)
        seven_days_ago = dt.datetime.utcnow() - dt.timedelta(days=7)
        recent_files = DataFile.query.filter(
            DataFile.file_created_at >= seven_days_ago
        ).count()
        print(f"Recent files (7 days): {recent_files}")
        
        # Top file types theo dung lượng
        size_by_type = db.session.query(
            DataFile.file_type,
            func.sum(DataFile.file_size)
        ).group_by(DataFile.file_type).order_by(
            desc(func.sum(DataFile.file_size))
        ).all()
        print(f"Size by type: {size_by_type}")
        
        # Tổng số files
        total_files = DataFile.query.count()
        print(f"Total files count: {total_files}")
        
        # Validation dữ liệu
        if total_size < 0:
            total_size = 0
        if total_files < 0:
            total_files = 0
        
        # Tính toán dung lượng với xử lý edge cases
        total_size_mb = 0
        total_size_gb = 0
        average_file_size = 0
        
        if total_size > 0:
            total_size_mb = round(float(total_size) / (1024 * 1024), 2)
            total_size_gb = round(float(total_size) / (1024 * 1024 * 1024), 2)
            average_file_size = round(float(total_size) / total_files, 2) if total_files > 0 else 0
        
        print(f"Calculated sizes - MB: {total_size_mb}, GB: {total_size_gb}, Avg: {average_file_size}")
        
        result = {
            'total_files': total_files,
            'total_size_bytes': int(total_size),
            'total_size_mb': total_size_mb,
            'total_size_gb': total_size_gb,
            'file_type_distribution': {str(file_type): int(count) for file_type, count in file_type_stats if file_type and count > 0},
            'recent_files_7days': recent_files,
            'top_connections': [{'connection_id': str(conn_id), 'count': int(count)} for conn_id, count in connection_stats if conn_id and count > 0],
            'size_by_type': {str(file_type): int(size) for file_type, size in size_by_type if file_type and size and size > 0},
            'average_file_size': average_file_size,
            'files_with_valid_size': len([f for f in DataFile.query.all() if f.file_size and f.file_size > 0]),
            'files_without_size': len([f for f in DataFile.query.all() if not f.file_size or f.file_size <= 0])
        }
        
        print(f"Final result: {result}")
        print("=== END DEBUG ===")
        
        if total_size == 0 and total_files > 0:
            print(f"Warning: {total_files} files found but total size is 0. Check file_size field values.")
        
        return result
        
    except Exception as e:
        print(f"Error in get_data_statistics: {e}")
        import traceback
        traceback.print_exc()
        # Trả về dữ liệu mặc định thay vì dict rỗng
        return {
            'total_files': 0,
            'total_size_bytes': 0,
            'total_size_mb': 0,
            'total_size_gb': 0,
            'file_type_distribution': {},
            'recent_files_7days': 0,
            'top_connections': [],
            'size_by_type': {},
            'average_file_size': 0,
            'files_with_valid_size': 0,
            'files_without_size': 0,
            'error': str(e)
        }

def get_time_based_statistics():
    """Thống kê theo thời gian"""
    try:
        # Thống kê theo ngày (7 ngày gần đây)
        seven_days_ago = dt.datetime.utcnow() - dt.timedelta(days=7)
        
        # Targets theo ngày
        targets_by_day = db.session.query(
            func.date(Targets.created_at),
            func.count(Targets.server_id)
        ).filter(
            Targets.created_at >= seven_days_ago
        ).group_by(func.date(Targets.created_at)).all()
        
        # Shell connections theo ngày
        shells_by_day = db.session.query(
            func.date(ShellConnection.created_at),
            func.count(ShellConnection.connection_id)
        ).filter(
            ShellConnection.created_at >= seven_days_ago
        ).group_by(func.date(ShellConnection.created_at)).all()
        
        # Data files theo ngày
        files_by_day = db.session.query(
            func.date(DataFile.file_created_at),
            func.count(DataFile.file_id)
        ).filter(
            DataFile.file_created_at >= seven_days_ago
        ).group_by(func.date(DataFile.file_created_at)).all()
        
        return {
            'targets_by_day': [{'date': str(date), 'count': int(count)} for date, count in targets_by_day],
            'shells_by_day': [{'date': str(date), 'count': int(count)} for date, count in shells_by_day],
            'files_by_day': [{'date': str(date), 'count': int(count)} for date, count in files_by_day]
        }
    except Exception as e:
        print(f"Error in get_time_based_statistics: {e}")
        return {}

def get_special_logs():
    """Lấy các log đặc biệt trong hệ thống"""
    try:
        special_logs = []
        
        # Kiểm tra các shell có trạng thái lỗi
        error_shells = ShellConnection.query.filter_by(status=ShellStatus.ERROR).limit(5).all()
        for shell in error_shells:
            special_logs.append({
                'type': 'error',
                'message': f'Shell connection {shell.name} has ERROR status',
                'timestamp': shell.updated_at.isoformat() if shell.updated_at else None,
                'details': f'Connection ID: {shell.connection_id}, Target: {shell.hostname}'
            })
        
        # Kiểm tra targets có nhiều shell connections
        targets_with_many_shells = db.session.query(
            Targets.hostname,
            func.count(ShellConnection.connection_id)
        ).join(ShellConnection).group_by(Targets.hostname).having(
            func.count(ShellConnection.connection_id) > 3
        ).all()
        
        for target, count in targets_with_many_shells:
            special_logs.append({
                'type': 'warning',
                'message': f'Target {target} has {count} shell connections',
                'timestamp': dt.datetime.utcnow().isoformat(),
                'details': f'Multiple shell connections detected on {target}'
            })
        
        # Kiểm tra files lớn (>100MB)
        large_files = DataFile.query.filter(DataFile.file_size > 100 * 1024 * 1024).limit(5).all()
        for file in large_files:
            special_logs.append({
                'type': 'info',
                'message': f'Large file detected: {file.file_name}',
                'timestamp': file.file_created_at.isoformat() if file.file_created_at else None,
                'details': f'Size: {file.file_size / (1024*1024):.2f} MB, Type: {file.file_type}'
            })
        
        return special_logs[:20]  # Giới hạn 20 log
    except Exception as e:
        print(f"Error in get_special_logs: {e}")
        return []

@blueprint.route('/file_statistics', methods=['GET'])
def file_statistics():
    """API endpoint để lấy thống kê file đẹp mắt cho dashboard"""
    try:
        # Lấy tất cả files
        all_files = DataFile.query.all()
        
        # Tính toán thống kê chi tiết
        file_stats = {
            'total_files': len(all_files),
            'total_size_mb': 0,
            'total_size_gb': 0,
            'by_type': {},
            'download_files': {'count': 0, 'size_mb': 0},
            'upload_files': {'count': 0, 'size_mb': 0},
            'recent_files': [],
            'top_connections': []
        }
        
        # Tính tổng dung lượng và phân loại
        for file in all_files:
            if file.file_size and file.file_size > 0:
                # Tính tổng dung lượng (convert KB to MB)
                file_size_mb = file.file_size / 1024
                file_stats['total_size_mb'] += file_size_mb
                
                # Phân loại theo loại file
                file_type = file.file_type.lower() if file.file_type else 'unknown'
                if file_type not in file_stats['by_type']:
                    file_stats['by_type'][file_type] = {
                        'count': 0,
                        'size_mb': 0,
                        'size_gb': 0
                    }
                
                file_stats['by_type'][file_type]['count'] += 1
                file_stats['by_type'][file_type]['size_mb'] += file_size_mb
                
                # Phân loại theo download/upload dựa trên source_path hoặc file_type
                if file.source_path and ('download' in file.source_path.lower() or 'downloads' in file.source_path.lower()):
                    file_stats['download_files']['count'] += 1
                    file_stats['download_files']['size_mb'] += file_size_mb
                elif file.source_path and ('upload' in file.source_path.lower() or 'uploads' in file.source_path.lower()):
                    file_stats['upload_files']['count'] += 1
                    file_stats['upload_files']['size_mb'] += file_size_mb
                else:
                    # Nếu không xác định được, phân loại theo file_type
                    if file_type in ['download', 'downloaded']:
                        file_stats['download_files']['count'] += 1
                        file_stats['download_files']['size_mb'] += file_size_mb
                    elif file_type in ['upload', 'uploaded']:
                        file_stats['upload_files']['count'] += 1
                        file_stats['upload_files']['size_mb'] += file_size_mb
                    else:
                        # Mặc định là download nếu không xác định được
                        file_stats['download_files']['count'] += 1
                        file_stats['download_files']['size_mb'] += file_size_mb
        
        # Convert MB to GB
        file_stats['total_size_gb'] = round(file_stats['total_size_mb'] / 1024, 2)
        file_stats['total_size_mb'] = round(file_stats['total_size_mb'], 2)
        
        # Làm tròn dung lượng cho từng loại
        for file_type in file_stats['by_type']:
            file_stats['by_type'][file_type]['size_mb'] = round(file_stats['by_type'][file_type]['size_mb'], 2)
            file_stats['by_type'][file_type]['size_gb'] = round(file_stats['by_type'][file_type]['size_mb'] / 1024, 2)
        
        # Làm tròn dung lượng cho download/upload
        file_stats['download_files']['size_mb'] = round(file_stats['download_files']['size_mb'], 2)
        file_stats['upload_files']['size_mb'] = round(file_stats['upload_files']['size_mb'], 2)
        
        # Lấy files mới nhất
        recent_files = DataFile.query.order_by(desc(DataFile.file_created_at)).limit(10).all()
        file_stats['recent_files'] = [{
            'file_id': f.file_id,
            'file_name': f.file_name,
            'file_type': f.file_type,
            'file_size_mb': round(f.file_size / 1024, 2) if f.file_size else 0,
            'created_at': f.file_created_at.isoformat() if f.file_created_at else None,
            'connection_id': f.connection_id,
            'source_path': f.source_path
        } for f in recent_files]
        
        # Top connections theo số file
        connection_stats = db.session.query(
            DataFile.connection_id,
            func.count(DataFile.file_id).label('file_count'),
            func.sum(DataFile.file_size).label('total_size')
        ).filter(
            DataFile.connection_id.isnot(None),
            DataFile.connection_id != ''
        ).group_by(DataFile.connection_id).order_by(
            desc(func.count(DataFile.file_id))
        ).limit(10).all()
        
        file_stats['top_connections'] = [{
            'connection_id': str(conn_id),
            'file_count': int(count),
            'total_size_mb': round(float(total_size) / 1024, 2) if total_size else 0
        } for conn_id, count, total_size in connection_stats]
        
        return jsonify({
            'status': 'success',
            'file_statistics': file_stats
        })
        
    except Exception as e:
        print(f"Error in file_statistics: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        })