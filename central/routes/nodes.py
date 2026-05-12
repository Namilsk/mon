from flask import jsonify, session, request
from datetime import datetime

from . import nodes_bp
from auth import login_required
from extensions import db
from models import Node, Metric, ProcessStat, Alert, AlertConfig
from utils import check_alerts, cleanup_old_data
from config import DEFAULT_USER_ID


@nodes_bp.route('/nodes')
@login_required
def get_nodes():
    if session.get('is_admin'):
        nodes = Node.query.filter_by(is_active=True).all()
    else:
        nodes = Node.query.filter_by(is_active=True, user_id=session.get('user_id')).all()
    return jsonify({n.id: n.to_dict() for n in nodes})


@nodes_bp.route('/nodes/<node_id>')
@login_required
def get_node(node_id):
    node = Node.query.get(node_id)
    if not node:
        return jsonify({'error': 'Node not found'}), 404
    
    if not session.get('is_admin') and node.user_id != session.get('user_id'):
        return jsonify({'error': 'Access denied'}), 403
    
    metrics = Metric.query.filter_by(node_id=node_id).order_by(Metric.timestamp.desc()).limit(100).all()
    metrics.reverse()
    
    latest_processes = ProcessStat.query.filter_by(node_id=node_id).order_by(
        ProcessStat.timestamp.desc(), ProcessStat.cpu_percent.desc()
    ).limit(10).all()
    
    alerts = Alert.query.filter_by(node_id=node_id, is_resolved=False).order_by(Alert.created_at.desc()).all()
    
    cpu_history = [{'v': m.cpu_percent or 0} for m in metrics]
    network_history = [
        {
            'sent': (m.bytes_sent or 0) / 1024,
            'recv': (m.bytes_recv or 0) / 1024
        } for m in metrics
    ]
    
    return jsonify({
        'info': node.to_dict(),
        'current': metrics[-1].to_dict() if metrics else None,
        'history': [m.to_dict() for m in metrics],
        'cpu_history': cpu_history,
        'network_history': network_history,
        'processes': [p.to_dict() for p in latest_processes],
        'alerts': [a.to_dict() for a in alerts]
    })


@nodes_bp.route('/nodes/<node_id>/config', methods=['POST'])
@login_required
def update_config(node_id):
    node = Node.query.get(node_id)
    if not node:
        return jsonify({'error': 'Node not found'}), 404
    
    if not session.get('is_admin') and node.user_id != session.get('user_id'):
        return jsonify({'error': 'Access denied'}), 403
    
    config = request.json or {}
    node.config = {**(node.config or {}), **config}
    
    if 'poll_interval' in config:
        node.poll_interval = int(config['poll_interval'])
    
    db.session.commit()
    return jsonify({'status': 'ok', 'config': node.config})


@nodes_bp.route('/nodes/<node_id>/alerts', methods=['POST'])
@login_required
def update_alert_config(node_id):
    node = Node.query.get(node_id)
    if not node:
        return jsonify({'error': 'Node not found'}), 404
    
    if not session.get('is_admin') and node.user_id != session.get('user_id'):
        return jsonify({'error': 'Access denied'}), 403
    
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
