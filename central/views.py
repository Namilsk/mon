from flask import render_template, request, session, redirect, url_for
from datetime import datetime

from auth import login_required, admin_required
from extensions import db
from models import User, Node
from config import ADMIN_PASSWORD

import logging
logger = logging.getLogger(__name__)


def create_default_admin():
    """Create default admin user if no users exist."""
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


def register_routes(app):
    """Register web view routes with the app."""
    
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

    @app.route('/admin')
    @admin_required
    def admin_panel():
        return render_template('admin.html')
