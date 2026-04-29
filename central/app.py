import os
import json
import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict
from functools import wraps

from flask import Flask, jsonify, request, render_template
from flask_sock import Sock
import jwt

app = Flask(__name__)
sock = Sock(app)

JWT_SECRET = os.environ.get('JWT_SECRET', 'dev-secret-change-me')
DATA_DIR = '/app/data'
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

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/nodes')
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
def get_node(node_id):
    if node_id not in nodes_data:
        return jsonify({'error': 'Node not found'}), 404
    history = nodes_history.get(node_id, {'cpu': [], 'network': []})
    return jsonify({
        'info': nodes_data.get(node_id, {}),
        'cpu_history': history['cpu'][-100:],
        'network_history': history['network'][-100:],
        'top_processes': history['processes'][-1] if history['processes'] else []
    })

@app.route('/api/nodes/<node_id>/config', methods=['POST'])
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
