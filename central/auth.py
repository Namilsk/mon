import jwt
from functools import wraps
from datetime import datetime
from flask import jsonify, request, session, redirect, url_for

from config import JWT_SECRET
from extensions import db
from models import ApiToken

import logging
logger = logging.getLogger(__name__)


def token_required(f):
    """Require valid JWT token (for node agents)."""
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
    """Require session authentication (for web users)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Require admin session authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        if not session.get('is_admin'):
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


def api_auth_required(f):
    """Check either session auth or API token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('authenticated'):
            return f(*args, **kwargs)
        
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Token ') or auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
            api_token = ApiToken.query.filter_by(token=token, is_active=True).first()
            if api_token:
                api_token.last_used_at = datetime.utcnow()
                db.session.commit()
                session['user_id'] = api_token.user_id
                session['is_admin'] = api_token.user.is_admin
                return f(*args, **kwargs)
        
        return jsonify({'error': 'Authentication required'}), 401
    return decorated
