from flask import jsonify, request
from datetime import datetime

from . import metrics_bp
from auth import token_required
from extensions import db
from models import Node, Metric, ProcessStat
from utils import check_alerts, cleanup_old_data
from config import DEFAULT_USER_ID


@metrics_bp.route('/metrics', methods=['POST'])
@token_required
def receive_metrics():
    data = request.json
    node_id = data.get('node_id')
    if not node_id:
        return jsonify({'error': 'node_id required'}), 400
    
    node = Node.query.get(node_id)
    if not node:
        user_id = None
        if DEFAULT_USER_ID:
            try:
                user_id = int(DEFAULT_USER_ID)
            except ValueError:
                pass
        node = Node(id=node_id, user_id=user_id)
        db.session.add(node)
    
    node.last_seen = datetime.utcnow()
    node.hostname = data.get('hostname', node.hostname)
    node.platform = data.get('platform', node.platform)
    node.ip_address = request.remote_addr
    node.poll_interval = data.get('poll_interval', node.poll_interval or 5)
    
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
    
    check_alerts(node, metric)
    cleanup_old_data(node_id)
    
    return jsonify({
        'status': 'ok',
        'config': node.config or {}
    })
