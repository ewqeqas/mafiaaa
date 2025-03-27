from flask import Flask
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
import os

# Инициализация Flask приложения
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///game.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация базы данных и Socket.IO
socketio = SocketIO(app, cors_allowed_origins="*")
db = SQLAlchemy(app)

from app import routes, models

# Создание базы данных
with app.app_context():
    db.create_all() 