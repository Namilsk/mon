from flask import Blueprint

# Create blueprints for different API sections
nodes_bp = Blueprint('nodes', __name__, url_prefix='/api')
metrics_bp = Blueprint('metrics', __name__, url_prefix='/api')
alerts_bp = Blueprint('alerts', __name__, url_prefix='/api')
users_bp = Blueprint('users', __name__, url_prefix='/api')
tokens_bp = Blueprint('tokens', __name__, url_prefix='/api')
stats_bp = Blueprint('stats', __name__, url_prefix='/api')

# Import routes to register them
from . import nodes, metrics, alerts, users, tokens, stats

def register_blueprints(app):
    """Register all blueprints with the app."""
    app.register_blueprint(nodes_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(tokens_bp)
    app.register_blueprint(stats_bp)
