from flask import render_template, request, redirect, url_for, session, jsonify
from app import app, db, socketio
from app.models import User, Room
from flask_socketio import join_room, leave_room, emit
import random
import string
from datetime import datetime
import math

def generate_room_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/join', methods=['POST'])
def join():
    username = request.form.get('username')
    room_code = request.form.get('room_code')
    
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    
    # Если указан код комнаты, проверяем существование комнаты
    if room_code:
        room = Room.query.filter_by(code=room_code).first()
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        if room.status != 'waiting':
            return jsonify({'error': 'Game already started'}), 400
            
        # Проверяем уникальность имени только в пределах комнаты
        existing_user = User.query.filter_by(username=username, room_code=room_code).first()
        if existing_user:
            return jsonify({'error': 'Username already taken in this room'}), 400
    else:
        # Создаем новую комнату
        room_code = generate_room_code()
        room = Room(code=room_code)
        db.session.add(room)
    
    # Создаем нового пользователя
    user = User(username=username, room_code=room_code)
    db.session.add(user)
    db.session.commit()
    
    session['username'] = username
    session['room_code'] = room_code
    return jsonify({'success': True, 'room_code': room_code})

@app.route('/game')
def game():
    username = session.get('username')
    room_code = session.get('room_code')
    
    if not username or not room_code:
        return redirect(url_for('index'))
    
    user = User.query.filter_by(username=username, room_code=room_code).first()
    if not user:
        session.clear()  # Очищаем сессию, если пользователь не найден
        return redirect(url_for('index'))
    
    room = Room.query.filter_by(code=room_code).first()
    return render_template('game.html', user=user, room=room)

@app.route('/logout')
def logout():
    username = session.get('username')
    if username:
        user = User.query.filter_by(username=username).first()
        if user:
            db.session.delete(user)
            db.session.commit()
    session.clear()
    return redirect(url_for('index'))

@app.route('/roles')
def show_roles():
    return render_template('roles.html')

# Словарь для хранения состояния игры
game_states = {}

@socketio.on('connect')
def handle_connect():
    if 'username' not in session:
        return False
    
    user = User.query.filter_by(username=session['username']).first()
    if user and user.room_code:
        join_room(user.room_code)
        join_room(user.username)  # Присоединяемся к персональной комнате
        
        room = Room.query.filter_by(code=user.room_code).first()
        
        # Отправляем текущее состояние комнаты
        emit('room_status_update', {
            'status': room.status,
            'players': [{'username': p.username, 'is_alive': p.is_alive} 
                       for p in room.players]
        })
        
        # Если игра уже идет, отправляем роль игроку и историю сообщений
        if room.status == 'playing':
            emit('game_started', {
                'role': user.role,
                'players': [{'username': p.username, 'is_alive': p.is_alive} 
                          for p in room.players]
            })
            
            # Отправляем текущую фазу игры
            game_state = game_states.get(room.code)
            if game_state:
                # Отправляем историю сообщений
                if 'messages' in game_state:
                    for message in game_state['messages']:
                        emit('chat_message', message)
                
                emit('phase_change', {
                    'phase': game_state['phase'],
                    'message': get_phase_message(game_state['phase'])
                })

def get_phase_message(phase):
    messages = {
        'night': 'Наступила ночь. Город засыпает...',
        'day_discussion': 'Наступил день. Время обсудить события прошедшей ночи.',
        'day_voting': 'Время выбрать подозреваемого!'
    }
    return messages.get(phase, '')

@socketio.on('start_game')
def handle_start_game():
    user = User.query.filter_by(username=session['username']).first()
    if not user or not user.room_code:
        return
    
    room = Room.query.filter_by(code=user.room_code).first()
    if room.status == 'waiting' and room.get_players_count() >= 4:
        room.status = 'playing'
        room.assign_roles()
        
        # Инициализация состояния игры
        game_states[room.code] = {
            'phase': 'night',
            'night_actions': {},
            'votes': {},
            'turn': 1,
            'messages': [],  # Добавляем список для хранения сообщений
            'vote_timer': None  # Добавляем таймер для голосования
        }
        
        db.session.commit()
        
        # Отправляем всем в комнате обновление статуса
        emit('room_status_update', {
            'status': 'playing',
            'players': [{'username': p.username, 'is_alive': p.is_alive} 
                       for p in room.players]
        }, room=room.code)
        
        # Отправляем каждому игроку его роль через персональную комнату
        for player in room.players:
            emit('game_started', {
                'role': player.role,
                'players': [{'username': p.username, 'is_alive': p.is_alive} 
                          for p in room.players]
            }, room=player.username)  # Используем персональную комнату
        
        # Добавляем системное сообщение о начале игры
        add_system_message(room.code, 'Игра началась! Всем игрокам отправлены их роли.')
        
        # Начинаем первую ночь
        start_night(room)

def add_system_message(room_code, message):
    if room_code in game_states:
        game_states[room_code]['messages'].append({
            'type': 'system',
            'text': message,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        })
        emit('chat_message', {
            'type': 'system',
            'text': message,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }, room=room_code)

def start_night(room):
    game_states[room.code]['phase'] = 'night'
    game_states[room.code]['night_actions'] = {}
    
    message = 'Наступила ночь. Город засыпает...'
    add_system_message(room.code, message)
    
    emit('phase_change', {
        'phase': 'night',
        'message': message
    }, room=room.code)

def start_day(room):
    game_states[room.code]['phase'] = 'day'
    game_states[room.code]['votes'] = {}
    
    # Обработка ночных действий
    night_results = process_night_actions(room)
    
    # Если игра не закончилась после ночных действий
    if room.status != 'finished':
        # Отправляем результаты ночи
        if night_results['killed']:
            add_system_message(room.code, f'Этой ночью был убит игрок {night_results["killed"]}')
        else:
            add_system_message(room.code, 'Этой ночью никто не погиб')
        
        # Отправляем результаты шерифу
        if night_results['checked']:
            for player in room.players:
                if player.role == 'sheriff' and player.is_alive:
                    is_mafia = 'является' if night_results['isMafia'] else 'не является'
                    socketio.emit('chat_message', {
                        'type': 'system',
                        'text': f'Игрок {night_results["checked"]} {is_mafia} мафией',
                        'timestamp': datetime.now().strftime('%H:%M:%S')
                    }, room=player.username)
        
        # Начинаем день
        socketio.emit('phase_change', {
            'phase': 'day',
            'message': 'Наступил день. Время обсудить события прошедшей ночи.'
        }, room=room.code)
        
        # Запускаем таймер для автоматического начала голосования
        socketio.start_background_task(start_voting_after_delay, room)

def start_voting_after_delay(room):
    socketio.sleep(120)  # 2 минуты на обсуждение
    if room.code in game_states and game_states[room.code]['phase'] == 'day':
        start_voting(room)

def start_voting(room):
    if room.code not in game_states:
        return
        
    game_states[room.code]['phase'] = 'voting'
    game_states[room.code]['votes'] = {}
    
    # Получаем список живых игроков
    alive_players = [p for p in room.players if p.is_alive]
    
    # Отправляем системное сообщение о начале голосования
    socketio.emit('chat_message', {
        'type': 'system',
        'text': 'Начинается голосование! Выберите подозреваемого или воздержитесь.',
        'timestamp': datetime.now().strftime('%H:%M:%S')
    }, room=room.code)
    
    # Оповещаем всех игроков о начале голосования
    socketio.emit('phase_change', {
        'phase': 'voting',
        'message': 'Время выбрать подозреваемого!',
        'players': [{'username': p.username, 'is_alive': p.is_alive} for p in alive_players]
    }, room=room.code)

    # Устанавливаем таймер на окончание голосования
    def voting_timeout():
        socketio.sleep(60)  # 60 секунд на голосование
        if room.code in game_states and game_states[room.code]['phase'] == 'voting':
            process_votes(room)
    
    socketio.start_background_task(voting_timeout)

def process_night_actions(room):
    actions = game_states[room.code]['night_actions']
    results = {'killed': None, 'checked': None, 'isMafia': None}
    
    # Находим цель мафии
    mafia_target = None
    for username, action in actions.items():
        if action['role'] == 'mafia':
            mafia_target = action['target']
            break
    
    # Проверяем, спас ли доктор цель мафии
    saved = False
    for username, action in actions.items():
        if action['role'] == 'doctor' and action['target'] == mafia_target:
            saved = True
            break
    
    # Если цель не спасена, помечаем как мертвую
    if mafia_target and not saved:
        target_user = User.query.filter_by(username=mafia_target).first()
        if target_user:
            target_user.is_alive = False
            db.session.commit()
            results['killed'] = mafia_target
            
            # Проверяем условия победы после убийства
            if check_game_over(room):
                return results
    
    # Обрабатываем проверку шерифа
    for username, action in actions.items():
        if action['role'] == 'sheriff':
            checked_user = User.query.filter_by(username=action['target']).first()
            if checked_user:
                results['checked'] = checked_user.username
                results['isMafia'] = (checked_user.role == 'mafia')
                
                # Если шериф нашел мафию
                if results['isMafia']:
                    checked_user.is_alive = False
                    db.session.commit()
                    add_system_message(room.code, f"Шериф раскрыл мафию! Игрок {checked_user.username} был исключен из игры.")
                    
                    # Проверяем условия победы после обнаружения мафии
                    if check_game_over(room):
                        return results
            break
    
    return results

def process_votes(room):
    if room.code not in game_states:
        return
        
    votes = game_states[room.code]['votes']
    if not votes:
        add_system_message(room.code, 'Никто не проголосовал. День заканчивается.')
        start_night(room)
        return
    
    # Подсчитываем голоса (игнорируем воздержавшихся)
    vote_count = {}
    for target in votes.values():
        if target:  # Учитываем только реальные голоса
            vote_count[target] = vote_count.get(target, 0) + 1
    
    if not vote_count:
        add_system_message(room.code, 'Все воздержались от голосования. День заканчивается.')
        start_night(room)
        return
    
    # Находим игрока с максимальным количеством голосов
    max_votes = max(vote_count.values())
    eliminated = [player for player, count in vote_count.items() if count == max_votes]
    
    if len(eliminated) == 1:
        # Казним игрока
        player = User.query.filter_by(username=eliminated[0]).first()
        if player:
            player.is_alive = False
            db.session.commit()
            add_system_message(room.code, f'Город решил казнить игрока {player.username}. Его роль: {ROLE_INFO[player.role]["name"]}')
            
            # Проверяем условия победы после казни
            if check_game_over(room):
                return
    else:
        add_system_message(room.code, 'Город не смог принять решение. Никто не был казнен.')
    
    # Если игра не закончилась, начинаем следующую ночь
    start_night(room)

def check_game_over(room):
    alive_players = [p for p in room.players if p.is_alive]
    mafia_count = len([p for p in alive_players if p.role == 'mafia'])
    civilian_count = len([p for p in alive_players if p.role != 'mafia'])  # Все, кто не мафия (включая доктора и шерифа)

    # Добавим отладочное сообщение
    print(f"Alive players: {len(alive_players)}, Mafia: {mafia_count}, Civilians: {civilian_count}")
    
    # Проверяем условия победы
    if mafia_count == 0:
        # Победа мирных жителей
        add_system_message(room.code, "🎉 Мирные жители победили! Вся мафия уничтожена!")
        emit('game_over', {
            'winner': 'civilians',
            'message': 'Мирные жители выиграли! Мафия уничтожена!',
            'roles': {p.username: p.role for p in room.players}
        }, room=room.code)
        room.status = 'finished'
        db.session.commit()
        return True
    elif mafia_count >= civilian_count:
        # Победа мафии (когда мафий столько же или больше, чем мирных)
        add_system_message(room.code, "🎭 Мафия победила! Мирных жителей не осталось!")
        emit('game_over', {
            'winner': 'mafia',
            'message': 'Мафия выиграла! Силы сравнялись!',
            'roles': {p.username: p.role for p in room.players}
        }, room=room.code)
        room.status = 'finished'
        db.session.commit()
        return True
    
    return False

@socketio.on('night_action')
def handle_night_action(data):
    user = User.query.filter_by(username=session['username']).first()
    if not user or not user.room_code or not user.is_alive:  # Проверяем, жив ли игрок
        return
    
    room = Room.query.filter_by(code=user.room_code).first()
    if not room or room.status != 'playing':
        return
    
    game_state = game_states.get(room.code)
    if not game_state or game_state['phase'] != 'night':
        return
    
    # Проверяем, что цель жива
    target_user = User.query.filter_by(username=data['target'], room_code=room.code).first()
    if not target_user or not target_user.is_alive:
        return
    
    # Записываем ночное действие
    game_state['night_actions'][user.username] = {
        'role': user.role,
        'target': data['target']
    }
    
    # Проверяем, все ли живые игроки с ночными действиями выполнили их
    night_roles = [p for p in room.players if p.role in ['mafia', 'sheriff', 'doctor'] and p.is_alive]
    if len(game_state['night_actions']) >= len(night_roles):
        start_day(room)

@socketio.on('vote')
def handle_vote(data):
    user = User.query.filter_by(username=session['username']).first()
    if not user or not user.room_code or not user.is_alive:  # Проверяем, жив ли игрок
        return
    
    room = Room.query.filter_by(code=user.room_code).first()
    game_state = game_states.get(room.code)
    
    if not room or room.status != 'playing' or not game_state or game_state['phase'] != 'voting':
        return
    
    # Проверяем, что цель жива (если голосование не пропущено)
    if data.get('target'):
        target_user = User.query.filter_by(username=data['target'], room_code=room.code).first()
        if not target_user or not target_user.is_alive:
            return
    
    # Записываем голос
    target = data.get('target')
    game_state['votes'][user.username] = target
    
    if target:
        add_system_message(room.code, f'{user.username} проголосовал против {target}')
    else:
        add_system_message(room.code, f'{user.username} воздержался от голосования')
    
    # Проверяем, все ли живые игроки проголосовали
    alive_players = [p for p in room.players if p.is_alive]
    if len(game_state['votes']) >= len(alive_players):
        process_votes(room)

@socketio.on('chat_message')
def handle_chat_message(data):
    user = User.query.filter_by(username=session['username']).first()
    if not user or not user.room_code:
        return
    
    room = Room.query.filter_by(code=user.room_code).first()
    if not room:
        return
    
    message = {
        'type': 'user',
        'username': user.username,
        'text': data['message'],
        'timestamp': datetime.now().strftime('%H:%M:%S')
    }
    
    # Сохраняем сообщение
    if room.code in game_states:
        game_states[room.code]['messages'].append(message)
    
    # Отправляем сообщение всем в комнате
    emit('chat_message', message, room=room.code)

@socketio.on('start_voting')
def handle_start_voting():
    user = User.query.filter_by(username=session['username']).first()
    if not user or not user.room_code:
        return
    
    room = Room.query.filter_by(code=user.room_code).first()
    if not room or room.status != 'playing':
        return
        
    game_state = game_states.get(room.code)
    if not game_state or game_state['phase'] != 'day':
        return
    
    start_voting(room) 