from flask import Flask, request, send_file
from flask_cors import CORS
from flasgger import Swagger
from database import db
from Controllers.UserController import *
from Controllers.DocCallController import doc_call_bp
from Controllers.DocPermissionController import doc_permission_bp
from Controllers.DocumentController import *
from Controllers.MessageController import *
from Controllers.AudioController import *
from Controllers.LLMMemoryController import llm_memory_bp
from Controllers.ChatController import *

app = Flask(__name__)
CORS(app)  # Enable CORS for the entire app

# Ensure JSON UTF-8 output
app.config['JSON_AS_ASCII'] = False
try:
    app.json.ensure_ascii = False  # type: ignore[attr-defined]
except Exception:
    pass

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://root:root@db:5432/dbuild'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Swagger configuration
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
        {'name': 'Users', 'description': 'Операции с пользователями'},
        {'name': 'Chats', 'description': 'Операции с чатами'},
        {'name': 'Auth', 'description': 'Аутентификация и авторизация'},
        {'name': 'Messages', 'description': 'Операции с сообщениями'},
        {'name': 'Audio', 'description': 'Конвертация текста в аудио'},
        {'name': 'DocCall', 'description': 'Вызовы документов'},
        {'name': 'DocPermissions', 'description': 'Разрешения на документы'},
        {'name': 'LLM Memory', 'description': 'Память LLM для пользователей'}
    ]
}

Swagger(app)
db.init_app(app)

with app.app_context():
    db.create_all()

# -------------------------
# Register Blueprints with Swagger support
# -------------------------
app.register_blueprint(doc_call_bp)
app.register_blueprint(doc_permission_bp)
app.register_blueprint(llm_memory_bp)

# -------------------------
# Document routes
# -------------------------
app.route('/api/documents/', methods=['GET'])(get_documents)
app.route('/api/documents/<int:item_id>', methods=['GET'])(get_document)
app.route('/api/documents/', methods=['POST'])(add_document)
app.route('/api/documents/<int:item_id>', methods=['PUT'])(update_document)
app.route('/api/documents/<int:item_id>', methods=['DELETE'])(delete_document)

# -------------------------
# User routes
# -------------------------
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

# -------------------------
# Chat routes
# -------------------------
app.route('/api/chats/', methods=['GET'])(get_chats)
app.route('/api/chats/<int:chat_id>', methods=['GET'])(get_chat)
app.route('/api/chats/', methods=['POST'])(add_chat)
app.route('/api/chats/<int:chat_id>', methods=['PUT'])(update_chat)
app.route('/api/chats/<int:chat_id>', methods=['DELETE'])(delete_chat)

# -------------------------
# Auth routes
# -------------------------
app.route('/api/auth/login', methods=['POST'])(login)
app.route('/api/auth/refresh', methods=['POST'])(refresh_token)
app.route('/api/auth/register', methods=['POST'])(register)

# -------------------------
# Messages routes
# -------------------------
app.route('/api/messages/', methods=['GET'])(get_messages)
app.route('/api/messages/<int:item_id>', methods=['GET'])(get_message)
app.route('/api/messages/', methods=['POST'])(add_message)

# -------------------------
# Audio conversion route
# -------------------------
app.route('/api/converttexttoaudio/', methods=['POST'])(convert_text_to_audio)

# -------------------------
# Run the app
# -------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)