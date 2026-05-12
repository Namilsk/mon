import json
import time
from models import Node
from extensions import sock


@sock.route('/ws')
def websocket(ws):
    """WebSocket endpoint for real-time node updates."""
    while True:
        try:
            nodes = Node.query.filter_by(is_active=True).all()
            data = {
                'nodes': {n.id: n.to_dict() for n in nodes},
                'timestamp': time.time()
            }
            ws.send(json.dumps(data))
            time.sleep(2)
        except:
            break
