from datetime import datetime, timedelta
from extensions import db
from models import Metric, ProcessStat, Alert, AlertConfig

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
            existing = Alert.query.filter_by(
                node_id=node.id, alert_type=alert_type, is_resolved=False
            ).first()
            if existing:
                existing.is_resolved = True
                existing.resolved_at = datetime.utcnow()
    
    db.session.commit()


def cleanup_old_data(node_id):
    """Remove data older than 24 hours."""
    cutoff = datetime.utcnow() - timedelta(hours=24)
    
    Metric.query.filter(Metric.node_id == node_id, Metric.timestamp < cutoff).delete()
    ProcessStat.query.filter(ProcessStat.node_id == node_id, ProcessStat.timestamp < cutoff).delete()
    
    db.session.commit()
