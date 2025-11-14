from flask import Flask, request, send_file
from flask_cors import CORS
from flasgger import Swagger
from database import db
from Controllers.UserController import *
from Controllers.MessageController import *
from Controllers.AudioController import *
from Controllers.ChatController import *
from Controllers.DepartmentController import *

app = Flask(__name__)
CORS(app) # Включаем поддержку CORS для всего приложения

# Возвращать JSON в UTF-8 без escape-последовательностей для не-ASCII
app.config['JSON_AS_ASCII'] = False
# Для Flask >= 2.2 используем JSON provider
try:
    app.json.ensure_ascii = False  # type: ignore[attr-defined]
except Exception:
    pass

# Настройка подключения к базе данных MySQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://root:root@db:5432/dbuild'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Конфигурация Swagger
app.config['SWAGGER'] = {
    'title': 'D-building API',
    'uiversion': 3,
    'version': '1.0.0',
    'description': 'API для системы управления зданиями',
    'contact': {
        'developer': 'D-building Team',
        'email': 'info@dbuilding.com'
    },
    'license': {
        'name': 'MIT',
        'url': 'https://opensource.org/licenses/MIT'
    },
    'tags': [
        {
            'name': 'Users',
            'description': 'Операции с пользователями'
        },
        {
            'name': 'Chats',
            'description': 'Операции с чатами'
        },
        {
            'name': 'Departments',
            'description': 'Операции с отделами'
        },
        {
            'name': 'Auth',
            'description': 'Аутентификация и авторизация'
        },
        {
            'name': 'Messages',
            'description': 'Операции с сообщениями'
        },
        {
            'name': 'Audio',
            'description': 'Конвертация текста в аудио'
        }
    ]
}

Swagger(app)

db.init_app(app)

with app.app_context():
    db.create_all()

# Роуты пользователя
app.route('/api/users/', methods=['GET'])(get_users)
app.route('/api/users/<int:item_id>', methods=['GET'])(get_user)
app.route('/api/users/', methods=['POST'])(add_user)
app.route('/api/users/<int:item_id>', methods=['PUT'])(update_user)

# ----------------- Manager routes -----------------
app.route('/api/managers/', methods=['GET'])(get_managers)
app.route('/api/managers/<int:item_id>', methods=['GET'])(get_manager)
app.route('/api/managers/', methods=['POST'])(add_manager)
app.route('/api/managers/<int:item_id>', methods=['PUT'])(update_manager)
app.route('/api/managers/<int:item_id>', methods=['DELETE'])(delete_manager)

# ----------------- Employee routes -----------------
app.route('/api/employees/', methods=['GET'])(get_employees)
app.route('/api/employees/<int:item_id>', methods=['GET'])(get_employee)
app.route('/api/employees/', methods=['POST'])(add_employee)
app.route('/api/employees/<int:item_id>', methods=['PUT'])(update_employee)
app.route('/api/employees/<int:item_id>', methods=['DELETE'])(delete_employee)

# Роуты чатов
app.route('/api/chats/', methods=['GET'])(get_chats)
app.route('/api/chats/<int:chat_id>', methods=['GET'])(get_chat)
app.route('/api/chats/', methods=['POST'])(add_chat)
app.route('/api/chats/<int:chat_id>', methods=['PUT'])(update_chat)
app.route('/api/chats/<int:chat_id>', methods=['DELETE'])(delete_chat)

# Роуты отделов
app.route('/api/departments/', methods=['GET'])(get_departments)
app.route('/api/departments/<int:department_id>', methods=['GET'])(get_department)
app.route('/api/departments/', methods=['POST'])(add_department)
app.route('/api/departments/<int:department_id>', methods=['PUT'])(update_department)
app.route('/api/departments/<int:department_id>', methods=['DELETE'])(delete_department)

# Роуты аутентификации
app.route('/api/auth/login', methods=['POST'])(login)
app.route('/api/auth/refresh', methods=['POST'])(refresh_token)
app.route('/api/auth/register', methods=['POST'])(register)

# Роуты сообщений
app.route('/api/messages/', methods=['GET'])(get_messages)
app.route('/api/messages/<int:item_id>', methods=['GET'])(get_message)
app.route('/api/messages/', methods=['POST'])(add_message)

app.route('/api/converttexttoaudio/', methods=['POST'])(convert_text_to_audio)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)