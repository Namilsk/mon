from flask import jsonify, request, session
from datetime import datetime

from . import alerts_bp
from auth import login_required
from extensions import db
from models import Alert


@alerts_bp.route('/alerts')
@login_required
def get_alerts():
    node_id = request.args.get('node_id')
    resolved = request.args.get('resolved', 'false').lower() == 'true'
    
    query = Alert.query.filter_by(is_resolved=resolved)
    if node_id:
        query = query.filter_by(node_id=node_id)
    
    alerts = query.order_by(Alert.created_at.desc()).limit(100).all()
    return jsonify([a.to_dict() for a in alerts])


@alerts_bp.route('/alerts/<int:alert_id>/resolve', methods=['POST'])
@login_required
def resolve_alert(alert_id):
    alert = Alert.query.get(alert_id)
    if not alert:
        return jsonify({'error': 'Alert not found'}), 404
    
    alert.is_resolved = True
    alert.resolved_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'status': 'ok'})
