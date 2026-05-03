import os
import time
import json
import socket
import threading
import psutil
import requests
import jwt
from datetime import datetime

CENTRAL_URL = os.environ.get('CENTRAL_URL', 'http://localhost:5000')
NODE_ID = os.environ.get('NODE_ID', socket.gethostname())
JWT_SECRET = os.environ.get('JWT_SECRET', 'dev-secret-change-me')
POLL_INTERVAL = int(os.environ.get('POLL_INTERVAL', '5'))

# Docker detection - check if we're in a container
IN_DOCKER = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER', False)

config = {'poll_interval': POLL_INTERVAL}
last_net_io = None
last_net_time = None


def generate_token():
    token = jwt.encode({'node': NODE_ID, 'exp': time.time() + 60}, JWT_SECRET, algorithm='HS256')
    return token


def get_secret_preview():
    return f"{JWT_SECRET[:8]}..." if len(JWT_SECRET) > 8 else "<empty>"


def is_host_process(proc):
    """Check if process is from host (not container)"""
    try:
        # In Docker, PID 1 is usually the container's init process
        # Host processes have PIDs that might not be visible
        # Check if we can access the process's environment
        proc.environ()
        return True
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return False


def get_top_processes(n=10):
    """Get top processes by CPU usage with Docker awareness."""
    processes = []
    
    try:
        # Get all process info in one call for efficiency
        attrs = ['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info', 'username', 'cmdline']
        
        for proc in psutil.process_iter(attrs):
            try:
                info = proc.info
                if info['cpu_percent'] is None:
                    continue
                    
                # In Docker, filter out container-only processes
                # Host processes typically have more complete info
                cpu_pct = info['cpu_percent'] or 0
                mem_pct = info['memory_percent'] or 0
                
                # Only include processes with meaningful activity
                if cpu_pct > 0.1 or mem_pct > 0.1:
                    cmdline = info.get('cmdline', [])
                    command = ' '.join(cmdline)[:100] if cmdline else ''
                    
                    processes.append({
                        'pid': info['pid'],
                        'name': (info['name'] or 'unknown')[:30],
                        'cpu_percent': round(cpu_pct, 2),
                        'memory_percent': round(mem_pct, 2),
                        'memory_mb': round(info['memory_info'].rss / (1024 * 1024), 1) if info.get('memory_info') else 0,
                        'username': (info['username'] or 'unknown')[:20],
                        'command': command
                    })
            except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                continue
            except Exception:
                continue
    except Exception as e:
        print(f'[{NODE_ID}] Error getting processes: {e}')
    
    # Sort by CPU usage and return top N
    return sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)[:n]


def get_disk_info():
    """Get disk usage information."""
    try:
        disk = psutil.disk_usage('/')
        return {
            'percent': disk.percent,
            'used_gb': round(disk.used / (1024**3), 1),
            'total_gb': round(disk.total / (1024**3), 1),
            'free_gb': round(disk.free / (1024**3), 1)
        }
    except Exception as e:
        print(f'[{NODE_ID}] Error getting disk info: {e}')
        return {'percent': 0, 'used_gb': 0, 'total_gb': 0, 'free_gb': 0}


def get_load_average():
    """Get system load average (Unix only)."""
    try:
        load = os.getloadavg()
        return {
            '1min': round(load[0], 2),
            '5min': round(load[1], 2),
            '15min': round(load[2], 2)
        }
    except (AttributeError, OSError):
        # Windows doesn't have loadavg
        cpu_count = psutil.cpu_count()
        # Calculate pseudo-load from CPU percent
        cpu_pct = psutil.cpu_percent(interval=0.1)
        load = cpu_pct / 100.0 * cpu_count
        return {
            '1min': round(load, 2),
            '5min': round(load, 2),
            '15min': round(load, 2)
        }


def get_boot_time():
    """Get system boot time."""
    try:
        return datetime.fromtimestamp(psutil.boot_time()).isoformat()
    except Exception:
        return None


def get_network_rates():
    """Get network I/O rates (bytes/sec)."""
    global last_net_io, last_net_time
    
    try:
        current = psutil.net_io_counters()
        current_time = time.time()
        
        if last_net_io is None or last_net_time is None:
            last_net_io = current
            last_net_time = current_time
            return {
                'bytes_sent': 0,
                'bytes_recv': 0,
                'packets_sent': 0,
                'packets_recv': 0
            }
        
        time_delta = current_time - last_net_time
        if time_delta <= 0:
            time_delta = 1
        
        result = {
            'bytes_sent': max(0, (current.bytes_sent - last_net_io.bytes_sent) / time_delta),
            'bytes_recv': max(0, (current.bytes_recv - last_net_io.bytes_recv) / time_delta),
            'packets_sent': max(0, (current.packets_sent - last_net_io.packets_sent) / time_delta),
            'packets_recv': max(0, (current.packets_recv - last_net_io.packets_recv) / time_delta)
        }
        
        last_net_io = current
        last_net_time = current_time
        
        return result
    except Exception as e:
        print(f'[{NODE_ID}] Error getting network stats: {e}')
        return {
            'bytes_sent': 0,
            'bytes_recv': 0,
            'packets_sent': 0,
            'packets_recv': 0
        }


def collect_metrics():
    """Collect all system metrics."""
    # Get memory info
    mem = psutil.virtual_memory()
    
    # Get disk info
    disk = get_disk_info()
    
    # Get network rates
    net = get_network_rates()
    
    # Get CPU percent
    cpu_pct = psutil.cpu_percent(interval=None)  # Non-blocking
    
    # Get load average
    load_avg = get_load_average()
    
    # Get processes
    processes = get_top_processes(10)
    
    return {
        'node_id': NODE_ID,
        'timestamp': time.time(),
        'hostname': socket.gethostname(),
        'platform': os.sys.platform,
        'poll_interval': config.get('poll_interval', POLL_INTERVAL),
        'cpu_percent': cpu_pct,
        'memory_percent': mem.percent,
        'memory_used_mb': round(mem.used / (1024 * 1024), 1),
        'memory_total_mb': round(mem.total / (1024 * 1024), 1),
        'disk_percent': disk['percent'],
        'disk_used_gb': disk['used_gb'],
        'disk_total_gb': disk['total_gb'],
        'network': net,
        'load_avg': load_avg,
        'boot_time': get_boot_time(),
        'top_processes': processes,
        'in_docker': IN_DOCKER,
        'cpu_count': psutil.cpu_count()
    }


def send_metrics():
    try:
        data = collect_metrics()
        token = generate_token()
        headers = {'Authorization': f'Bearer {token}'}
        
        resp = requests.post(
            f'{CENTRAL_URL}/api/metrics',
            json=data,
            headers=headers,
            timeout=15
        )
        
        if resp.status_code == 200:
            new_config = resp.json().get('config', {})
            if new_config:
                config.update(new_config)
            print(f'[{NODE_ID}] Metrics sent OK ({len(data["top_processes"])} processes)')
            return True
        elif resp.status_code == 401:
            print(f'[{NODE_ID}] 401 Unauthorized - check JWT_SECRET (secret: {get_secret_preview()})')
        else:
            print(f'[{NODE_ID}] HTTP {resp.status_code}: {resp.text[:100]}')
        
        return False
    except requests.exceptions.ConnectionError as e:
        print(f'[{NODE_ID}] Connection failed: {e}')
        return False
    except requests.exceptions.Timeout:
        print(f'[{NODE_ID}] Request timeout')
        return False
    except Exception as e:
        print(f'[{NODE_ID}] Failed to send metrics: {e}')
        return False


def main():
    print(f'=' * 60)
    print(f'Server Monitor Agent')
    print(f'Node ID: {NODE_ID}')
    print(f'Hostname: {socket.gethostname()}')
    print(f'Central server: {CENTRAL_URL}')
    print(f'JWT_SECRET: {get_secret_preview()}')
    print(f'Poll interval: {POLL_INTERVAL}s')
    print(f'Docker mode: {IN_DOCKER}')
    print(f'CPU cores: {psutil.cpu_count()}')
    print(f'=' * 60)
    
    # Initial CPU reading to warm up
    psutil.cpu_percent(interval=1)
    
    while True:
        start = time.time()
        success = send_metrics()
        elapsed = time.time() - start
        
        interval = config.get('poll_interval', POLL_INTERVAL)
        sleep_time = max(0.1, interval - elapsed)
        
        if not success:
            # Back off on error
            sleep_time = min(sleep_time, 5)
        
        time.sleep(sleep_time)


if __name__ == '__main__':
    main()
