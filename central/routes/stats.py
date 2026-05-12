import os
from flask import jsonify, request
from datetime import datetime, timedelta

from . import stats_bp
from auth import login_required
from extensions import db
from models import Node, Metric, Alert, User
from flask import current_app


@stats_bp.route('/export/metrics/<node_id>')
@login_required
def export_metrics(node_id):
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


@stats_bp.route('/stats')
@login_required
def get_system_stats():
    total_nodes = Node.query.filter_by(is_active=True).count()
    online_nodes = sum(1 for n in Node.query.filter_by(is_active=True).all() if n.is_online())
    
    active_alerts = Alert.query.filter_by(is_resolved=False).count()
    total_users = User.query.count()
    
    recent_metrics = Metric.query.filter(
        Metric.timestamp >= datetime.utcnow() - timedelta(minutes=5)
    ).all()
    
    avg_cpu = sum(m.cpu_percent or 0 for m in recent_metrics) / len(recent_metrics) if recent_metrics else 0
    avg_mem = sum(m.memory_percent or 0 for m in recent_metrics) / len(recent_metrics) if recent_metrics else 0
    
    # Get database size
    db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
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


@stats_bp.route('/health')
def health_check():
    try:
        Node.query.limit(1).all()
        db_status = 'ok'
    except Exception as e:
        db_status = f'error: {str(e)}'
    
    return jsonify({
        'status': 'healthy' if db_status == 'ok' else 'unhealthy',
        'database': db_status,
        'timestamp': datetime.utcnow().isoformat()
    })
