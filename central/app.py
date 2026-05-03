import os
import json
import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict
from functools import wraps

from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_sock import Sock
from flask_migrate import Migrate
import jwt

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from models import db, User, Node, Metric, ProcessStat, Alert, AlertConfig

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    f'sqlite:///{os.path.join(os.path.dirname(__file__), "data", "monitor.db")}'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)
sock = Sock(app)

JWT_SECRET = os.environ.get('JWT_SECRET', 'dev-secret-change-me')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin')
DATA_DIR = os.environ.get('DATA_DIR', os.path.join(os.path.dirname(__file__), 'data'))
os.makedirs(DATA_DIR, exist_ok=True)


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        client_ip = request.remote_addr
        if not token:
            logger.warning(f"401 from {client_ip}: Token missing")
            return jsonify({'error': 'Token missing'}), 401
        try:
            token = token.replace('Bearer ', '')
            jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            logger.info(f"200 from {client_ip}: Valid token")
        except jwt.InvalidSignatureError:
            logger.error(f"401 from {client_ip}: Invalid signature")
            return jsonify({'error': 'Invalid token signature'}), 401
        except jwt.ExpiredSignatureError:
            logger.warning(f"401 from {client_ip}: Token expired")
            return jsonify({'error': 'Token expired'}), 401
        except Exception as e:
            logger.error(f"401 from {client_ip}: {str(e)}")
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    return decorated


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        if not session.get('is_admin'):
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


def create_default_admin():
    """Create default admin user if no users exist."""
    with app.app_context():
        if User.query.count() == 0:
            admin = User(
                username='admin',
                email='admin@localhost',
                password_hash=User.hash_password(ADMIN_PASSWORD),
                is_admin=True,
                is_active=True
            )
            db.session.add(admin)
            db.session.commit()
            logger.info(f"Created default admin user (password: {ADMIN_PASSWORD})")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        user = User.query.filter_by(username=username, is_active=True).first()
        
        if user and user.verify_password(password):
            session['authenticated'] = True
            session['username'] = username
            session['user_id'] = user.id
            session['is_admin'] = user.is_admin
            user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('dashboard'))
        
        return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm = request.form.get('confirm', '').strip()
        
        if not username or not email or not password:
            return render_template('register.html', error='All fields required')
        
        if password != confirm:
            return render_template('register.html', error='Passwords do not match')
        
        if User.query.filter_by(username=username).first():
            return render_template('register.html', error='Username already exists')
        
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error='Email already exists')
        
        # First user becomes admin
        is_first = User.query.count() == 0
        
        user = User(
            username=username,
            email=email,
            password_hash=User.hash_password(password),
            is_admin=is_first,
            is_active=True
        )
        db.session.add(user)
        db.session.commit()
        
        session['authenticated'] = True
        session['username'] = username
        session['user_id'] = user.id
        session['is_admin'] = user.is_admin
        
        return redirect(url_for('dashboard'))
    
    return render_template('register.html')


@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')


@app.route('/node/<node_id>')
@login_required
def node_detail(node_id):
    node = Node.query.get(node_id)
    if not node:
        return redirect(url_for('dashboard'))
    return render_template('node_detail.html', node_id=node_id)


@app.route('/api/nodes')
@login_required
def get_nodes():
    nodes = Node.query.filter_by(is_active=True).all()
    return jsonify({n.id: n.to_dict() for n in nodes})


@app.route('/api/nodes/<node_id>')
@login_required
def get_node(node_id):
    node = Node.query.get(node_id)
    if not node:
        return jsonify({'error': 'Node not found'}), 404
    
    # Get last 100 metrics
    metrics = Metric.query.filter_by(node_id=node_id).order_by(Metric.timestamp.desc()).limit(100).all()
    metrics.reverse()
    
    # Get latest processes
    latest_processes = ProcessStat.query.filter_by(node_id=node_id).order_by(
        ProcessStat.timestamp.desc(), ProcessStat.cpu_percent.desc()
    ).limit(10).all()
    
    # Get active alerts
    alerts = Alert.query.filter_by(node_id=node_id, is_resolved=False).order_by(Alert.created_at.desc()).all()
    
    return jsonify({
        'info': node.to_dict(),
        'current': metrics[-1].to_dict() if metrics else None,
        'history': [m.to_dict() for m in metrics],
        'processes': [p.to_dict() for p in latest_processes],
        'alerts': [a.to_dict() for a in alerts]
    })


@app.route('/api/nodes/<node_id>/config', methods=['POST'])
@login_required
def update_config(node_id):
    node = Node.query.get(node_id)
    if not node:
        return jsonify({'error': 'Node not found'}), 404
    
    config = request.json or {}
    node.config = {**(node.config or {}), **config}
    
    if 'poll_interval' in config:
        node.poll_interval = int(config['poll_interval'])
    
    db.session.commit()
    return jsonify({'status': 'ok', 'config': node.config})


@app.route('/api/nodes/<node_id>/alerts', methods=['POST'])
@login_required
def update_alert_config(node_id):
    node = Node.query.get(node_id)
    if not node:
        return jsonify({'error': 'Node not found'}), 404
    
    data = request.json or {}
    
    alert_config = AlertConfig.query.filter_by(node_id=node_id).first()
    if not alert_config:
        alert_config = AlertConfig(node_id=node_id)
        db.session.add(alert_config)
    
    if 'cpu_threshold' in data:
        alert_config.cpu_threshold = float(data['cpu_threshold'])
    if 'memory_threshold' in data:
        alert_config.memory_threshold = float(data['memory_threshold'])
    if 'disk_threshold' in data:
        alert_config.disk_threshold = float(data['disk_threshold'])
    if 'enabled' in data:
        alert_config.enabled = bool(data['enabled'])
    
    db.session.commit()
    return jsonify({'status': 'ok', 'config': alert_config.to_dict()})


def check_alerts(node, metric):
    """Check metric against thresholds and create alerts."""
    config = AlertConfig.query.filter_by(node_id=node.id).first()
    if not config or not config.enabled:
        return
    
    checks = [
        ('cpu', metric.cpu_percent, config.cpu_threshold),
        ('memory', metric.memory_percent, config.memory_threshold),
        ('disk', metric.disk_percent, config.disk_threshold),
    ]
    
    for alert_type, value, threshold in checks:
        if value and value > threshold:
            # Check if unresolved alert already exists
            existing = Alert.query.filter_by(
                node_id=node.id, alert_type=alert_type, is_resolved=False
            ).first()
            
            if not existing:
                alert = Alert(
                    node_id=node.id,
                    alert_type=alert_type,
                    severity='warning' if value < threshold + 10 else 'critical',
                    message=f'{alert_type.upper()} usage is {value:.1f}% (threshold: {threshold}%)',
                    threshold=threshold,
                    actual_value=value
                )
                db.session.add(alert)
        else:
            # Resolve existing alert
            existing = Alert.query.filter_by(
                node_id=node.id, alert_type=alert_type, is_resolved=False
            ).first()
            if existing:
                existing.is_resolved = True
                existing.resolved_at = datetime.utcnow()
    
    db.session.commit()


@app.route('/api/metrics', methods=['POST'])
@token_required
def receive_metrics():
    data = request.json
    node_id = data.get('node_id')
    if not node_id:
        return jsonify({'error': 'node_id required'}), 400
    
    # Get or create node
    node = Node.query.get(node_id)
    if not node:
        node = Node(id=node_id)
        db.session.add(node)
    
    node.last_seen = datetime.utcnow()
    node.hostname = data.get('hostname', node.hostname)
    node.platform = data.get('platform', node.platform)
    node.ip_address = request.remote_addr
    node.poll_interval = data.get('poll_interval', node.poll_interval or 5)
    
    # Create metric record
    metric = Metric(
        node_id=node_id,
        cpu_percent=data.get('cpu_percent'),
        memory_percent=data.get('memory_percent'),
        memory_used_mb=data.get('memory_used_mb'),
        memory_total_mb=data.get('memory_total_mb'),
        disk_percent=data.get('disk_percent'),
        disk_used_gb=data.get('disk_used_gb'),
        disk_total_gb=data.get('disk_total_gb'),
        bytes_sent=data.get('network', {}).get('bytes_sent'),
        bytes_recv=data.get('network', {}).get('bytes_recv'),
        packets_sent=data.get('network', {}).get('packets_sent'),
        packets_recv=data.get('network', {}).get('packets_recv'),
        load_avg_1=data.get('load_avg', {}).get('1min'),
        load_avg_5=data.get('load_avg', {}).get('5min'),
        load_avg_15=data.get('load_avg', {}).get('15min'),
        boot_time=data.get('boot_time')
    )
    db.session.add(metric)
    
    # Store processes
    if data.get('top_processes'):
        for proc in data['top_processes']:
            process = ProcessStat(
                node_id=node_id,
                pid=proc.get('pid'),
                name=proc.get('name'),
                cpu_percent=proc.get('cpu_percent'),
                memory_percent=proc.get('memory_percent'),
                memory_mb=proc.get('memory_mb'),
                username=proc.get('username'),
                command=proc.get('command')
            )
            db.session.add(process)
    
    db.session.commit()
    
    # Check for alerts
    check_alerts(node, metric)
    
    # Clean old data (keep last 24 hours)
    cleanup_old_data(node_id)
    
    return jsonify({
        'status': 'ok',
        'config': node.config or {}
    })


def cleanup_old_data(node_id):
    """Remove data older than 24 hours."""
    cutoff = datetime.utcnow() - timedelta(hours=24)
    
    Metric.query.filter(Metric.node_id == node_id, Metric.timestamp < cutoff).delete()
    ProcessStat.query.filter(ProcessStat.node_id == node_id, ProcessStat.timestamp < cutoff).delete()
    
    db.session.commit()


@app.route('/api/alerts')
@login_required
def get_alerts():
    node_id = request.args.get('node_id')
    resolved = request.args.get('resolved', 'false').lower() == 'true'
    
    query = Alert.query.filter_by(is_resolved=resolved)
    if node_id:
        query = query.filter_by(node_id=node_id)
    
    alerts = query.order_by(Alert.created_at.desc()).limit(100).all()
    return jsonify([a.to_dict() for a in alerts])


@app.route('/api/alerts/<int:alert_id>/resolve', methods=['POST'])
@login_required
def resolve_alert(alert_id):
    alert = Alert.query.get(alert_id)
    if not alert:
        return jsonify({'error': 'Alert not found'}), 404
    
    alert.is_resolved = True
    alert.resolved_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'status': 'ok'})


@app.route('/api/users', methods=['GET', 'POST'])
@admin_required
def manage_users():
    if request.method == 'GET':
        users = User.query.all()
        return jsonify([u.to_dict() for u in users])
    
    data = request.json
    if User.query.filter_by(username=data.get('username')).first():
        return jsonify({'error': 'Username exists'}), 400
    
    user = User(
        username=data['username'],
        email=data['email'],
        password_hash=User.hash_password(data['password']),
        is_admin=data.get('is_admin', False),
        is_active=data.get('is_active', True)
    )
    db.session.add(user)
    db.session.commit()
    
    return jsonify(user.to_dict()), 201


@app.route('/api/users/<int:user_id>', methods=['PUT', 'DELETE'])
@admin_required
def update_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if request.method == 'DELETE':
        if user.id == session.get('user_id'):
            return jsonify({'error': 'Cannot delete yourself'}), 400
        db.session.delete(user)
        db.session.commit()
        return jsonify({'status': 'ok'})
    
    data = request.json
    if 'is_admin' in data:
        user.is_admin = data['is_admin']
    if 'is_active' in data:
        user.is_active = data['is_active']
    if 'password' in data and data['password']:
        user.password_hash = User.hash_password(data['password'])
    
    db.session.commit()
    return jsonify(user.to_dict())


@app.route('/api/export/metrics/<node_id>')
@login_required
def export_metrics(node_id):
    """Export node metrics as CSV or JSON."""
    fmt = request.args.get('format', 'json')
    hours = int(request.args.get('hours', 24))
    
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    metrics = Metric.query.filter(
        Metric.node_id == node_id,
        Metric.timestamp >= cutoff
    ).order_by(Metric.timestamp).all()
    
    if fmt == 'csv':
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'timestamp', 'cpu_percent', 'memory_percent', 'memory_used_mb',
            'disk_percent', 'bytes_sent_rate', 'bytes_recv_rate',
            'load_avg_1', 'load_avg_5', 'load_avg_15'
        ])
        
        for m in metrics:
            writer.writerow([
                m.timestamp.isoformat() if m.timestamp else '',
                m.cpu_percent,
                m.memory_percent,
                m.memory_used_mb,
                m.disk_percent,
                m.bytes_sent,
                m.bytes_recv,
                m.load_avg_1,
                m.load_avg_5,
                m.load_avg_15
            ])
        
        output.seek(0)
        return output.getvalue(), 200, {
            'Content-Type': 'text/csv',
            'Content-Disposition': f'attachment; filename={node_id}_metrics.csv'
        }
    
    return jsonify([m.to_dict() for m in metrics])


@app.route('/api/stats')
@login_required
def get_system_stats():
    """Get overall system statistics."""
    total_nodes = Node.query.filter_by(is_active=True).count()
    online_nodes = sum(1 for n in Node.query.filter_by(is_active=True).all() if n.is_online())
    
    active_alerts = Alert.query.filter_by(is_resolved=False).count()
    total_users = User.query.count()
    
    # Calculate average CPU and memory across all nodes
    recent_metrics = Metric.query.filter(
        Metric.timestamp >= datetime.utcnow() - timedelta(minutes=5)
    ).all()
    
    avg_cpu = sum(m.cpu_percent or 0 for m in recent_metrics) / len(recent_metrics) if recent_metrics else 0
    avg_mem = sum(m.memory_percent or 0 for m in recent_metrics) / len(recent_metrics) if recent_metrics else 0
    
    # Get database size
    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    db_size = 0
    if os.path.exists(db_path):
        db_size = os.path.getsize(db_path)
    
    return jsonify({
        'nodes': {
            'total': total_nodes,
            'online': online_nodes,
            'offline': total_nodes - online_nodes
        },
        'alerts': {
            'active': active_alerts
        },
        'users': {
            'total': total_users,
            'admins': User.query.filter_by(is_admin=True).count()
        },
        'performance': {
            'avg_cpu': round(avg_cpu, 2),
            'avg_memory': round(avg_mem, 2)
        },
        'database': {
            'size_bytes': db_size,
            'size_mb': round(db_size / (1024 * 1024), 2)
        },
        'timestamp': datetime.utcnow().isoformat()
    })


@app.route('/api/health')
def health_check():
    """Public health check endpoint."""
    try:
        # Test database connection
        Node.query.limit(1).all()
        db_status = 'ok'
    except Exception as e:
        db_status = f'error: {str(e)}'
    
    return jsonify({
        'status': 'healthy' if db_status == 'ok' else 'unhealthy',
        'database': db_status,
        'timestamp': datetime.utcnow().isoformat()
    })


@app.route('/admin')
@admin_required
def admin_panel():
    """Admin panel page."""
    return render_template('admin.html')


@sock.route('/ws')
def websocket(ws):
    while True:
        try:
            nodes = Node.query.filter_by(is_active=True).all()
            data = {
                'nodes': {n.id: n.to_dict() for n in nodes},
                'timestamp': time.time()
            }
            ws.send(json.dumps(data))
            time.sleep(2)
        except:
            break


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_default_admin()
    
    logger.info(f"Starting Server Monitor")
    logger.info(f"JWT_SECRET (first 8 chars): {JWT_SECRET[:8]}...")
    logger.info(f"Data directory: {DATA_DIR}")
    app.run(host='0.0.0.0', port=5000, debug=False)
