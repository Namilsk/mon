import os
import time
import json
import socket
import threading
import psutil
import requests
import jwt

CENTRAL_URL = os.environ.get('CENTRAL_URL', 'http://localhost:5000')
NODE_ID = os.environ.get('NODE_ID', socket.gethostname())
JWT_SECRET = os.environ.get('JWT_SECRET', 'dev-secret-change-me')
POLL_INTERVAL = int(os.environ.get('POLL_INTERVAL', '5'))

config = {'poll_interval': POLL_INTERVAL}

def generate_token():
    return jwt.encode({'node': NODE_ID, 'exp': time.time() + 60}, JWT_SECRET, algorithm='HS256')

def get_top_processes(n=10):
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            info = proc.info
            if info['cpu_percent'] and info['cpu_percent'] > 0:
                processes.append({
                    'pid': info['pid'],
                    'name': info['name'][:20],
                    'cpu_percent': info['cpu_percent'],
                    'memory_percent': info['memory_percent'] or 0
                })
        except:
            pass
    return sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)[:n]

def collect_metrics():
    net_before = psutil.net_io_counters()
    time.sleep(1)
    net_after = psutil.net_io_counters()
    
    return {
        'node_id': NODE_ID,
        'timestamp': time.time(),
        'hostname': socket.gethostname(),
        'platform': os.sys.platform,
        'poll_interval': config.get('poll_interval', POLL_INTERVAL),
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_percent': psutil.virtual_memory().percent,
        'network': {
            'bytes_sent': net_after.bytes_sent - net_before.bytes_sent,
            'bytes_recv': net_after.bytes_recv - net_before.bytes_recv,
            'packets_sent': net_after.packets_sent - net_before.packets_sent,
            'packets_recv': net_after.packets_recv - net_before.packets_recv
        },
        'top_processes': get_top_processes(10)
    }

def send_metrics():
    try:
        data = collect_metrics()
        headers = {'Authorization': f'Bearer {generate_token()}'}
        resp = requests.post(
            f'{CENTRAL_URL}/api/metrics',
            json=data,
            headers=headers,
            timeout=10
        )
        if resp.status_code == 200:
            new_config = resp.json().get('config', {})
            if new_config:
                config.update(new_config)
        return resp.status_code == 200
    except Exception as e:
        print(f'Failed to send metrics: {e}')
        return False

def main():
    print(f'Starting agent {NODE_ID}')
    print(f'Central server: {CENTRAL_URL}')
    
    while True:
        send_metrics()
        time.sleep(config.get('poll_interval', POLL_INTERVAL))

if __name__ == '__main__':
    main()
