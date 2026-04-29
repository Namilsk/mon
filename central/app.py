import os
import json
import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict
from functools import wraps

from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_sock import Sock
import jwt

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(32))
sock = Sock(app)

JWT_SECRET = os.environ.get('JWT_SECRET', 'dev-secret-change-me')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin')
DATA_DIR = os.environ.get('DATA_DIR', os.path.join(os.path.dirname(__file__), 'data'))
os.makedirs(DATA_DIR, exist_ok=True)

nodes_data = {}
nodes_history = defaultdict(lambda: {'cpu': [], 'network': [], 'processes': []})
MAX_HISTORY = 1000

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token missing'}), 401
        try:
            token = token.replace('Bearer ', '')
            jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        except:
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    return decorated

def save_data():
    with open(f'{DATA_DIR}/nodes.json', 'w') as f:
        json.dump(nodes_data, f)

def load_data():
    global nodes_data
    try:
        with open(f'{DATA_DIR}/nodes.json', 'r') as f:
            nodes_data = json.load(f)
    except:
        nodes_data = {}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if username == 'admin' and password == ADMIN_PASSWORD:
            session['authenticated'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/nodes')
@login_required
def get_nodes():
    active_nodes = {}
    now = time.time()
    for node_id, data in nodes_data.items():
        last_seen = data.get('last_seen', 0)
        active_nodes[node_id] = {
            'online': (now - last_seen) < 30,
            'last_seen': last_seen,
            'poll_interval': data.get('poll_interval', 5)
        }
    return jsonify(active_nodes)

@app.route('/api/nodes/<node_id>')
@login_required
def get_node(node_id):
    if node_id not in nodes_data:
        return jsonify({'error': 'Node not found'}), 404
    history = nodes_history.get(node_id, {})
    return jsonify({
        'info': nodes_data.get(node_id, {}),
        'cpu_history': history.get('cpu', [])[-100:],
        'network_history': history.get('network', [])[-100:],
        'top_processes': history.get('processes', [])[-1] if history.get('processes') else []
    })

@app.route('/api/nodes/<node_id>/config', methods=['POST'])
@login_required
def update_config(node_id):
    if node_id not in nodes_data:
        return jsonify({'error': 'Node not found'}), 404
    config = request.json or {}
    nodes_data[node_id]['config'] = config
    save_data()
    return jsonify({'status': 'ok'})

@app.route('/api/metrics', methods=['POST'])
@token_required
def receive_metrics():
    data = request.json
    node_id = data.get('node_id')
    if not node_id:
        return jsonify({'error': 'node_id required'}), 400
    
    nodes_data[node_id] = {
        'last_seen': time.time(),
        'poll_interval': data.get('poll_interval', 5),
        'cpu_percent': data.get('cpu_percent', 0),
        'memory_percent': data.get('memory_percent', 0),
        'network': data.get('network', {}),
        'hostname': data.get('hostname', 'unknown'),
        'platform': data.get('platform', 'unknown'),
        'config': nodes_data.get(node_id, {}).get('config', {})
    }
    
    timestamp = time.time()
    history = nodes_history[node_id]
    
    history['cpu'].append({'t': timestamp, 'v': data.get('cpu_percent', 0)})
    
    net = data.get('network', {})
    history['network'].append({
        't': timestamp,
        'sent': net.get('bytes_sent', 0),
        'recv': net.get('bytes_recv', 0)
    })
    
    if data.get('top_processes'):
        history['processes'].append(data['top_processes'])
    
    for key in ['cpu', 'network', 'processes']:
        if len(history[key]) > MAX_HISTORY:
            history[key] = history[key][-MAX_HISTORY:]
    
    save_data()
    
    config = nodes_data[node_id].get('config', {})
    return jsonify({
        'status': 'ok',
        'config': config
    })

@sock.route('/ws')
def websocket(ws):
    while True:
        try:
            data = {'nodes': nodes_data, 'timestamp': time.time()}
            ws.send(json.dumps(data))
            time.sleep(2)
        except:
            break

if __name__ == '__main__':
    load_data()
    app.run(host='0.0.0.0', port=5000, debug=False)
