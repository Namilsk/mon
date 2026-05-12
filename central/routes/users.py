from flask import jsonify, request, session
from datetime import datetime

from . import users_bp
from auth import admin_required
from extensions import db
from models import User


@users_bp.route('/users', methods=['GET', 'POST'])
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


@users_bp.route('/users/<int:user_id>', methods=['PUT', 'DELETE'])
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
