# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from apps.partial import blueprint
from flask import render_template, jsonify
from apps.models import Product, Targets, ShellStatus, ShellConnection
from pocsuite3.lib.core.interpreter import PocsuiteInterpreter


poc_core = PocsuiteInterpreter()

@blueprint.route('/header_statictical', methods=['GET'])
def charts():
    #Số POC
    try: 
        listModules = poc_core.get_all_modules()
        total_POC = len(listModules)
        
        # số target
        listTarget = Targets.query.all()
        total_target = len(listTarget)
        
        # Só data stolen => đếm từ csdl
        total_DataStolen = 0
        
        # Connection 
        listShellConnection = ShellConnection.query.all()
        for shell in listShellConnection:
            if shell.status == ShellStatus.CONNECTED or shell.status == ShellStatus.RECONNECTING:
                total_DataStolen += 1
        
        return jsonify({
            'total_POC': total_POC,
            'total_target': total_target,
            'total_DataStolen': total_DataStolen,
            'total_ShellConnection': len(listShellConnection)
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