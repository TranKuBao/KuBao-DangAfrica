#Trần ku bảo đã viết cái này
from unittest import result
from flask import render_template, request, redirect, url_for, jsonify, session
from urllib3 import response
from apps.reconna import blueprint
import datetime as dt
import os 
import json
import time
import random
from flask import Blueprint, request, jsonify
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from apps.models import Targets, Reports, db
from apps.reconna.Recon_Nmap._Nmap_ import Recon_Nmap
from apps.reconna.Recon_Wappalyzer._Wappalyzer_ import Recon_Wappalyzer
from apps.reconna.Recon_Dirsearch._Dirseach_ import Recon_Directory, DirsearchManager
from apps.reconna.Recon_Wpcan._WP_Scan_ import Recon_Wpscan

#import các model để luwu dữ liệu
from apps.models import Reports, Targets
from apps import db  # Đảm bảo đã import db

#=================================NMAP======================================================
@blueprint.route('/recon/nmap/scan',methods=['GET','POST'])
def recon_nmap_scan():    
    try:
        data = request.get_json()
        url_target = data.get('hostname')
        mode_scan = data.get('mode')
        print(f"[+] Data scan nmap: {data}")
        # Host Discovery: chỉ xem host nào đang online   nmap -sn 192.168.1.5   
        # Fast Scan: Quét nhanh ~100 cổng phổ biến.     nmap -T4 -F -Pn 10.10.10.10
        # Service Detection: Quét TCP stealth, dò dịch vụ + phiên bản.    nmap -sS -sV -Pn -T4 10.10.10.10
        # Vulnerability Scan: Dùng các script NSE để phát hiện lỗi như Heartbleed, SMB vuln, HTTP vuln...      nmap --script=vuln -Pn 10.10.10.10
        # Aggressive Scan: Tổng hợp: OS, dịch vụ, script, traceroute.      nmap -A -Pn 10.10.10.10
        arguments = "-sn" if mode_scan == 1 else \
                "-T4 -F -Pn" if mode_scan == 2 else \
                "-sS -sV -Pn -T4" if mode_scan == 3 else \
                "--script=vuln -Pn" if mode_scan == 4 else \
                "-A -Pn"
        ok, msg = Recon_Nmap.start_scan(url_target, arguments)

        return jsonify({'status': 0 if ok else -1, 'msg': msg})
    except Exception as e:
        return jsonify({
            'status': -1,
            'msg': str(e),
            'error': str(e)
        })

@blueprint.route('/recon/nmap/result', methods=['GET'])
def get_nmap_result():
    result = Recon_Nmap.get_scan_result()
    if result is not None:
        return jsonify({'status': 0, 'data': result})
    else:
        return jsonify({'status': -1, 'msg': 'No result available'})

@blueprint.route('/recon/nmap/stop', methods=['POST'])
def stop_nmap_scan():
    ok, msg = Recon_Nmap.stop_scan()
    return jsonify({'status': 0 if ok else -1, 'msg': msg})




#=================================Wappalyzer======================================================
@blueprint.route('/recon/wappalyzer/scan', methods=['POST'])
def recon_wappalyzer_scan():
    try:
        data = request.get_json()
        url_target = data.get('hostname')
        print(f"Data scan Wappalyzer: {data}")
        ok, msg = Recon_Wappalyzer.start_scan(url_target)
        return jsonify({'status': 0 if ok else -1, 'msg': msg})
    except Exception as e:
        return jsonify({
            'status': -1,
            'msg': str(e),
            'error': str(e)
        })

@blueprint.route('/recon/wappalyzer/result', methods=['GET'])
def get_wappalyzer_result():
    result = Recon_Wappalyzer.get_scan_result()
    if result is not None:
        return jsonify({'status': 0, 'data': result})
    else:
        return jsonify({'status': -1, 'msg': 'No result available'})

@blueprint.route('/recon/wappalyzer/stop', methods=['POST'])
def stop_wappalyzer_scan():
    ok, msg = Recon_Wappalyzer.stop_scan()
    return jsonify({'status': 0 if ok else -1, 'msg': msg})


#=================================Dirsearch======================================================
@blueprint.route('/recon/Dirsearch/scan', methods=['POST'])
def recon_Dirsearch_scan():
    try:
        data = request.get_json()
        url_target = data.get('hostname')
        mode_scan = data.get('mode')
        mode = "fast" if mode_scan == 1 else \
                "normal" if mode_scan == 2 else \
                "deep" 

        print(f"Data scan Dirsearch: {data}")
        ok, msg = DirsearchManager.start_scan(url_target, mode)
        return jsonify({'status': 0 if ok else -1, 'msg': msg})
    except Exception as e:
        return jsonify({
            'status': -1,
            'msg': str(e),
            'error': str(e)
        })

@blueprint.route('/recon/Dirsearch/result', methods=['GET'])
def get_Dirsearch_result():
    result = DirsearchManager.get_scan_result()
    done = not DirsearchManager._is_running
    if result is not None:
        return jsonify({'status': 0, 'data': result, 'done': done})
    else:
        return jsonify({'status': -1, 'msg': 'No result available', 'done': done})

@blueprint.route('/recon/Dirsearch/stop', methods=['POST'])
def stop_Dirsearch_scan():
    ok, msg = DirsearchManager.stop_scan()
    return jsonify({'status': 0 if ok else -1, 'msg': msg})


#================================= Wpscan ======================================================
@blueprint.route('/recon/wpscan/scan',methods=['POST'])
def recon_wpscan_scan():
    try:
        data = request.get_json()
        url_target = data.get('hostname')
        if not url_target:
            return jsonify({"status":-1,"msg":"Thiếu URL target","error": "Thiếu URL"}), 400

        print(f"Data scan Wpscan: {data}")
        ok, msg = Recon_Wpscan.start_scan(url_target)
        return jsonify({'status':0,'msg':msg})
    except Exception as e:
        return jsonify({'status':-1,"error":str(e),"msg":str(e)})


@blueprint.route('/recon/wpscan/result', methods=['GET'])
def get_wpscan_result():
    result = Recon_Wpscan.get_scan_result()
    if result is not None:
        return jsonify({'status': 0, 'data': result})
    else:
        return jsonify({'status': -1, 'msg': 'No result available'})


#================================= Lưu dữ liệu report ==========================================================   
@blueprint.route('/api/save_report', methods=['POST'])
def save_recon():
    try:
        data = request.get_json()
        server_id = data.get('server_id')
        tool = data.get('tool')
        data_scan = data.get('data_scan')

        if not server_id or not tool or data_scan is None:
            return jsonify({'status': -1, 'msg': 'Thiếu tham số'}), 400

        report = Reports.query.filter_by(server_id=server_id).first()
        if not report:
            # Tự động tạo record Reports nếu chưa có
            try:
                report = Reports(
                    server_id=server_id,
                    nmap=None,
                    dirsearch=None,
                    wappalyzer=None,
                    wpscan=None,
                    pocs=None,
                    update_nmap=None,
                    update_dirsearch=None,
                    update_wappalyzer=None,
                    update_wpscan=None,
                    update_pocs=None
                )
                db.session.add(report)
                db.session.commit()
                print(f"Đã tạo record Reports mới cho server_id: {server_id}")
            except Exception as e:
                db.session.rollback()
                print(f"Lỗi tạo record Reports: {e}")
                return jsonify({'status': -1, 'msg': f'Lỗi tạo record Reports: {e}'})

        now_time = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        update_fields = {}

        if tool == 'nmap':
            update_fields = {'nmap': data_scan, 'update_nmap': now_time}
        elif tool == 'dirsearch':
            update_fields = {'dirsearch': data_scan, 'update_dirsearch': now_time}
        elif tool == 'wappalyzer':
            update_fields = {'wappalyzer': data_scan, 'update_wappalyzer': now_time}
        elif tool == 'wpscan':
            update_fields = {'wpscan': data_scan, 'update_wpscan': now_time}
        elif tool == 'pocs':
            # Lưu dữ liệu POC scan vào bảng Reports
            update_fields = {'pocs': data_scan, 'update_pocs': now_time}
            
            # Đồng thời cập nhật exploitation_level của target
            try:
                pocs = []
                if data_scan:
                    try:
                        pocs = json.loads(data_scan)
                    except Exception:
                        pocs = []
                
                # Chỉ lưu số lượng POC đã verify
                poc_count = len(pocs)
                poc_dir = os.path.join(os.path.dirname(__file__), '../../pocsuite3/pocs')
                total_poc = len([
                    f for f in os.listdir(os.path.abspath(poc_dir))
                    if f.endswith('.py') and not f.startswith('__')
                ])
                target = Targets.get_by_id(server_id=server_id)
                if target:
                    target.exploitation_level = str(poc_count) + "/" + str(total_poc)
                    target.updated_at = dt.datetime.utcnow()
                    db.session.commit()
            except Exception as e:
                print(f'Lỗi cập nhật exploitation_level: {e}')
                # Không rollback vì vẫn muốn lưu dữ liệu scan

        try:
            report.update(**update_fields)
        except Exception as e:
            db.session.rollback()
            print(f'Lỗi commit DB: {e}')
            return jsonify({'status': -1, 'msg': f'Lỗi commit DB: {e}'})

        return jsonify({'status': 0, 'msg': 'Saving successfully'})
        
    except Exception as e:
        db.session.rollback()
        print(f'Lỗi ở hàm lưu dữ liệu lưu... {e}')
        return jsonify({'status': -1, 'msg': str(e), 'error': str(e)})


@blueprint.route('/api/get_poc_report', methods=['GET'])
def get_poc_report():
    """Lấy dữ liệu POC scan đã lưu cho một target cụ thể"""
    try:
        server_id = request.args.get('server_id', type=int)
        if not server_id:
            return jsonify({'status': -1, 'msg': 'Thiếu server_id'}), 400
        
        report = Reports.query.filter_by(server_id=server_id).first()
        if not report:
            return jsonify({'status': -1, 'msg': 'Không tìm thấy report cho server này'})
        
        poc_data = None
        if report.pocs:
            try:
                poc_data = json.loads(report.pocs)
            except Exception:
                poc_data = report.pocs  # Giữ nguyên nếu không parse được JSON
        
        return jsonify({
            'status': 0,
            'data': {
                'server_id': server_id,
                'poc_data': poc_data,
                'update_pocs': report.update_pocs,
                'exploitation_level': report.target.exploitation_level if report.target else None
            }
        })
        
    except Exception as e:
        print(f'Lỗi lấy POC report: {e}')
        return jsonify({'status': -1, 'msg': str(e), 'error': str(e)})


#================================================================================================
