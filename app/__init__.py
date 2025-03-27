from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_migrate import Migrate
import os

# Инициализация Flask приложения
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация базы данных и Socket.IO
db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app)

from app import routes, models

# Создание базы данных
with app.app_context():
    db.create_all() 