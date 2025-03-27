from flask import Flask
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
import os

# Инициализация Flask приложения
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///game.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация SocketIO с простым веб-сокетом
socketio = SocketIO(app, 
                   async_mode='threading',
                   cors_allowed_origins="*",
                   engineio_logger=True)

db = SQLAlchemy(app)

from app import routes, models

# Создание базы данных
with app.app_context():
    db.create_all() 