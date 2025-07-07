#Trần ku bảo đã viết cái này
from unittest import result
from flask import render_template, request, redirect, url_for, jsonify, session
from apps.reconna import blueprint
from apps.models import Product

from apps.reconna.Recon_Nmap._Nmap_ import Recon_Nmap


import multiprocessing #lưu lại process ID
from multiprocessing import Process, Queue


#=================================NMAP======================================================
@blueprint.route('/recon/nmap/scan',methods=['GET','POST'])
def recon_nmap_scan():    
    try:
        data = request.get_json()
        url_target = data.get('hostname')
        mode_scan = data.get('mode')
        scanner = Recon_Nmap(target=url_target)

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




