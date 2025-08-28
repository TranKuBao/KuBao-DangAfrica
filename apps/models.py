# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
from email.policy import default
from apps import db
from sqlalchemy.exc import SQLAlchemyError
from apps.exceptions.exception import InvalidUsage
import datetime as dt
import math
from sqlalchemy.orm import relationship
from enum import Enum
from sqlalchemy import or_, desc, asc

class CURRENCY_TYPE(Enum):
    usd = 'usd'
    eur = 'eur'


class Product(db.Model):
    __tablename__ = 'products'
    id            = db.Column(db.Integer,      primary_key=True)
    name          = db.Column(db.String(128),  nullable=False)
    info          = db.Column(db.Text,         nullable=True)
    price         = db.Column(db.Integer,      nullable=False)
    currency      = db.Column(db.Enum(CURRENCY_TYPE), default=CURRENCY_TYPE.usd, nullable=False)
    date_created  = db.Column(db.DateTime,     default=dt.datetime.utcnow())
    date_modified = db.Column(db.DateTime,     default=db.func.current_timestamp(),
                                               onupdate=db.func.current_timestamp())
    
    def __init__(self, **kwargs):
        super(Product, self).__init__(**kwargs)

    def __repr__(self):
        return f"{self.name} / ${self.price}"

    @classmethod
    def find_by_id(cls, _id: int) -> "Product":
        return cls.query.filter_by(id=_id).first() 
    
    @classmethod
    def get_list(cls):
        return cls.query.all()

    def save(self) -> None:
        try:
            db.session.add(self)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            db.session.close()
            error = str(e.__dict__['orig'])
            raise InvalidUsage(error, 422)

    def delete(self) -> None:
        try:
            db.session.delete(self)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            db.session.close()
            error = str(e.__dict__['orig'])
            raise InvalidUsage(error, 422)
        return


class IncidentType(Enum):
    MALWARE = "malware"
    PHISHING = "phishing"
    DATA_BREACH = "data_breach"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DDOS = "ddos"
    VULNERABILITY = "vulnerability"
    OTHER = "other"


class ResolutionStatus(Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ServerType(Enum):
    WEB_SERVER = "web_server"
    DATABASE_SERVER = "database_server"
    APPLICATION_SERVER = "application_server"
    FILE_SERVER = "file_server"
    EMAIL_SERVER = "email_server"
    DNS_SERVER = "dns_server"
    OTHER = "other"


class FileType(Enum):
    """Enum for file types"""
    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    ARCHIVE = "archive"
    OTHER = "other"


class PrivilegeLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ADMIN = "admin"
    ROOT = "root"


class Targets(db.Model):
    """
    Model for target servers/assets, including shell management fields for integration with pwncat.
    """
    __tablename__ = 'targets'

    # Core identification fields
    server_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    hostname = db.Column(db.String(255), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)  # IPv6 support
    server_type = db.Column(db.String(50), nullable=False)
    os = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(50), nullable=False, default='active')
    privilege_escalation = db.Column(db.String(100), nullable=True)
    exploitation_level = db.Column(db.String(100), nullable=True)
    incident_id = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    # --- Shell management fields (for pwncat integration) ---
    shell_type = db.Column(db.String(50), nullable=True, comment="Type of shell: bind/reverse/other")
    connect_time = db.Column(db.DateTime, nullable=True, comment="Shell connect time (UTC)")
    disconnect_time = db.Column(db.DateTime, nullable=True, comment="Shell disconnect time (UTC)")
    reconnect_count = db.Column(db.Integer, default=0, nullable=True, comment="Number of reconnect attempts")
    last_status = db.Column(db.String(50), nullable=True, comment="Last known shell status")
    user = db.Column(db.String(100), nullable=True, comment="User of the shell session")
    url = db.Column(db.String(255), nullable=True, comment="Original URL/hostname if applicable")

    # Relationships
    reports = db.relationship('Reports', backref='target', lazy=True)

    def __init__(self, hostname, ip_address, server_type, os=None, location=None, 
                 status='active', privilege_escalation=None, exploitation_level=None, 
                 incident_id=None, notes=None, shell_type=None, connect_time=None, disconnect_time=None, 
                 reconnect_count=0, last_status=None, user=None, url=None):
        self.hostname = hostname
        self.ip_address = ip_address
        self.server_type = server_type
        self.os = os
        self.location = location
        self.status = status
        self.exploitation_level = exploitation_level
        self.privilege_escalation = privilege_escalation
        self.incident_id = incident_id
        self.notes = notes
        self.shell_type = shell_type
        self.connect_time = connect_time
        self.disconnect_time = disconnect_time
        self.reconnect_count = reconnect_count
        self.last_status = last_status
        self.user = user
        self.url = url

    def __repr__(self):
        return f'<Target {self.server_id}: {self.hostname}>'
    
    def to_dict(self):
        return {
            'server_id': self.server_id,
            'hostname': self.hostname,
            'ip_address': self.ip_address,
            'server_type': self.server_type if self.server_type else None,
            'os': self.os,
            'location': self.location,
            'status': self.status,
            'privilege_escalation': self.privilege_escalation,
            'exploitation_level': self.exploitation_level,
            'incident_id': self.incident_id,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            # Shell management fields
            'shell_type': self.shell_type,
            'connect_time': self.connect_time.isoformat() if self.connect_time else None,
            'disconnect_time': self.disconnect_time.isoformat() if self.disconnect_time else None,
            'reconnect_count': self.reconnect_count,
            'last_status': self.last_status,
            'user': self.user,
            'url': self.url
        }
    
    @classmethod
    def create_target(cls, hostname, ip_address, server_type, os=None, location=None, 
                      status='active', privilege_escalation=None, exploitation_level=None, 
                      incident_id=None, notes=None, report_data=None, shell_type=None, connect_time=None, disconnect_time=None, 
                      reconnect_count=0, last_status=None, user=None, url=None):
        """Create a new target và đồng thời tạo report với server_id tương ứng"""
        from apps.models import Reports, db
        try:
            target = cls(
                hostname=hostname,
                ip_address=ip_address,
                server_type=server_type,
                os=os,
                location=location,
                status=status,
                privilege_escalation=privilege_escalation,
                exploitation_level=exploitation_level,
                incident_id=incident_id,
                notes=notes,
                shell_type=shell_type,
                connect_time=connect_time,
                disconnect_time=disconnect_time,
                reconnect_count=reconnect_count,
                last_status=last_status,
                user=user,
                url=url
            )
            db.session.add(target)
            db.session.flush()  # Để lấy server_id vừa tạo
            # Tạo report với server_id giống target
            report = Reports(
                server_id=target.server_id,
                **(report_data or {})
            )
            db.session.add(report)
            db.session.commit()
            return target
        except Exception as e:
            db.session.rollback()
            raise InvalidUsage(f"Error creating target: {str(e)}")
    
    @classmethod
    def get_by_id(cls, server_id):
        """Get target by ID"""
        return cls.query.filter_by(server_id=server_id).first()
    
    @classmethod
    def get_by_server_type(cls, server_type):
        """Get targets by server type"""
        return cls.query.filter_by(server_type=server_type).all()
    
    @classmethod
    def search(cls, keyword, page=None, per_page=None, sort_type=None):
        """Tìm kiếm targets theo hostname, ip_address, server_type hoặc status"""
        print(f"[x] keyword: {keyword} & page={page} & per_page={per_page} & sort_type={sort_type}")
        query = cls.query
        if keyword:
            search_term = f"%{keyword}%"
            query =  query.filter(
                or_(
                    getattr(cls, 'hostname').ilike(search_term),
                    getattr(cls, 'ip_address').ilike(search_term),
                    getattr(cls, 'server_type').ilike(search_term),
                    getattr(cls, 'status').ilike(search_term),      
                    getattr(cls, 'location').ilike(search_term),
                    getattr(cls, 'os').ilike(search_term)
                )
            )
        # Apply sorting
        if sort_type:
            if sort_type == 'hostname':
                query = query.order_by(asc(getattr(cls, 'hostname')))
            elif sort_type == 'updated_at_desc':
                query = query.order_by(desc(getattr(cls, 'updated_at')))
            elif sort_type == 'updated_at_asc':
                query = query.order_by(asc(getattr(cls, 'updated_at')))
            elif sort_type == 'created_at_desc':
                query = query.order_by(desc(getattr(cls, 'created_at')))
            elif sort_type == 'created_at_asc':
                query = query.order_by(asc(getattr(cls, 'created_at')))
            elif sort_type == 'status':
                query = query.order_by(asc(getattr(cls, 'status')))
            elif sort_type == 'server_type':
                query = query.order_by(asc(getattr(cls, 'server_type')))
            elif sort_type == 'ip_address':
                query = query.order_by(asc(getattr(cls, 'ip_address')))
            else:
                # Default sorting by server_id desc (newest first)
                query = query.order_by(desc(getattr(cls, 'server_id')))
        else:
            # Default sorting by server_id desc (newest first)
            query = query.order_by(desc(getattr(cls, 'server_id')))
            
        #print(f"QUERY: {query}")
        if page and per_page: # nếu có các giá trị của phân trang thì mình cho nó
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            #print(f"[[x]]result: {pagination}")
            return pagination.items, pagination.pages
        return query.all(), None # không thi đéo trả về hết
    
    def update(self, **kwargs):
        """Update target attributes"""
        try:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            self.updated_at = dt.datetime.utcnow()
            db.session.commit()
            return self
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error updating target: {str(e)}")
    
    def delete(self):
        """Delete target and associated report"""
        try:
            # Xóa report trước (nếu có)
            report = Reports.get_by_server_id(self.server_id)
            if report:
                db.session.delete(report)
            
            # Sau đó xóa target
            db.session.delete(self)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error deleting target: {str(e)}")


class Reports(db.Model):
    __tablename__ = 'reports'
    
    report_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    server_id = db.Column(db.Integer, db.ForeignKey('targets.server_id'), nullable=False, unique=True)
    nmap = db.Column(db.Text, nullable=True)
    dirsearch = db.Column(db.Text, nullable=True)
    wappalyzer = db.Column(db.Text, nullable=True)
    wpscan = db.Column(db.Text, nullable=True)
    pocs = db.Column(db.Text, nullable=True)
    update_nmap = db.Column(db.String(255), nullable=True)
    update_dirsearch = db.Column(db.String(255), nullable=True)
    update_wappalyzer = db.Column(db.String(255), nullable=True)
    update_wpscan = db.Column(db.String(255), nullable=True)
    update_pocs = db.Column(db.String(255), nullable=True)
    

    def __init__(self, server_id, nmap=None, dirsearch=None, wappalyzer=None, wpscan=None, pocs=None, 
                 update_nmap=None, update_dirsearch=None, update_wappalyzer=None, update_wpscan=None, update_pocs=None):
        self.server_id = server_id
        self.nmap = nmap
        self.dirsearch = dirsearch
        self.wappalyzer = wappalyzer
        self.wpscan = wpscan
        self.pocs = pocs
        self.update_nmap = update_nmap
        self.update_dirsearch = update_dirsearch
        self.update_wappalyzer = update_wappalyzer
        self.update_wpscan = update_wpscan
        self.update_pocs = update_pocs

    def to_dict(self):
        return {
            'report_id': self.report_id,
            'server_id': self.server_id,
            'nmap': self.nmap,
            'dirsearch': self.dirsearch,
            'wappalyzer': self.wappalyzer,
            'wpscan': self.wpscan,
            'pocs': self.pocs,
            'update_nmap': self.update_nmap,
            'update_dirsearch': self.update_dirsearch,
            'update_wappalyzer': self.update_wappalyzer,
            'update_wpscan': self.update_wpscan,
            'update_pocs': self.update_pocs
        }

    @classmethod
    def create_report(cls, server_id, nmap, dirsearch, wappalyzer, wpscan, pocs, update_nmap, update_dirsearch, update_wappalyzer, update_wpscan, update_pocs):
        try:
            report = cls(
                server_id=server_id,
                nmap=nmap,
                dirsearch=dirsearch,
                wappalyzer=wappalyzer,
                wpscan=wpscan,
                pocs=pocs,
                update_nmap=update_nmap,
                update_dirsearch=update_dirsearch,
                update_wappalyzer=update_wappalyzer,
                update_wpscan=update_wpscan,
                update_pocs=update_pocs
            )
            db.session.add(report)
            db.session.commit()
            return report
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error creating report: {str(e)}")

    @classmethod
    def get_by_id(cls, report_id):
        return cls.query.filter_by(report_id=report_id).first()
    
    @classmethod
    def get_by_server_id(cls, server_id):
        return cls.query.filter_by(server_id=server_id).first()

    @classmethod
    def get_all(cls):
        return cls.query.all()

    def update(self, **kwargs):
        try:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            db.session.commit()
            return self
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error updating report: {str(e)}")

    def delete(self):
        try:
            db.session.delete(self)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error deleting report: {str(e)}")


class VerificationResults(db.Model):
    """Model for storing verification results"""
    __tablename__ = 'verification_results'
    
    result_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    poc_id = db.Column(db.String(255), nullable=True)
    poc_path = db.Column(db.String(500), nullable=True)
    target_hostname = db.Column(db.String(255), nullable=False)
    target_ip = db.Column(db.String(45), nullable=True)
    verification_date = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
    result_data = db.Column(db.Text, nullable=True)  # JSON string of result data
    status = db.Column(db.String(50), nullable=False, default='completed')
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
    
    def __init__(self, target_hostname, poc_id=None, poc_path=None, target_ip=None, 
                 result_data=None, status='completed', notes=None):
        self.target_hostname = target_hostname
        self.poc_id = poc_id
        self.poc_path = poc_path
        self.target_ip = target_ip
        self.result_data = result_data
        self.status = status
        self.notes = notes
    
    def __repr__(self):
        return f'<VerificationResult {self.result_id}: {self.target_hostname}>'
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'result_id': self.result_id,
            'poc_id': self.poc_id,
            'poc_path': self.poc_path,
            'target_hostname': self.target_hostname,
            'target_ip': self.target_ip,
            'verification_date': self.verification_date.isoformat() if self.verification_date else None,
            'result_data': self.result_data,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def create_result(cls, target_hostname, poc_id=None, poc_path=None, target_ip=None, 
                     result_data=None, status='completed', notes=None):
        """Create a new verification result"""
        try:
            result = cls(
                target_hostname=target_hostname,
                poc_id=poc_id,
                poc_path=poc_path,
                target_ip=target_ip,
                result_data=result_data,
                status=status,
                notes=notes
            )
            db.session.add(result)
            db.session.commit()
            return result
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error creating verification result: {str(e)}")
    
    @classmethod
    def get_by_id(cls, result_id):
        """Get verification result by ID"""
        return cls.query.filter_by(result_id=result_id).first()
    
    @classmethod
    def get_by_target(cls, target_hostname):
        """Get verification results by target hostname"""
        return cls.query.filter_by(target_hostname=target_hostname).all()
    
    @classmethod
    def get_by_poc(cls, poc_id):
        """Get verification results by POC ID"""
        return cls.query.filter_by(poc_id=poc_id).all()
    
    @classmethod
    def get_recent_results(cls, limit=50):
        """Get recent verification results"""
        return cls.query.order_by(cls.created_at.desc()).limit(limit).all()
    
    def update(self, **kwargs):
        """Update verification result attributes"""
        try:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            self.updated_at = dt.datetime.utcnow()
            db.session.commit()
            return self
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error updating verification result: {str(e)}")
    
    def delete(self):
        """Delete verification result"""
        try:
            db.session.delete(self)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error deleting verification result: {str(e)}")


# Utility functions for database operations
class DatabaseUtils:
    """Utility class for common database operations"""
    
    # Note: Collection and CollectedFiles related methods have been removed
    # as those models have been deleted from the system
    pass



#==============================================================================================
    #    _______
    #  /        \\
    # |  ()  ()  |  <-- Reverse Shell and Webshell
    # |    __    |     Console
    #  \________/
    #    / || \
    #   /__||__\     pwncat && weevely>>
    #  |   ||   |
    #  |   ||   |     [CONNECTED]
    #  |___||___|
#phía dưới này là các DB liên quan đến quản lý Shell
# gốm 1 bảng lưu các thông tin quản lý shell
# và 1 bảng lưu các dữ liệu liên quan tói command shell
class ShellStatus(Enum):
    LISTENING = "listening"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    CLOSED = "closed"

class ShellType(Enum):
    REVERSE = "reverse"
    BIND = "bind"
    WEBSHELL = "webshell"
    SSH = "ssh"

class ShellConnection(db.Model):
    """Model for managing reverse shell connections"""
    __tablename__ = 'shell_connections'
    
    connection_id = db.Column(db.String(255), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    shell_type = db.Column(db.Enum(ShellType), nullable=False)
    status = db.Column(db.Enum(ShellStatus), nullable=False, default=ShellStatus.CLOSED)
    
    # Connection details
    local_ip = db.Column(db.String(45), nullable=True)
    local_port = db.Column(db.Integer, nullable=True)
    remote_ip = db.Column(db.String(45), nullable=True)
    remote_port = db.Column(db.Integer, nullable=True)
    
    # Target information
    target_id = db.Column(db.Integer, db.ForeignKey('targets.server_id'), nullable=True)
    hostname = db.Column(db.String(255), nullable=True)
    url = db.Column(db.String(255), nullable=True)
    
    # Session information
    user = db.Column(db.String(100), nullable=True)
    os_info = db.Column(db.String(255), nullable=True)
    privilege_level = db.Column(db.String(50), nullable=True)
    password = db.Column(db.String(255), nullable=True)
    
    # Timing
    connect_time = db.Column(db.DateTime, nullable=True)
    disconnect_time = db.Column(db.DateTime, nullable=True)
    last_active = db.Column(db.DateTime, nullable=True)
    
    # Statistics
    reconnect_count = db.Column(db.Integer, default=0)
    command_count = db.Column(db.Integer, default=0)
    data_transferred = db.Column(db.BigInteger, default=0)  # bytes
    
    # Process management
    process_id = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    # Metadata
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
    
    # Relationships
    target = db.relationship(Targets, backref='shell_connections')
    commands = db.relationship('ShellCommand', backref='connection', lazy=True, cascade='all, delete-orphan')   
    def __init__(self, connection_id, name, shell_type, local_ip=None, local_port=None, 
                 remote_ip=None, remote_port=None, target_id=None, hostname=None, url=None, 
                 status=ShellStatus.CLOSED, created_at=None, updated_at=None, password=None, notes=None):
        self.connection_id = connection_id
        self.name = name
        self.shell_type = shell_type
        self.local_ip = local_ip
        self.local_port = local_port
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        self.target_id = target_id
        self.hostname = hostname
        self.url = url
        self.password = password
        self.connect_time = dt.datetime.utcnow()
        self.last_active = dt.datetime.utcnow()
        self.status = status
        self.notes = notes
        self.created_at = created_at
        self.updated_at = updated_at
    
    def __repr__(self):
        return f'<ShellConnection {self.connection_id}: {self.name}>'
    
    def to_dict(self):
        return {
            'connection_id': self.connection_id,
            'name': self.name,
            'shell_type': self.shell_type.value if self.shell_type else None,
            'status': self.status.value if self.status else None,
            'local_ip': self.local_ip,
            'local_port': self.local_port,
            'remote_ip': self.remote_ip,
            'remote_port': self.remote_port,
            'target_id': self.target_id,
            'hostname': self.hostname,
            'url': self.url,
            'user': self.user,
            'os_info': self.os_info,
            'privilege_level': self.privilege_level,
            'connect_time': self.connect_time.isoformat() if self.connect_time else None,
            'disconnect_time': self.disconnect_time.isoformat() if self.disconnect_time else None,
            'last_active': self.last_active.isoformat() if self.last_active else None,
            'reconnect_count': self.reconnect_count,
            'command_count': self.command_count,
            'data_transferred': self.data_transferred,
            'process_id': self.process_id,
            'is_active': self.is_active,
            'notes': self.notes,
            'password': self.password,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def create_connection(cls, connection_id, name, shell_type, **kwargs):
        """Create a new shell connection"""
        try:
            connection = cls(connection_id, name, shell_type, **kwargs)
            db.session.add(connection)
            db.session.commit()
            return connection
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error creating shell connection: {str(e)}")
    @classmethod
    def get_by_id(cls, connection_id):
        """Get connection by ID"""
        return cls.query.filter_by(connection_id=connection_id).first()
    
    @classmethod
    def get_active_connections(cls):
        """active connections"""
        return cls.query.filter_by(is_active=True).all()
    
    @classmethod
    def get_by_status(cls, status):
        """Get connections by status"""
        return cls.query.filter_by(status=status).all()
    
    @classmethod
    def get_by_target(cls, target_id):
        """et connections for a specific target"""
        return cls.query.filter_by(target_id=target_id).all()
    
    @classmethod
    def search(cls, keyword=None, page=None, per_page=None, sort_type=None):
        """Tìm kiếm shell connections theo name, hostname, IP, user, status, shell_type"""
        query = cls.query
        if keyword:
            search_term = f"%{keyword}%"
            query = query.filter(
                or_(
                    getattr(cls, 'name').ilike(search_term),
                    getattr(cls, 'hostname').ilike(search_term),
                    getattr(cls, 'local_ip').ilike(search_term),
                    getattr(cls, 'local_port').ilike(search_term),
                    getattr(cls, 'remote_ip').ilike(search_term),
                    getattr(cls, 'remote_port').ilike(search_term),
                    getattr(cls, 'user').ilike(search_term),
                    getattr(cls, 'status').ilike(search_term),
                    getattr(cls, 'shell_type').ilike(search_term)
                )
            )
        # Apply sorting
        if sort_type:
            if sort_type == 'name':
                query = query.order_by(asc(getattr(cls, 'name')))
            elif sort_type == 'created_at_desc':
                query = query.order_by(desc(getattr(cls, 'created_at')))
            elif sort_type == 'created_at_asc':
                query = query.order_by(asc(getattr(cls, 'created_at')))
            elif sort_type == 'updated_at_desc':
                query = query.order_by(desc(getattr(cls, 'updated_at')))
            elif sort_type == 'updated_at_asc':
                query = query.order_by(asc(getattr(cls, 'updated_at')))
            elif sort_type == 'status':
                query = query.order_by(asc(getattr(cls, 'status')))
            elif sort_type == 'shell_type':
                query = query.order_by(asc(getattr(cls, 'shell_type')))
            else:
                query = query.order_by(desc(getattr(cls, 'created_at')))
        else:
            query = query.order_by(desc(getattr(cls, 'created_at')))
        if page and per_page:
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            return pagination.items, pagination.pages
        return query.all(), None
    
    def update_status(self, status, **kwargs):
        """Update connection status and other fields"""
        try:
            self.status = status
            self.last_active = dt.datetime.utcnow()
            
            if status == ShellStatus.DISCONNECTED or status == ShellStatus.CLOSED:
                self.disconnect_time = dt.datetime.utcnow()
                self.is_active = False
            elif status == ShellStatus.CONNECTED:
                self.connect_time = dt.datetime.utcnow()
                self.is_active = True      
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            
            db.session.commit()
            return self
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error updating shell connection: {str(e)}")
    
    def increment_command_count(self):
        """Increment command count"""
        self.command_count += 1
        self.last_active = dt.datetime.utcnow()
        db.session.commit()
    
    def add_data_transferred(self, bytes_count):
        """o data transferred count"""
        self.data_transferred += bytes_count
        self.last_active = dt.datetime.utcnow()
        db.session.commit()
    
    def delete(self):
        """Delete connection"""
        try:
            db.session.delete(self)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error deleting shell connection: {str(e)}")


class ShellCommand(db.Model):
    """Model for storing shell commands and their outputs"""
    __tablename__ = 'shell_commands'
    command_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    connection_id = db.Column(db.String(255), db.ForeignKey('shell_connections.connection_id'), nullable=False)
    
    # Command details
    command = db.Column(db.Text, nullable=False)
    output = db.Column(db.Text, nullable=True)
    exit_code = db.Column(db.Integer, nullable=True)
    
    # Timing
    executed_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    duration_ms = db.Column(db.Integer, nullable=True)  # milliseconds
    
    # Metadata
    success = db.Column(db.Boolean, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    
    def __init__(self, connection_id, command, output=None, exit_code=None, 
                 completed_at=None, duration_ms=None, success=None, error_message=None):
        self.connection_id = connection_id
        self.command = command
        self.output = output
        self.exit_code = exit_code
        self.completed_at = completed_at
        self.duration_ms = duration_ms
        self.success = success
        self.error_message = error_message
    
    def __repr__(self):
        return f'<ShellCommand {self.command_id}: {self.command[:50]}...>'
    
    def to_dict(self):
        return {
            'command_id': self.command_id,
            'connection_id': self.connection_id,
            'command': self.command,
            'output': self.output,
            'exit_code': self.exit_code,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_ms': self.duration_ms,
            'success': self.success,
            'error_message': self.error_message
        }
    
    @classmethod
    def create_command(cls, connection_id, command, **kwargs):
        """Create a new shell command record"""
        try:
            cmd = cls(connection_id, command, **kwargs)
            db.session.add(cmd)
            db.session.commit()
            return cmd
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error creating shell command: {str(e)}")
    @classmethod
    def get_by_connection(cls, connection_id, limit=100):
        """Get commands for a specific connection"""
        return cls.query.filter_by(connection_id=connection_id).order_by(desc(cls.executed_at)).limit(limit).all()
    
    def complete(self, output=None, exit_code=None, success=None, error_message=None):
        """mmand as completed"""
        try:
            self.output = output
            self.exit_code = exit_code
            self.success = success
            self.error_message = error_message
            self.completed_at = dt.datetime.utcnow()
            
            if self.executed_at and self.completed_at:
                self.duration_ms = int((self.completed_at - self.executed_at).total_seconds() * 1000)
            db.session.commit()
            return self
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error completing shell command: {str(e)}")


class DataFile(db.Model):
    __tablename__ = 'data_files'
    file_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    file_name = db.Column(db.String(255), nullable=False)
    source_path = db.Column(db.String(500), nullable=False)
    local_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    file_hash = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255), nullable=True)
    connection_id = db.Column(db.String(255), db.ForeignKey('shell_connections.connection_id'), nullable=False)
    file_created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
    file_updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    def __init__(self, file_name, source_path, local_path, file_type, file_size, file_hash, connection_id, file_created_at, file_updated_at, password = ''):
        self.file_name = file_name
        self.source_path = source_path
        self.local_path = local_path
        self.file_type = file_type
        self.file_size = file_size
        self.file_hash = file_hash
        self.connection_id = connection_id
        self.file_created_at = file_created_at
        self.file_updated_at = file_updated_at
        self.password = password
    
    def __repr__(self):
        return f'<DataFile {self.file_id}: {self.file_name}>'
    
    def to_dict(self):
        return {
            'file_id': self.file_id,
            'file_name': self.file_name,
            'source_path': self.source_path,
            'local_path': self.local_path,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'file_size_readable': self.get_file_size_readable(),
            'file_hash': self.file_hash,
            'password': self.password,
            'connection_id': self.connection_id,
            'file_created_at': self.file_created_at.isoformat() if self.file_created_at else None,
            'file_updated_at': self.file_updated_at.isoformat() if self.file_updated_at else None
        }
    
    @classmethod
    def create_file(cls, file_name, source_path, local_path, file_type, file_size, file_hash, connection_id):
        """Create a new data file record"""
        try:
            data_file = cls(file_name, source_path, local_path, file_type, file_size, file_hash, connection_id)
            db.session.add(data_file)
            db.session.commit()
            return data_file
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error creating data file: {str(e)}")
    
    @classmethod
    def get_by_connection(cls, connection_id, limit=100):
        """Get files for a specific connection"""
        return cls.query.filter_by(connection_id=connection_id).order_by(desc(cls.file_created_at)).limit(limit).all()
    
    @classmethod
    def get_by_file_hash(cls, file_hash):
        """Get file by hash to check for duplicates"""
        return cls.query.filter_by(file_hash=file_hash).first()
    
    @classmethod
    def get_by_id(cls, file_id):
        """Get file by ID"""
        return cls.query.filter_by(file_id=file_id).first()

    @classmethod
    def get_by_file_name(cls, file_name):
        """Get file by name"""
        return cls.query.filter_by(file_name=file_name).first()
    
    @classmethod
    def update_file_info(self, **kwargs):
        """Update file information"""
        try:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            
            self.file_updated_at = dt.datetime.utcnow()
            db.session.commit()
            return self
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error updating file info: {str(e)}")
    
    def delete_file(self):
        """Delete file record"""
        try:
            db.session.delete(self)
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error deleting file record: {str(e)}")
    
    @classmethod
    def search_files(cls, search_keyword=None, folder_type='upload', limit=100):
        """Search files with filters"""
        from sqlalchemy import or_, desc
        
        query = cls.query
        
        if search_keyword:
            search_term = f"%{search_keyword}%"
            query = query.filter(
                or_(
                    cls.file_name.ilike(search_term),
                    cls.connection_id.ilike(search_term)
                )
            )
        
        # Lấy theo loại folder
        query = query.filter_by(file_type=folder_type)
        
        return query.order_by(desc(cls.file_created_at)).limit(limit).all()
    
    def get_file_size_readable(self):
        """Get human readable file size"""
        bytes_size = self.file_size or 0
        if bytes_size == 0:
            return "0 B"
        
        try:
            size_name = ["B", "KB", "MB", "GB", "TB"]
            i = int(math.floor(math.log(bytes_size, 1024)))
            p = math.pow(1024, i)
            s = round(bytes_size / p, 2)
            return f"{s} {size_name[i]}"
        except (ValueError, OverflowError):
            return f"{bytes_size} B" 


class CronJob(db.Model):
    """Model for managing cron jobs"""
    __tablename__ = 'cron_jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Cron scheduling
    cron_expression = db.Column(db.String(100), nullable=False)  # e.g., "*/5 * * * *"
    timezone = db.Column(db.String(50), default='UTC')
    
    # Job configuration
    job_type = db.Column(db.String(50), nullable=False)  # 'file_operation', 'command', 'download', 'upload'
    job_data = db.Column(db.Text, nullable=False)  # JSON string with job parameters
    
    # Weevely connection
    weevely_connection_id = db.Column(db.String(255), nullable=True)
    
    # Status and execution
    is_active = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime, nullable=True)
    next_run = db.Column(db.DateTime, nullable=True)
    run_count = db.Column(db.Integer, default=0)
    success_count = db.Column(db.Integer, default=0)
    failure_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
    
    def __init__(self, **kwargs):
        super(CronJob, self).__init__(**kwargs)
    
    def __repr__(self):
        return f"<CronJob {self.name} ({self.cron_expression})>"
    
    @classmethod
    def find_by_id(cls, _id: int) -> "CronJob":
        return cls.query.filter_by(id=_id).first()
    
    @classmethod
    def get_active_jobs(cls):
        return cls.query.filter_by(is_active=True).all()
    
    @classmethod
    def get_by_weevely_connection(cls, connection_id: str):
        return cls.query.filter_by(weevely_connection_id=connection_id).all()
    
    def save(self) -> None:
        try:
            db.session.add(self)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            db.session.close()
            error = str(e.__dict__['orig'])
            raise InvalidUsage(error, 422)
    
    def delete(self) -> None:
        try:
            db.session.delete(self)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            db.session.close()
            error = str(e.__dict__['orig'])
            raise InvalidUsage(error, 422)
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'cron_expression': self.cron_expression,
            'timezone': self.timezone,
            'job_type': self.job_type,
            'job_data': self.job_data,
            'weevely_connection_id': self.weevely_connection_id,
            'is_active': self.is_active,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'next_run': self.next_run.isoformat() if self.next_run else None,
            'run_count': self.run_count,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        } 