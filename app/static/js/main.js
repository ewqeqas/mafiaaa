let socket;
let currentState = 'waiting';
let myRole = null;
let isNightActionDone = false;
let myUsername = null;

// Информация о ролях
const ROLE_INFO = {
    'civilian': {
        name: 'Мирный житель',
        description: 'Ваша задача - найти и устранить мафию путем голосования днем. У вас нет специальных способностей.',
        canActAtNight: false,
        actionDescription: '',
        cardImage: '/static/images/mirniy.jpg',
        goal: 'Найти и устранить всю мафию путем голосования'
    },
    'mafia': {
        name: 'Мафия',
        description: 'Ваша задача - устранить всех мирных жителей. Каждую ночь вы можете выбрать одного игрока для убийства.',
        canActAtNight: true,
        actionDescription: 'Выберите игрока для убийства',
        cardImage: '/static/images/mafia.jpg',
        goal: 'Устранить всех мирных жителей'
    },
    'doctor': {
        name: 'Доктор',
        description: 'Вы можете спасать игроков от смерти. Каждую ночь выбирайте одного игрока для защиты.',
        canActAtNight: true,
        actionDescription: 'Выберите игрока для лечения',
        cardImage: '/static/images/doctor.jpg',
        goal: 'Помогать мирным жителям, спасая их от мафии'
    },
    'sheriff': {
        name: 'Шериф',
        description: 'Вы можете проверять игроков на принадлежность к мафии. Каждую ночь вы можете проверить одного игрока.',
        canActAtNight: true,
        actionDescription: 'Выберите игрока для проверки',
        cardImage: '/static/images/sheriff.jpg',
        goal: 'Выявить мафию и помочь мирным жителям'
    }
};

// Фазы игры
const GAME_PHASES = {
    WAITING: 'waiting',
    NIGHT: 'night',
    DAY: 'day',
    VOTING: 'voting'
};

// Функция добавления сообщения в чат
function addChatMessage(message) {
    const chat = document.getElementById('chat-messages');
    if (!chat) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${message.type}-message`;
    
    let content = '';
    if (message.type === 'system') {
        content = `<span class="timestamp">[${message.timestamp}]</span> ${message.text}`;
    } else {
        content = `<span class="timestamp">[${message.timestamp}]</span> <strong>${message.username}:</strong> ${message.text}`;
    }
    
    messageDiv.innerHTML = content;
    chat.appendChild(messageDiv);
    chat.scrollTop = chat.scrollHeight;
}

// Функция показа модального окна с ролью
function showRoleModal(role) {
    const roleInfo = ROLE_INFO[role];
    const modal = document.getElementById('role-modal');
    if (!modal) return;
    
    const roleText = document.getElementById('role-text');
    if (!roleText) return;
    
    roleText.innerHTML = `
        <h3>Ваша роль - ${roleInfo.name}</h3>
        <p>${roleInfo.description}</p>
    `;
    
    const modalInstance = M.Modal.getInstance(modal);
    if (!modalInstance) {
        M.Modal.init(modal).open();
    } else {
        modalInstance.open();
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Получаем имя пользователя из глобальной переменной, установленной в шаблоне
    myUsername = document.querySelector('#my-username').textContent;
    
    // Инициализация Socket.IO
    socket = io();
    
    // Инициализация модальных окон
    const modals = document.querySelectorAll('.modal');
    M.Modal.init(modals);
    
    // Инициализация кнопки начала игры
    const startButton = document.getElementById('start-game');
    if (startButton) {
        startButton.addEventListener('click', function() {
            socket.emit('start_game');
            startButton.disabled = true;
        });
    }
    
    // Обработка подключения
    socket.on('connect', () => {
        console.log('Connected to server');
        addChatMessage({
            type: 'system',
            text: 'Подключение установлено',
            timestamp: new Date().toLocaleTimeString()
        });
    });

    // Обработка обновления состояния комнаты
    socket.on('room_status_update', (data) => {
        console.log('Room status update:', data);
        // Обновляем статус игры
        const gameStatus = document.getElementById('game-status');
        if (gameStatus) {
            switch (data.status) {
                case 'waiting':
                    gameStatus.textContent = '🕒 Ожидание игроков';
                    break;
                case 'playing':
                    gameStatus.textContent = '🎮 Игра идет';
                    // Скрываем кнопку начала игры
                    const startButton = document.getElementById('start-game');
                    if (startButton) {
                        startButton.style.display = 'none';
                    }
                    break;
                case 'finished':
                    gameStatus.textContent = '🏁 Игра окончена';
                    break;
            }
        }
        
        // Обновляем список игроков
        if (data.players) {
            updatePlayersList(data.players);
        }
    });

    // Обработка начала игры
    socket.on('game_started', (data) => {
        console.log('Game started:', data);
        myRole = data.role;
        currentState = GAME_PHASES.NIGHT;
        
        // Показываем роль игрока
        showRoleModal(data.role);
        
        // Показываем карту роли
        showRoleCard(data.role);
        
        // Обновляем список игроков
        if (data.players) {
            updatePlayersList(data.players);
        }
        
        // Обновляем интерфейс
        updateGameState();
    });

    // Обработка смены фазы игры
    socket.on('phase_change', (data) => {
        console.log('Phase change:', data);
        currentState = data.phase;
        isNightActionDone = false;
        updateGameState();
    });

    // Обработка сообщений чата
    socket.on('chat_message', (message) => {
        console.log('Chat message:', message);
        addChatMessage(message);
    });

    // Обработка результатов ночи
    socket.on('night_results', (data) => {
        if (data.killed) {
            addSystemMessage(`Этой ночью был убит игрок ${data.killed}`);
        } else {
            addSystemMessage('Этой ночью никто не погиб');
        }
        
        if (data.checked && myRole === 'sheriff') {
            const isMafiaText = data.isMafia ? 'является' : 'не является';
            addSystemMessage(`Игрок ${data.checked} ${isMafiaText} мафией`);
        }
    });

    // Обработка результатов голосования
    socket.on('vote_results', (data) => {
        if (data.eliminated) {
            addSystemMessage(`Город решил казнить игрока ${data.eliminated}`);
        } else {
            addSystemMessage('Город не смог принять решение');
        }
    });

    // Обработка окончания игры
    socket.on('game_over', (data) => {
        showGameOverModal(data.winner, data.roles);
    });

    // Обработка чата
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                const message = this.value.trim();
                if (message) {
                    socket.emit('chat_message', { message: message });
                    this.value = '';
                }
            }
        });
    }
});

// Функция обновления состояния игры
function updateGameState() {
    const gameStatus = document.getElementById('game-status');
    const actionArea = document.getElementById('action-area');
    
    if (!gameStatus || !actionArea) return;
    
    switch (currentState) {
        case GAME_PHASES.NIGHT:
            gameStatus.textContent = '🌙 Ночь';
            if (myRole && ROLE_INFO[myRole].canActAtNight && !isNightActionDone) {
                showNightActionControls();
            } else {
                actionArea.innerHTML = '<p>Дождитесь окончания ночи...</p>';
            }
            break;
            
        case GAME_PHASES.DAY:
            gameStatus.textContent = '☀️ День - Обсуждение';
            actionArea.innerHTML = `
                <div class="day-discussion">
                    <h5>Время обсудить события прошедшей ночи</h5>
                    <p>Используйте чат для обсуждения</p>
                    <button class="btn waves-effect waves-light" onclick="startVoting()">
                        Начать голосование
                        <i class="material-icons right">how_to_vote</i>
                    </button>
                </div>
            `;
            break;
            
        case GAME_PHASES.VOTING:
            gameStatus.textContent = '☀️ День - Голосование';
            if (!isNightActionDone) {  // Используем тот же флаг для голосования
                showVotingControls();
            } else {
                actionArea.innerHTML = '<p>Вы уже проголосовали. Ожидайте результатов...</p>';
            }
            break;
            
        default:
            gameStatus.textContent = '🕒 Ожидание игроков';
            actionArea.innerHTML = '<p>Ожидаем подключения игроков...</p>';
    }
}

// Добавляем функцию handleNightAction
function handleNightAction(target) {
    if (!myRole || !ROLE_INFO[myRole].canActAtNight || isNightActionDone) {
        return;
    }

    socket.emit('night_action', { target: target });
    isNightActionDone = true;

    // Обновляем интерфейс после выполнения действия
    const actionArea = document.getElementById('action-area');
    if (actionArea) {
        actionArea.innerHTML = `
            <div class="action-confirmation">
                <h5>Действие выполнено</h5>
                <p>${getActionConfirmationMessage(myRole, target)}</p>
                <p>Ожидайте окончания ночи...</p>
                <div class="progress">
                    <div class="indeterminate"></div>
                </div>
            </div>
        `;
    }
}

// Добавляем вспомогательную функцию для получения сообщения подтверждения
function getActionConfirmationMessage(role, target) {
    switch (role) {
        case 'mafia':
            return `Вы выбрали целью игрока ${target}`;
        case 'doctor':
            return `Вы решили вылечить игрока ${target}`;
        case 'sheriff':
            return `Вы проверяете игрока ${target}`;
        default:
            return `Действие выполнено на игрока ${target}`;
    }
}

// Функция показа элементов управления для ночных действий
function showNightActionControls() {
    const actionArea = document.getElementById('action-area');
    if (!actionArea) return;
    
    // Проверяем, жив ли игрок
    const playersList = document.getElementById('players-list');
    const currentPlayerElement = Array.from(playersList.getElementsByClassName('collection-item'))
        .find(item => item.dataset.username === myUsername);
    
    if (currentPlayerElement && currentPlayerElement.classList.contains('dead')) {
        actionArea.innerHTML = '<p class="dead-message">Вы мертвы и не можете выполнять действия</p>';
        return;
    }

    // Если действие уже выполнено
    if (isNightActionDone) {
        actionArea.innerHTML = '<p>Вы уже выполнили своё действие. Ожидайте окончания ночи...</p>';
        return;
    }
    
    const roleInfo = ROLE_INFO[myRole];
    if (!roleInfo.canActAtNight) {
        actionArea.innerHTML = '<p>Дождитесь окончания ночи...</p>';
        return;
    }

    // Получаем только живых игроков для выбора действия
    const alivePlayers = Array.from(playersList.getElementsByClassName('collection-item'))
        .filter(item => !item.classList.contains('dead'))
        .map(item => item.dataset.username)
        .filter(username => username !== myUsername);

    actionArea.innerHTML = `
        <div class="night-action">
            <h5>${roleInfo.actionDescription}</h5>
            <div class="collection">
                ${alivePlayers.map(player => `
                    <a href="#!" class="collection-item target-button waves-effect" onclick="handleNightAction('${player}')">
                        ${player}
                    </a>
                `).join('')}
            </div>
        </div>
    `;
}

// Функция показа элементов управления для голосования
function showVotingControls() {
    const actionArea = document.getElementById('action-area');
    if (!actionArea) return;
    
    // Проверяем, жив ли игрок
    const playersList = document.getElementById('players-list');
    const currentPlayerElement = Array.from(playersList.getElementsByClassName('collection-item'))
        .find(item => item.dataset.username === myUsername);
    
    if (currentPlayerElement && currentPlayerElement.classList.contains('dead')) {
        actionArea.innerHTML = '<p>Вы мертвы и не можете голосовать</p>';
        return;
    }

    // Получаем только живых игроков для голосования
    const alivePlayers = Array.from(playersList.getElementsByClassName('collection-item'))
        .filter(item => !item.classList.contains('dead'))
        .map(item => item.dataset.username)
        .filter(username => username !== myUsername);

    actionArea.innerHTML = `
        <div class="voting-section">
            <h5>Голосование</h5>
            <p>Выберите игрока для исключения или пропустите голосование:</p>
            <div class="collection">
                ${alivePlayers.map(player => `
                    <a href="#!" class="collection-item vote-button waves-effect" data-username="${player}">
                        <span>${player}</span>
                        <span class="badge new" id="vote-count-${player}">0</span>
                    </a>
                `).join('')}
            </div>
            <div class="voting-controls">
                <button class="btn waves-effect waves-light skip-vote-btn" onclick="vote(null)">
                    Пропустить голосование
                    <i class="material-icons right">skip_next</i>
                </button>
            </div>
        </div>
    `;

    // Добавляем обработчики для кнопок голосования
    const voteButtons = actionArea.getElementsByClassName('vote-button');
    Array.from(voteButtons).forEach(button => {
        button.addEventListener('click', () => {
            vote(button.dataset.username);
        });
    });
}

// Добавляем функцию для начала голосования
function startVoting() {
    socket.emit('start_voting');
}

// Функция обновления прогресса голосования
function updateVotingProgress() {
    const totalPlayers = document.querySelectorAll('#players-list .collection-item:not(.dead)').length;
    const votesNeeded = Math.ceil(totalPlayers * 0.5);
    const votesCount = Object.keys(game_states[room_code].votes || {}).length;
    
    const progressBar = document.querySelector('#voting-progress');
    const votesNeededText = document.querySelector('#votes-needed');
    
    if (progressBar && votesNeededText) {
        const progress = (votesCount / totalPlayers) * 100;
        progressBar.style.width = `${progress}%`;
        votesNeededText.textContent = `Проголосовало: ${votesCount}/${totalPlayers} (необходимо: ${votesNeeded})`;
    }
}

// Функция генерации кнопок игроков
function generatePlayerButtons() {
    const players = document.querySelectorAll('#players-list .collection-item');
    let buttons = '';
    
    players.forEach(player => {
        const username = player.dataset.username;
        if (username !== myUsername) {  // Нельзя голосовать за себя
            const isAlive = !player.classList.contains('dead');
            if (isAlive) {  // Показываем только живых игроков
                buttons += `
                    <a href="#!" class="collection-item" onclick="handlePlayerClick('${username}')">
                        ${username}
                    </a>
                `;
            }
        }
    });
    
    return buttons;
}

// Функция обработки клика по игроку
function handlePlayerClick(target) {
    if (currentState === GAME_PHASES.NIGHT && !isNightActionDone) {
        performNightAction(target);
    } else if (currentState === GAME_PHASES.VOTING && !isNightActionDone) {
        vote(target);
    }
}

// Функция выполнения ночного действия
function performNightAction(target) {
    socket.emit('night_action', {
        target: target
    });
    isNightActionDone = true;
    updateGameState();
}

// Функция голосования
function vote(target) {
    socket.emit('vote', { target: target });
    isNightActionDone = true; // Помечаем, что голос отдан
    
    const actionArea = document.getElementById('action-area');
    if (actionArea) {
        actionArea.innerHTML = `
            <div class="vote-confirmation">
                <h5>Ваш голос принят</h5>
                <p>${target ? `Вы проголосовали против игрока ${target}` : 'Вы пропустили голосование'}</p>
                <p>Ожидание голосов других игроков...</p>
                <div class="progress">
                    <div class="indeterminate"></div>
                </div>
            </div>
        `;
    }
}

// Функция обновления списка игроков
function updatePlayersList(players) {
    const playersList = document.getElementById('players-list');
    if (!playersList) return;
    
    playersList.innerHTML = players.map(player => `
        <div class="collection-item${player.is_alive ? '' : ' dead'}" data-username="${player.username}">
            ${player.username}
            ${player.is_alive ? '' : '<span class="badge">☠️</span>'}
        </div>
    `).join('');
}

// Функция добавления системного сообщения
function addSystemMessage(message) {
    const chat = document.getElementById('chat-messages');
    if (!chat) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'chat-message system-message';
    messageDiv.textContent = message;
    chat.appendChild(messageDiv);
    chat.scrollTop = chat.scrollHeight;
}

// Функция показа модального окна окончания игры
function showGameOverModal(winner, roles) {
    const modal = document.getElementById('game-over-modal');
    const gameOverText = document.getElementById('game-over-text');
    
    let winnerText = winner === 'mafia' ? 
        '<h4 class="red-text">Мафия победила!</h4>' : 
        '<h4 class="green-text">Мирные жители победили!</h4>';
    
    let rolesText = '<h5>Роли игроков:</h5><ul class="collection">';
    for (const [username, role] of Object.entries(roles)) {
        const roleInfo = ROLE_INFO[role];
        rolesText += `
            <li class="collection-item">
                <span class="username">${username}</span>: 
                <span class="role ${role}">${roleInfo.name}</span>
            </li>`;
    }
    rolesText += '</ul>';
    
    gameOverText.innerHTML = `
        ${winnerText}
        ${rolesText}
        <div class="game-stats">
            <p>Игра окончена!</p>
        </div>
    `;
    
    M.Modal.getInstance(modal).open();
}

// Добавляем стили для подтверждения действия
const styles = `
.action-confirmation {
    text-align: center;
    padding: 20px;
    background-color: #e8f5e9;
    border-radius: 4px;
    margin-top: 20px;
}

.night-action .collection {
    border: none;
    margin: 20px 0;
}

.night-action .collection-item {
    cursor: pointer;
    transition: background-color 0.3s;
}

.night-action .collection-item:hover {
    background-color: #f5f5f5;
}

.target-button {
    color: #26a69a !important;
}

.target-button:hover {
    background-color: #e0f2f1 !important;
}
`;

// Добавляем стили на страницу
const styleSheet = document.createElement("style");
styleSheet.textContent = styles;
document.head.appendChild(styleSheet);

// Добавляем функцию для отображения карты роли
function showRoleCard(role) {
    const roleCardSection = document.getElementById('role-card-section');
    const roleCardImage = document.getElementById('role-card-image');
    const roleName = document.getElementById('role-name');
    const roleGoal = document.getElementById('role-goal');
    
    if (roleCardSection && roleCardImage && ROLE_INFO[role]) {
        roleCardImage.src = ROLE_INFO[role].cardImage;
        roleName.textContent = ROLE_INFO[role].name;
        roleGoal.textContent = `Цель: ${ROLE_INFO[role].goal}`;
        roleCardSection.style.display = 'block';
    }
} 