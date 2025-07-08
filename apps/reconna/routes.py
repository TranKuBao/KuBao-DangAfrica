#Trần ku bảo đã viết cái này
from unittest import result
from flask import render_template, request, redirect, url_for, jsonify, session
from apps.reconna import blueprint
from apps.models import Product

from apps.reconna.Recon_Nmap._Nmap_ import Recon_Nmap
from apps.reconna.Recon_Wappalyzer._Wappalyzer_ import Recon_Wappalyzer
from apps.reconna.Recon_Dirsearch._Dirseach_ import Recon_Directory, DirsearchManager

from multiprocessing import Process, Queue


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
        ok, msg = DirsearchManager.start_scan(url_target, 'default')
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
