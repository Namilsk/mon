import os

JWT_SECRET = os.environ.get('JWT_SECRET', 'dev-secret-change-me')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin')
DATA_DIR = os.environ.get('DATA_DIR', os.path.join(os.path.dirname(__file__), 'data'))
DEFAULT_USER_ID = os.environ.get('DEFAULT_USER_ID')

os.makedirs(DATA_DIR, exist_ok=True)
