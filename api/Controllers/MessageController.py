from flask import jsonify, request
from Models.Message import Message, db
from Models.User import User
from Models.Chat import Chat
from sqlalchemy import desc
from datetime import datetime
import speech_recognition as sr
import asyncio
import os
import requests
from pathlib import Path
import re
from openai import OpenAI
from flasgger import swag_from

API_URL = "https://openrouter.ai/api/v1/chat/completions"

from flask import Blueprint
message_bp = Blueprint("message_bp", __name__)


def _load_env_from_file():
    # Пытаемся загрузить ключ из ближайших .env без выхода за пределы родителей
    here = Path(__file__).resolve()
    parents = list(here.parents)

    candidates = []
    # Корень проекта в контейнере (обычно '/')
    if len(parents) >= 2:
        candidates.append(parents[1] / ".env")  # '/.env' после COPY . .
    # Папка на уровень выше текущего файла (например, '/Controllers' -> '/.env')
    if len(parents) >= 1:
        candidates.append(parents[0].parent / ".env")
    # Локально рядом с файлом (на случай альтернативной раскладки)
    candidates.append(here.parent / ".env")

    # Учитываем test/.env только если он достижим без выхода за границы
    if len(parents) >= 2:
        test_env = parents[1] / "test" / ".env"
        candidates.append(test_env)

    for env_path in candidates:
        try:
            if env_path.exists():
                for raw in env_path.read_text(encoding="utf-8").splitlines():
                    line = raw.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    k, v = line.split('=', 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    os.environ.setdefault(k, v)
        except Exception:
            # Тихо игнорируем ошибки чтения .env
            pass


_load_env_from_file()


client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

def _auth_header() -> str:
    token = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not token:
        raise RuntimeError("OPENROUTER_API_KEY not set in environment")
    return f"Bearer {token}"


def audio_to_text(audio):
    # Создаем объект распознавателя речи
    recognizer = sr.Recognizer()

    # Загружаем аудио файл
    audio_file = sr.AudioFile(audio)

    # Распознаем речь из аудио файла
    with audio_file as source:
        audio_data = recognizer.record(source)
        text = recognizer.recognize_google(audio_data, language="ru-RU")

    return text


def request_gpt_openrouter(text, previous_messages=None):
    """
    Sends a request to OpenRouter GPT-5.1 with reasoning support.
    previous_messages: list of dicts [{'role': 'user'/'assistant', 'content': str, 'reasoning_details': {...}}]
    """
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

    # Build messages list
    messages = [
        {"role": "system", "content": "Ты голосовой помощник банка. Отвечай кратко и по делу."},
        {"role": "user", "content": text}
    ]

    if previous_messages:
        # Append previous conversation preserving reasoning details
        for msg in previous_messages:
            messages.append(msg)

    try:
        response = client.chat.completions.create(
            model="openai/gpt-5.1",
            messages=messages,
            extra_body={"reasoning": {"enabled": True}}
        )
        return response.choices[0].message
    except Exception as e:
        return {"content": f"Ошибка запроса к AI: {e}", "reasoning_details": {}}


"""
method=GET

returns {
    status: true/false,
    message: OK / Error
    data = {{id, theme_id, message, time, type, code, sender}, ...} if success
}

sender: false -> user / true -> server
"""
@swag_from({
    'tags': ['Messages'],
    'responses': {
        200: {
            'description': 'Список сообщений',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
'properties': {
                            'id': {'type': 'integer'},
                            'message': {'type': 'string'},
                            'time': {'type': 'string'},
                            'type': {'type': 'boolean'},
                            'code': {'type': 'string'},
                            'sender': {'type': 'boolean'}
                        }
                        }
                    }
                }
            }
        }
    }
})
def get_messages():
    messages = Message.query.all()
    output = {
        'status': True if len(messages) > 0 else False,
        'message': "OK" if len(messages) > 0 else "Empty table",
        'data': []
    }
    for message in messages:
        user_data = {
            'id': message.id,
            'message': message.message,
            'time': message.time,
            'type': message.type,
            'code': message.code,
            'sender': message.sender
        }
        output['data'].append(user_data)
    return jsonify(output)

"""
method=GET/message_id

returns {
    status: true/false,
    message: OK / Error
    data = {id, theme_id, message, time, type, code, sender} if success
}

sender: 0 -> user / 1 -> server
"""
@swag_from({
    'tags': ['Messages'],
    'parameters': [
        {
            'name': 'item_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'ID сообщения'
        }
    ],
    'responses': {
        200: {
            'description': 'Информация о сообщении',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
'properties': {
                            'id': {'type': 'integer'},
                            'message': {'type': 'string'},
                            'time': {'type': 'string'},
                            'type': {'type': 'boolean'},
                            'code': {'type': 'string'},
                            'sender': {'type': 'boolean'}
                        }
                    }
                }
            }
        },
        404: {
            'description': 'Сообщение не найдено',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            }
        }
    }
})
def get_message(item_id):
    message = Message.query.get(item_id)
    if message:
        user_data = {
            'id': message.id,
            'message': message.message,
            'time': message.time,
            'type': message.type,
            'code': message.code,
            'sender': message.sender
        }
        return jsonify({'status': True, 'message': 'OK', 'data': user_data})
    else:
        return jsonify({'status': False, 'message': 'Message not found'}), 404


@swag_from({
    'tags': ['Messages'],
    'consumes': ['application/x-www-form-urlencoded', 'multipart/form-data'],
    'parameters': [
        {
            'name': 'user_id',
            'in': 'formData',
            'type': 'integer',
            'required': True,
            'description': 'ID пользователя'
        },
        {
            'name': 'chat_id',
            'in': 'formData',
            'type': 'integer',
            'required': False,
            'description': 'ID чата. Если не указан, будет создан новый чат'
        },
        {
            'name': 'type',
            'in': 'formData',
            'type': 'string',
            'required': True,
            'description': 'Тип сообщения (0 - текст, 1 - аудио)'
        },
        {
            'name': 'code',
            'in': 'formData',
            'type': 'string',
            'required': True,
            'description': 'Код сообщения'
        },
        {
            'name': 'message',
            'in': 'formData',
            'type': 'string',
            'required': False,
            'description': 'Текст сообщения (для type=0). Для type=1 отправьте файл в поле message как multipart/form-data.'
        }
    ],
    'responses': {
        201: {
            'description': 'Сообщение добавлено и ответ AI получен',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'boolean'},
                    'message': {'type': 'string', 'description': 'Ответ AI'},
                    'user_msg_time': {'type': 'string', 'description': 'Время отправки сообщения пользователем'},
                    'ai_msg_time': {'type': 'string', 'description': 'Время ответа AI'},
                    'redir': {'type': 'string', 'description': 'URL для перенаправления (если есть)'},
                    'message_id': {'type': 'integer', 'description': 'ID сохраненного сообщения пользователя'},
                    'chat_id': {'type': 'integer', 'description': 'ID чата'},
                    'reasoning_details': {'type': 'object', 'description': 'Детали рассуждений AI (если включены)'}
                }
            }
        },
        400: {
            'description': 'Ошибка в запросе',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            }
        }
    }
})
def add_message():
    user_id = request.form.get('user_id', -1)
    chat_id = request.form.get('chat_id')
    time_now = datetime.now()
    msg_type = request.form.get('type', 2)
    code = request.form.get('code')
    sender = False
    redir = ""

    if int(user_id) < 1 or not msg_type or not code:
        return jsonify({'status': False, 'message': 'Missing required fields'}), 400

    # Ensure user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({'status': False, 'message': 'User not found'}), 404

    # Handle chat creation if chat_id not provided
    if not chat_id:
        new_chat = Chat(name=f"Chat with User {user_id}", user_id=user_id)
        db.session.add(new_chat)
        db.session.commit()
        chat_id = new_chat.id
    else:
        chat_id = int(chat_id)
        chat = Chat.query.get(chat_id)
        if not chat:
            return jsonify({'status': False, 'message': 'Chat not found'}), 404

    # Handle audio messages
    if msg_type == '1':
        if 'message' not in request.files:
            return jsonify({'status': False, 'message': 'No file part'}), 400
        message_file = request.files['message']
        message_text = audio_to_text(message_file)
    else:
        message_text = request.form.get('message')
        if not message_text:
            return jsonify({'status': False, 'message': 'Message text is required'}), 400

    # Send to GPT-5.1 via OpenRouter
    assistant_msg_obj = request_gpt_openrouter(message_text)
    assistant_msg = (
        assistant_msg_obj.get("content")
        if isinstance(assistant_msg_obj, dict)
        else assistant_msg_obj.content
    )
    reasoning_details = (
        assistant_msg_obj.get("reasoning_details", {})
        if isinstance(assistant_msg_obj, dict)
        else getattr(assistant_msg_obj, "reasoning_details", {})
    )

    # Store messages in DB
    user_message = Message(
        message=message_text,
        time=time_now,
        type=bool(int(msg_type)),
        code=code,
        sender=sender,
        chat_id=chat_id
    )
    ai_message = Message(
        message=assistant_msg,
        time=datetime.now(),
        type=False,
        code="000",
        sender=True,
        chat_id=chat_id
    )

    db.session.add(user_message)
    db.session.add(ai_message)
    db.session.commit()

    return jsonify({
        'status': True,
        'message': assistant_msg,
        'user_msg_time': user_message.time.strftime('%Y-%m-%d %H:%M:%S'),
        'ai_msg_time': ai_message.time.strftime('%Y-%m-%d %H:%M:%S'),
        'redir': redir,
        'message_id': user_message.id,
        'chat_id': chat_id,
        'reasoning_details': reasoning_details
    }), 201