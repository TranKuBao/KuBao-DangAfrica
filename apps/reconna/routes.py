#Trần ku bảo đã viết cái này
from unittest import result
from flask import render_template, request, redirect, url_for, jsonify, session
from apps.reconna import blueprint
from apps.models import Product

from apps.reconna.Recon_Nmap._Nmap_ import Recon_Nmap


@blueprint.route('/hello', methods=['GET'])
def hello():
    return jsonify({'message': 'Hello from myfeature!'})

@blueprint.route('/recon/wappalyzer/scan',methods=['GET','POST'])
def recon_wappalyzer_scan():
    data = request.get_json()
    if not data:
        jsonify({
            'status': -1,
            'msg': 'No input data provided'
        })
    try:
        url_target = data.get('hostname')
        mode_scan = data.get('mode')
        scanner = Recon_Nmap(target=url_target)

        result = Recon_Nmap(url_target)
        
    # Host Discovery: chỉ xem host nào đang online   nmap -sn 192.168.1.5   
    #     
    # Fast Scan: Quét nhanh ~100 cổng phổ biến.     nmap -T4 -F -Pn 10.10.10.10
    # Service Detection: Quét TCP stealth, dò dịch vụ + phiên bản.    nmap -sS -sV -Pn -T4 10.10.10.10
    # Vulnerability Scan: Dùng các script NSE để phát hiện lỗi như Heartbleed, SMB vuln, HTTP vuln...      nmap --script=vuln -Pn 10.10.10.10
    # Aggressive Scan: Tổng hợp: OS, dịch vụ, script, traceroute.      nmap -A -Pn 10.10.10.10
        return jsonify({
            'status': 0,
            'msg': 'Successfully',
            'data': result
        })

    except Exception as e:
        return jsonify({
            'status': -1,
            'msg': str(e),
            'error': str(e)
        })