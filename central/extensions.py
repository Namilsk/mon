from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_sock import Sock

db = SQLAlchemy()
migrate = Migrate()
sock = Sock()
