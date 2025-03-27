from app import db
import random

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False)
    room_code = db.Column(db.String(6), db.ForeignKey('room.code'), nullable=True)
    role = db.Column(db.String(20), nullable=True)
    is_alive = db.Column(db.Boolean, default=True)
    
    __table_args__ = (
        db.UniqueConstraint('username', 'room_code', name='unique_username_per_room'),
    )

class Room(db.Model):
    code = db.Column(db.String(6), primary_key=True)
    status = db.Column(db.String(20), default='waiting')  # waiting, playing, finished
    players = db.relationship('User', backref='room', lazy=True)
    
    def get_players_count(self):
        return len(self.players)
        
    def assign_roles(self):
        """Распределяет роли между игроками в соответствии с балансом игры"""
        players = self.players
        player_count = len(players)
        
        # Определяем количество каждой роли в зависимости от количества игроков
        if player_count <= 6:  # 4-6 игроков
            mafia_count = 1
            has_sheriff = True
            has_doctor = True
            civilian_count = player_count - mafia_count - (1 if has_sheriff else 0) - (1 if has_doctor else 0)
        elif player_count <= 9:  # 7-9 игроков
            mafia_count = 2
            has_sheriff = True
            has_doctor = True
            civilian_count = player_count - mafia_count - (1 if has_sheriff else 0) - (1 if has_doctor else 0)
        else:  # 10+ игроков
            mafia_count = 3
            has_sheriff = True
            has_doctor = True
            civilian_count = player_count - mafia_count - (1 if has_sheriff else 0) - (1 if has_doctor else 0)
        
        # Формируем список ролей
        roles = ['mafia'] * mafia_count
        if has_sheriff:
            roles.append('sheriff')
        if has_doctor:
            roles.append('doctor')
        roles.extend(['civilian'] * civilian_count)
        
        # Перемешиваем роли
        random.shuffle(roles)
        
        # Назначаем роли игрокам
        for player, role in zip(players, roles):
            player.role = role
            player.is_alive = True
        
        db.session.commit() 