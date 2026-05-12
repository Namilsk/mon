from flask import jsonify, request, session
from datetime import datetime

from . import tokens_bp
from auth import login_required
from extensions import db
from models import ApiToken


@tokens_bp.route('/tokens', methods=['GET', 'POST'])
@login_required
def manage_tokens():
    if request.method == 'GET':
        tokens = ApiToken.query.filter_by(user_id=session['user_id']).all()
        return jsonify([t.to_dict() for t in tokens])
    
    data = request.json or {}
    name = data.get('name', 'API Token')
    
    token = ApiToken(
        user_id=session['user_id'],
        token=ApiToken.generate_token(),
        name=name
    )
    db.session.add(token)
    db.session.commit()
    
    return jsonify({
        'id': token.id,
        'name': token.name,
        'token': token.token,
        'created_at': token.created_at.isoformat() if token.created_at else None
    }), 201


@tokens_bp.route('/tokens/<int:token_id>', methods=['DELETE', 'PUT'])
@login_required
def update_token(token_id):
    token = ApiToken.query.get(token_id)
    if not token:
        return jsonify({'error': 'Token not found'}), 404
    
    if token.user_id != session['user_id'] and not session.get('is_admin'):
        return jsonify({'error': 'Access denied'}), 403
    
    if request.method == 'DELETE':
        db.session.delete(token)
        db.session.commit()
        return jsonify({'status': 'deleted'})
    
    data = request.json or {}
    if 'is_active' in data:
        token.is_active = bool(data['is_active'])
        db.session.commit()
    
    return jsonify(token.to_dict())
