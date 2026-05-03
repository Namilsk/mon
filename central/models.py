import os
import hashlib
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

    @staticmethod
    def hash_password(password):
        salt = os.urandom(32)
        pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        return salt + pwdhash

    def verify_password(self, password):
        salt = self.password_hash[:32]
        stored_hash = self.password_hash[32:]
        pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        return pwdhash == stored_hash

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active
        }


class Node(db.Model):
    __tablename__ = 'nodes'

    id = db.Column(db.String(100), primary_key=True)
    hostname = db.Column(db.String(100))
    platform = db.Column(db.String(50))
    ip_address = db.Column(db.String(50))
    poll_interval = db.Column(db.Integer, default=5)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime)
    config = db.Column(db.JSON, default=dict)

    metrics = db.relationship('Metric', backref='node', lazy='dynamic', cascade='all, delete-orphan')
    alerts = db.relationship('Alert', backref='node', lazy='dynamic', cascade='all, delete-orphan')
    processes = db.relationship('ProcessStat', backref='node', lazy='dynamic', cascade='all, delete-orphan')

    def is_online(self):
        if not self.last_seen:
            return False
        return (datetime.utcnow() - self.last_seen).total_seconds() < 30

    def to_dict(self):
        return {
            'id': self.id,
            'hostname': self.hostname,
            'platform': self.platform,
            'ip_address': self.ip_address,
            'poll_interval': self.poll_interval,
            'is_active': self.is_active,
            'online': self.is_online(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'config': self.config or {}
        }


class Metric(db.Model):
    __tablename__ = 'metrics'

    id = db.Column(db.Integer, primary_key=True)
    node_id = db.Column(db.String(100), db.ForeignKey('nodes.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    cpu_percent = db.Column(db.Float)
    memory_percent = db.Column(db.Float)
    memory_used_mb = db.Column(db.Float)
    memory_total_mb = db.Column(db.Float)
    disk_percent = db.Column(db.Float)
    disk_used_gb = db.Column(db.Float)
    disk_total_gb = db.Column(db.Float)
    bytes_sent = db.Column(db.BigInteger)
    bytes_recv = db.Column(db.BigInteger)
    packets_sent = db.Column(db.BigInteger)
    packets_recv = db.Column(db.BigInteger)
    load_avg_1 = db.Column(db.Float)
    load_avg_5 = db.Column(db.Float)
    load_avg_15 = db.Column(db.Float)
    boot_time = db.Column(db.DateTime)

    def to_dict(self):
        return {
            'id': self.id,
            'node_id': self.node_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'memory_used_mb': self.memory_used_mb,
            'memory_total_mb': self.memory_total_mb,
            'disk_percent': self.disk_percent,
            'disk_used_gb': self.disk_used_gb,
            'disk_total_gb': self.disk_total_gb,
            'bytes_sent': self.bytes_sent,
            'bytes_recv': self.bytes_recv,
            'packets_sent': self.packets_sent,
            'packets_recv': self.packets_recv,
            'load_avg_1': self.load_avg_1,
            'load_avg_5': self.load_avg_5,
            'load_avg_15': self.load_avg_15,
            'boot_time': self.boot_time.isoformat() if self.boot_time else None
        }


class ProcessStat(db.Model):
    __tablename__ = 'process_stats'

    id = db.Column(db.Integer, primary_key=True)
    node_id = db.Column(db.String(100), db.ForeignKey('nodes.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    pid = db.Column(db.Integer)
    name = db.Column(db.String(100))
    cpu_percent = db.Column(db.Float)
    memory_percent = db.Column(db.Float)
    memory_mb = db.Column(db.Float)
    username = db.Column(db.String(50))
    command = db.Column(db.Text)

    def to_dict(self):
        return {
            'id': self.id,
            'node_id': self.node_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'pid': self.pid,
            'name': self.name,
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'memory_mb': self.memory_mb,
            'username': self.username,
            'command': self.command
        }


class Alert(db.Model):
    __tablename__ = 'alerts'

    id = db.Column(db.Integer, primary_key=True)
    node_id = db.Column(db.String(100), db.ForeignKey('nodes.id'), nullable=False)
    alert_type = db.Column(db.String(50), nullable=False)
    severity = db.Column(db.String(20), default='warning')
    message = db.Column(db.Text)
    threshold = db.Column(db.Float)
    actual_value = db.Column(db.Float)
    is_resolved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            'id': self.id,
            'node_id': self.node_id,
            'alert_type': self.alert_type,
            'severity': self.severity,
            'message': self.message,
            'threshold': self.threshold,
            'actual_value': self.actual_value,
            'is_resolved': self.is_resolved,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }


class AlertConfig(db.Model):
    __tablename__ = 'alert_configs'

    id = db.Column(db.Integer, primary_key=True)
    node_id = db.Column(db.String(100), db.ForeignKey('nodes.id'), nullable=True)
    cpu_threshold = db.Column(db.Float, default=80.0)
    memory_threshold = db.Column(db.Float, default=85.0)
    disk_threshold = db.Column(db.Float, default=90.0)
    load_threshold = db.Column(db.Float, default=5.0)
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'node_id': self.node_id,
            'cpu_threshold': self.cpu_threshold,
            'memory_threshold': self.memory_threshold,
            'disk_threshold': self.disk_threshold,
            'load_threshold': self.load_threshold,
            'enabled': self.enabled
        }
