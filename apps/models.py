# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
from email.policy import default
from apps import db
from sqlalchemy.exc import SQLAlchemyError
from apps.exceptions.exception import InvalidUsage
import datetime as dt
from sqlalchemy.orm import relationship
from enum import Enum
from sqlalchemy import or_

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


class Incidents(db.Model):
    __tablename__ = 'incidents'
    
    incident_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    incident_type = db.Column(db.Enum(IncidentType), nullable=False)
    target_device = db.Column(db.String(255), nullable=True)
    resolution_status = db.Column(db.Enum(ResolutionStatus), nullable=False, default=ResolutionStatus.OPEN)
    impact_summary = db.Column(db.Text, nullable=True)
    related_email_id = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
    
    
    
    def __init__(self, incident_type, target_device=None, resolution_status=ResolutionStatus.OPEN, 
                 impact_summary=None, related_email_id=None):
        self.incident_type = incident_type
        self.target_device = target_device
        self.resolution_status = resolution_status
        self.impact_summary = impact_summary
        self.related_email_id = related_email_id
    
    def __repr__(self):
        return f'<Incident {self.incident_id}: {self.incident_type.value}>'
    
    def to_dict(self):
        return {
            'incident_id': self.incident_id,
            'incident_type': self.incident_type.value if self.incident_type else None,
            'target_device': self.target_device,
            'resolution_status': self.resolution_status.value if self.resolution_status else None,
            'impact_summary': self.impact_summary,
            'related_email_id': self.related_email_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def create_incident(cls, incident_type, target_device=None, impact_summary=None, related_email_id=None):
        """Create a new incident"""
        try:
            incident = cls(
                incident_type=incident_type,
                target_device=target_device,
                impact_summary=impact_summary,
                related_email_id=related_email_id
            )
            db.session.add(incident)
            db.session.commit()
            return incident
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error creating incident: {str(e)}")
    
    @classmethod
    def get_by_id(cls, incident_id):
        """Get incident by ID"""
        return cls.query.filter_by(incident_id=incident_id).first()
    
    @classmethod
    def get_by_status(cls, status):
        """Get incidents by resolution status"""
        return cls.query.filter_by(resolution_status=status).all()
    
    def update(self, **kwargs):
        """Update incident attributes"""
        try:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            self.updated_at = dt.datetime.utcnow()
            db.session.commit()
            return self
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error updating incident: {str(e)}")
    
    def delete(self):
        """Delete incident"""
        try:
            db.session.delete(self)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error deleting incident: {str(e)}")


class Targets(db.Model):
    __tablename__ = 'targets'
    
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
    
        
    def __init__(self, hostname, ip_address, server_type, os=None, location=None, 
                 status='active', privilege_escalation=None, exploitation_level=None, 
                 incident_id=None, notes=None):
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
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def create_target(cls, hostname, ip_address, server_type, **kwargs):
        """Create a new target"""
        try:
            target = cls(hostname=hostname, ip_address=ip_address, server_type=server_type, **kwargs)
            db.session.add(target)
            db.session.commit()
            print(target)
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
    def search(cls, keyword, page=None, per_page=None):
        """Tìm kiếm targets theo hostname, ip_address, server_type hoặc status"""
        print(f"[x] keyword: {keyword} & page={page} & per_page={per_page}")
        query = Targets.query
        if keyword:
            search_term = f"%{keyword}%"
            query =  query.filter(
                or_(
                    Targets.hostname.ilike(search_term),
                    Targets.ip_address.ilike(search_term),
                    Targets.server_type.ilike(search_term),
                    Targets.status.ilike(search_term),      
                    Targets.location.ilike(search_term),
                    Targets.os.ilike(search_term)
                )
            )
        print(f"QUERY: {query}")
        if page and per_page: # nếu có các giá trị của phân trang thì mình cho nó
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            print(f"[[x]]result: {pagination}")
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
        """Delete target"""
        try:
            db.session.delete(self)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error deleting target: {str(e)}")


class Credentials(db.Model):
    __tablename__ = 'credentials'
    
    credential_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('targets.server_id'), nullable=False)
    privilege_level = db.Column(db.Enum(PrivilegeLevel), nullable=False)
    breach_date = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
    
    
    def __init__(self, username, password_hash, server_id, privilege_level, 
                 breach_date=None, notes=None):
        self.username = username
        self.password_hash = password_hash
        self.server_id = server_id
        self.privilege_level = privilege_level
        self.breach_date = breach_date
        self.notes = notes
    
    def __repr__(self):
        return f'<Credential {self.credential_id}: {self.username}>'
    
    def to_dict(self):
        return {
            'credential_id': self.credential_id,
            'username': self.username,
            'password_hash': self.password_hash,
            'server_id': self.server_id,
            'privilege_level': self.privilege_level.value if self.privilege_level else None,
            'breach_date': self.breach_date.isoformat() if self.breach_date else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def create_credential(cls, username, password_hash, server_id, privilege_level, **kwargs):
        """Create a new credential"""
        try:
            # Validate target exists
            target = Targets.get_by_id(server_id)
            if not target:
                raise InvalidUsage(f"Target with ID {server_id} not found")
            
            credential = cls(
                username=username,
                password_hash=password_hash,
                server_id=server_id,
                privilege_level=privilege_level,
                **kwargs
            )
            db.session.add(credential)
            db.session.commit()
            return credential
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error creating credential: {str(e)}")
    
    @classmethod
    def get_by_id(cls, credential_id):
        """Get credential by ID"""
        return cls.query.filter_by(credential_id=credential_id).first()
    
    @classmethod
    def get_high_privilege_credentials(cls):
        """Get all high privilege credentials"""
        return cls.query.filter(
            cls.privilege_level.in_([PrivilegeLevel.HIGH, PrivilegeLevel.ADMIN, PrivilegeLevel.ROOT])
        ).all()
    
    def update(self, **kwargs):
        """Update credential attributes"""
        try:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            self.updated_at = dt.datetime.utcnow()
            db.session.commit()
            return self
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error updating credential: {str(e)}")
    
    def delete(self):
        """Delete credential"""
        try:
            db.session.delete(self)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error deleting credential: {str(e)}")


class VulInTarget(db.Model):
    __tablename__ = 'vul_in_target'
    
    id_vul_in_target = db.Column(db.Integer, primary_key=True, autoincrement=True)
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.incident_id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('targets.server_id'), nullable=False)
    attack_vector = db.Column(db.String(255), nullable=False)
    detection_date = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)
    resolution_status = db.Column(db.Enum(ResolutionStatus), nullable=False, default=ResolutionStatus.OPEN)
    impact_summary = db.Column(db.Text, nullable=True)
    related_email_id = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
    
    
    def __init__(self, incident_id, server_id, attack_vector, detection_date=None,
                 resolution_status=ResolutionStatus.OPEN, impact_summary=None, related_email_id=None):
        self.incident_id = incident_id
        self.server_id = server_id
        self.attack_vector = attack_vector
        self.detection_date = detection_date or dt.datetime.utcnow()
        self.resolution_status = resolution_status
        self.impact_summary = impact_summary
        self.related_email_id = related_email_id
    
    def __repr__(self):
        return f'<VulInTarget {self.id_vul_in_target}: {self.attack_vector}>'
    
    def to_dict(self):
        return {
            'id_vul_in_target': self.id_vul_in_target,
            'incident_id': self.incident_id,
            'server_id': self.server_id,
            'attack_vector': self.attack_vector,
            'detection_date': self.detection_date.isoformat() if self.detection_date else None,
            'resolution_status': self.resolution_status.value if self.resolution_status else None,
            'impact_summary': self.impact_summary,
            'related_email_id': self.related_email_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def create_vulnerability(cls, incident_id, server_id, attack_vector, **kwargs):
        """Create a new vulnerability in target"""
        try:
            # Validate incident and target exist
            incident = Incidents.get_by_id(incident_id)
            target = Targets.get_by_id(server_id)
            
            if not incident:
                raise InvalidUsage(f"Incident with ID {incident_id} not found")
            if not target:
                raise InvalidUsage(f"Target with ID {server_id} not found")
            
            vulnerability = cls(
                incident_id=incident_id,
                server_id=server_id,
                attack_vector=attack_vector,
                **kwargs
            )
            db.session.add(vulnerability)
            db.session.commit()
            return vulnerability
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error creating vulnerability: {str(e)}")
    
    @classmethod
    def get_by_id(cls, id_vul_in_target):
        """Get vulnerability by ID"""
        return cls.query.filter_by(id_vul_in_target=id_vul_in_target).first()
    
    def update(self, **kwargs):
        """Update vulnerability attributes"""
        try:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            self.updated_at = dt.datetime.utcnow()
            db.session.commit()
            return self
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error updating vulnerability: {str(e)}")
    
    def delete(self):
        """Delete vulnerability"""
        try:
            db.session.delete(self)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error deleting vulnerability: {str(e)}")


class Collections(db.Model):
    """Model for Collections table"""
    __tablename__ = 'collections'
    
    collection_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    server_id = db.Column(db.Integer, db.ForeignKey('targets.server_id'), nullable=False)
    collected_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
    folder_archive_path = db.Column(db.Text, nullable=True)
    db_size_mb = db.Column(db.Float, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    
    def __init__(self, server_id, folder_archive_path=None, db_size_mb=None, notes=None):
        self.server_id = server_id
        self.folder_archive_path = folder_archive_path
        self.db_size_mb = db_size_mb
        self.notes = notes
    
    def __repr__(self):
        return f'<Collection {self.collection_id}: Server {self.server_id}>'
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'collection_id': self.collection_id,
            'server_id': self.server_id,
            'collected_at': self.collected_at.isoformat() if self.collected_at else None,
            'folder_archive_path': self.folder_archive_path,
            'db_size_mb': self.db_size_mb,
            'notes': self.notes,
            'collected_files_count': len(self.collected_files) if self.collected_files else 0,
            'target_hostname': self.target.hostname if self.target else None
        }
    
    @classmethod
    def create_collection(cls, server_id, folder_archive_path=None, db_size_mb=None, notes=None):
        """Create a new collection"""
        try:
            # Validate target exists
            target = Targets.get_by_id(server_id)
            if not target:
                raise InvalidUsage(f"Target with ID {server_id} not found")
            
            collection = cls(
                server_id=server_id,
                folder_archive_path=folder_archive_path,
                db_size_mb=db_size_mb,
                notes=notes
            )
            db.session.add(collection)
            db.session.commit()
            return collection
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error creating collection: {str(e)}")
    
    @classmethod
    def get_by_id(cls, collection_id):
        """Get collection by ID"""
        return cls.query.filter_by(collection_id=collection_id).first()
    
    @classmethod
    def get_by_server_id(cls, server_id):
        """Get collections by server ID"""
        return cls.query.filter_by(server_id=server_id).all()
    
    def update(self, **kwargs):
        """Update collection attributes"""
        try:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            db.session.commit()
            return self
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error updating collection: {str(e)}")
    
    def delete(self):
        """Delete collection and all associated files"""
        try:
            db.session.delete(self)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error deleting collection: {str(e)}")


class CollectedFiles(db.Model):
    """Model for CollectedFiles table"""
    __tablename__ = 'collected_files'
    
    file_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    collection_id = db.Column(db.Integer, db.ForeignKey('collections.collection_id'), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.Text, nullable=False)
    file_archive_path = db.Column(db.Text, nullable=True)
    file_size_kb = db.Column(db.Float, nullable=True)
    file_type = db.Column(db.Enum(FileType), nullable=True)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    
    
    def __init__(self, collection_id, file_name, file_path, file_archive_path=None, 
                 file_size_kb=None, file_type=None, notes=None):
        self.collection_id = collection_id
        self.file_name = file_name
        self.file_path = file_path
        self.file_archive_path = file_archive_path
        self.file_size_kb = file_size_kb
        self.file_type = file_type
        self.notes = notes
    
    def __repr__(self):
        return f'<CollectedFile {self.file_id}: {self.file_name}>'
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'file_id': self.file_id,
            'collection_id': self.collection_id,
            'file_name': self.file_name,
            'file_path': self.file_path,
            'file_archive_path': self.file_archive_path,
            'file_size_kb': self.file_size_kb,
            'file_type': self.file_type.value if self.file_type else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'notes': self.notes
        }
    
    @classmethod
    def create_file(cls, collection_id, file_name, file_path, file_archive_path=None,
                    file_size_kb=None, file_type=None, notes=None):
        """Create a new collected file"""
        try:
            # Validate collection exists
            collection = Collections.get_by_id(collection_id)
            if not collection:
                raise InvalidUsage(f"Collection with ID {collection_id} not found")
            
            collected_file = cls(
                collection_id=collection_id,
                file_name=file_name,
                file_path=file_path,
                file_archive_path=file_archive_path,
                file_size_kb=file_size_kb,
                file_type=file_type,
                notes=notes
            )
            db.session.add(collected_file)
            db.session.commit()
            return collected_file
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error creating collected file: {str(e)}")
    
    @classmethod
    def get_by_id(cls, file_id):
        """Get collected file by ID"""
        return cls.query.filter_by(file_id=file_id).first()
    
    @classmethod
    def get_by_collection_id(cls, collection_id):
        """Get all files in a collection"""
        return cls.query.filter_by(collection_id=collection_id).all()
    
    @classmethod
    def get_by_file_type(cls, file_type):
        """Get all files of a specific type"""
        return cls.query.filter_by(file_type=file_type).all()
    
    def update(self, **kwargs):
        """Update collected file attributes"""
        try:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            db.session.commit()
            return self
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error updating collected file: {str(e)}")
    
    def delete(self):
        """Delete collected file"""
        try:
            db.session.delete(self)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidUsage(f"Error deleting collected file: {str(e)}")



# Utility functions for database operations
class DatabaseUtils:
    """Utility class for common database operations"""
    
    @staticmethod
    def get_collection_with_files(collection_id):
        """Get collection with all its files"""
        collection = Collections.get_by_id(collection_id)
        if not collection:
            raise InvalidUsage(f"Collection with ID {collection_id} not found")
        
        return {
            'collection': collection.to_dict(),
            'files': [file.to_dict() for file in collection.collected_files]
        }
    
    @staticmethod
    def get_collections_summary():
        """Get summary of all collections"""
        collections = Collections.query.all()
        summary = []
        
        for collection in collections:
            files_count = len(collection.collected_files)
            total_size_kb = sum(
                file.file_size_kb for file in collection.collected_files 
                if file.file_size_kb is not None
            )
            
            summary.append({
                'collection_id': collection.collection_id,
                'server_id': collection.server_id,
                'collected_at': collection.collected_at.isoformat(),
                'files_count': files_count,
                'total_size_kb': total_size_kb,
                'total_size_mb': round(total_size_kb / 1024, 2) if total_size_kb > 0 else 0
            })
        
        return summary
    
    @staticmethod
    def search_files(query, file_type=None, collection_id=None):
        """Search files by name with optional filters"""
        search_query = CollectedFiles.query
        
        # Filter by file name
        if query:
            search_query = search_query.filter(
                CollectedFiles.file_name.ilike(f'%{query}%')
            )
        
        # Filter by file type
        if file_type:
            search_query = search_query.filter(CollectedFiles.file_type == file_type)
        
        # Filter by collection
        if collection_id:
            search_query = search_query.filter(CollectedFiles.collection_id == collection_id)
        
        return search_query.all()