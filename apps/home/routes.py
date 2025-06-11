# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
import wtforms
from apps.home import blueprint
from flask import render_template, request, redirect, url_for, jsonify
from jinja2 import TemplateNotFound
from flask_login import login_required, current_user
from apps import db
from apps.authentication.models import Users
from flask_wtf import FlaskForm

#bắt đầu code từ đây
@blueprint.route('/targets')
def targets():
    return render_template('targets/index-targets.html', segment='index_targets')


@blueprint.route('/api/add_targets', methods=['POST'])
def add_targets():
    """API để thêm một target mới"""
    try:
        # Lấy dữ liệu JSON từ request
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No input data provided'}), 400
        else:
            data = request.form.to_dict()
            
        if not data:
            return jsonify({'error': 'No input data provided'}), 400
        
        # Kiểm tra các trường bắt buộc
        required_fields = ['hostname', 'ip_address', 'server_type']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Kiểm tra server_type hợp lệ
        try:
            server_type = ServerType(data['server_type'])
        except ValueError:
            return jsonify({'error': 'Invalid server_type value'}), 400

        # Tạo dictionary cho các tham số tùy chọn
        optional_fields = {
            'os': data.get('os'),
            'location': data.get('location'),
            'status': data.get('status', 'active'),
            'privilege_escalation': data.get('privilege_escalation', False),
            'exploitation_level': data.get('exploitation_level'),
            'incident_id': data.get('incident_id'),
            'notes': data.get('notes')
        }

        # Tạo target mới
        target = Targets.create_target(
            hostname=data['hostname'],
            ip_address=data['ip_address'],
            server_type=server_type,
            **{k: v for k, v in optional_fields.items() if v is not None}
        )

        # Trả về thông tin target vừa tạo
        return jsonify({
            'message': 'Target created successfully',
            'target': target.to_dict()
        }), 201

    except InvalidUsage as e:
        return jsonify({'error': str(e)}), 400
    except SQLAlchemyError as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500


















@blueprint.route('/')
@blueprint.route('/index')
def index():
    return render_template('pages/index.html', segment='dashboard', parent="dashboard")

@blueprint.route('/billing')
def billing():
    return render_template('pages/billing.html', segment='billing')

@blueprint.route('/rtl')
def rtl():
    return render_template('pages/rtl.html', segment='rtl')

@blueprint.route('/tables')
def tables():
    return render_template('pages/tables.html', segment='tables')

@blueprint.route('/virtual_reality')
def virtual_reality():
    return render_template('pages/virtual-reality.html', segment='virtual_reality')



def getField(column): 
    if isinstance(column.type, db.Text):
        return wtforms.TextAreaField(column.name.title())
    if isinstance(column.type, db.String):
        return wtforms.StringField(column.name.title())
    if isinstance(column.type, db.Boolean):
        return wtforms.BooleanField(column.name.title())
    if isinstance(column.type, db.Integer):
        return wtforms.IntegerField(column.name.title())
    if isinstance(column.type, db.Float):
        return wtforms.DecimalField(column.name.title())
    if isinstance(column.type, db.LargeBinary):
        return wtforms.HiddenField(column.name.title())
    return wtforms.StringField(column.name.title()) 


@blueprint.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():

    class ProfileForm(FlaskForm):
        pass

    readonly_fields = Users.readonly_fields
    full_width_fields = {"bio"}

    for column in Users.__table__.columns:
        if column.name == "id":
            continue

        field_name = column.name
        if field_name in full_width_fields:
            continue

        field = getField(column)
        setattr(ProfileForm, field_name, field)

    for field_name in full_width_fields:
        if field_name in Users.__table__.columns:
            column = Users.__table__.columns[field_name]
            field = getField(column)
            setattr(ProfileForm, field_name, field)

    form = ProfileForm(obj=current_user)

    if form.validate_on_submit():
        readonly_fields.append("password")
        excluded_fields = readonly_fields
        for field_name, field_value in form.data.items():
            if field_name not in excluded_fields:
                setattr(current_user, field_name, field_value)

        db.session.commit()
        return redirect(url_for('home_blueprint.profile'))
    
    context = {
        'segment': 'profile',
        'form': form,
        'readonly_fields': readonly_fields,
        'full_width_fields': full_width_fields,
    }
    return render_template('pages/profile.html', **context)


# Helper - Extract current page name from request
@blueprint.app_template_filter('replace_value')
def replace_value(value, args):
  return value.replace(args, " ").title()

def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'index'

        return segment

    except:
        return None
