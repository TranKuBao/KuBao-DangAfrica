from flask import render_template, request, redirect, url_for, jsonify, session
from apps.reconna import blueprint
from apps.models import Product


@blueprint.route('/hello', methods=['GET'])
def hello():
    return jsonify({'message': 'Hello from myfeature!'})