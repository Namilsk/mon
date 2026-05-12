import os
import logging
from flask import Flask

from extensions import db, migrate, sock
from config import DATA_DIR, JWT_SECRET
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app():
    """Application factory."""
    app = Flask(__name__)
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(32))
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{os.path.join(DATA_DIR, "monitor.db")}'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    sock.init_app(app)

    # Import models (needed for create_all)
    from models import User, Node, Metric, ProcessStat, Alert, AlertConfig, ApiToken

    # Register blueprints
    from routes import register_blueprints
    register_blueprints(app)

    # Register web views
    from views import register_routes, create_default_admin
    register_routes(app)

    # Register websocket
    import websocket

    @app.cli.command('init-db')
    def init_db():
        """Initialize the database."""
        with app.app_context():
            db.create_all()
            create_default_admin()
        logger.info('Database initialized')

    return app


if __name__ == '__main__':
    app = create_app()
    
    with app.app_context():
        db.create_all()
        from views import create_default_admin
        create_default_admin()
    
    logger.info(f"Starting Server Monitor")
    logger.info(f"JWT_SECRET (first 8 chars): {JWT_SECRET[:8]}...")
    logger.info(f"Data directory: {DATA_DIR}")
    app.run(host='0.0.0.0', port=5000, debug=False)
