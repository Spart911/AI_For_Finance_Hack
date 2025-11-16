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
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
rag_model = SentenceTransformer("all-MiniLM-L6-v2")

    



QDRANT_HOST = "qdrant"  
QDRANT_PORT = 6333
COLLECTION_NAME = "documents_rag"

rag_client = QdrantClient(
    host=QDRANT_HOST,
    port=QDRANT_PORT
)

API_URL = "https://openrouter.ai/api/v1/chat/completions"


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
    base_url="https://api.polza.ai/api/v1",
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

def query_rag_context(query: str, top_k=1) -> str:
    """
    Выполняет поиск по Qdrant и возвращает объединённый текст из наиболее релевантных чанков.
    """
    try:
        emb = rag_model.encode(query).tolist() 
        results = rag_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=emb,
            limit=top_k
        )
        context_chunks = [hit.payload.get("text", "") for hit in results]

        return "\n".join(context_chunks).strip()
    except Exception as e:
        return f"RAG context unavailable: {e}"

def request_gpt_openrouter(text, previous_messages=None):
    """
    Sends a request to OpenRouter GPT-5.1 with reasoning support.
    previous_messages: list of dicts [{'role': 'user'/'assistant', 'content': str, 'reasoning_details': {...}}]
    """
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    
    context = query_rag_context(text)
    
    system_prompt = "Ты - финансовый помощник, который развернуто и грамотно отвечает на вопросы с использованием информации из предоставленного документа."

    user_content = f'Контекст: {context}. Вопрос: {text}'
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    if previous_messages:
        messages.extend(previous_messages)

    try:
        response = client.chat.completions.create(
            model="qwen/qwen-turbo",
            messages=messages,
            extra_body={"reasoning": {"enabled": True}}
        )
        
        msg = response.choices[0].message
        if isinstance(msg, dict):
            content = msg.get("content", "")
            reasoning_details = msg.get("reasoning_details", {})
        else:
            content = msg.content
            reasoning_details = {}

        # Возвращаем словарь с контекстом и ответом
        return {
            "content": content,
            "reasoning_details": reasoning_details,
            "context": context
        }
    except Exception as e:
        return {
            "content": f"Ошибка запроса к AI: {e}",
            "reasoning_details": {},
            "context": context
        }



"""
method=GET

returns {
    status: true/false,
    message: OK / Error
    data = {{id, theme_id, message, time, type, sender}, ...} if success
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
            'sender': message.sender
        }
        output['data'].append(user_data)
    return jsonify(output)

"""
method=GET/message_id

returns {
    status: true/false,
    message: OK / Error
    data = {id, theme_id, message, time, type, sender} if success
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
    msg_type = request.form.get('type', '0')  # по умолчанию текст
    sender = False
    redir = ""

    # Проверяем, что пользователь существует
    user = User.query.get(user_id)
    if not user:
        return jsonify({'status': False, 'message': 'User not found'}), 404

    # Создаём чат, если chat_id не указан
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

    # Обрабатываем аудио-сообщения
    if msg_type == '1':
        if 'message' not in request.files:
            return jsonify({'status': False, 'message': 'No file part'}), 400
        message_file = request.files['message']
        message_text = audio_to_text(message_file)
    else:
        message_text = request.form.get('message')
        if not message_text:
            return jsonify({'status': False, 'message': 'Message text is required'}), 400

    # Отправка запроса к GPT-5.1 через OpenRouter
    assistant_msg_obj = request_gpt_openrouter(message_text)

    # Извлечение данных из словаря
    assistant_msg = assistant_msg_obj.get("content", "")
    reasoning_details = assistant_msg_obj.get("reasoning_details", {})
    rag_context = assistant_msg_obj.get("context", "")

    # Сохраняем сообщение пользователя в БД
    user_message = Message(
        message=message_text,
        time=time_now,
        type=bool(int(msg_type)),
        sender=sender,
        chat_id=chat_id
    )
    # Сохраняем сообщение AI в БД
    ai_message = Message(
        message=assistant_msg,
        time=datetime.now(),
        type=False,
        sender=True,
        chat_id=chat_id
    )

    db.session.add(user_message)
    db.session.add(ai_message)
    db.session.commit()
    
    return jsonify({
        'status': True,
        'message': assistant_msg,
        'rag_context': rag_context,  # возвращаем RAG-контекст
        'user_msg_time': user_message.time.strftime('%Y-%m-%d %H:%M:%S'),
        'ai_msg_time': ai_message.time.strftime('%Y-%m-%d %H:%M:%S'),
        'redir': redir,
        'message_id': user_message.id,
        'chat_id': chat_id,
        'reasoning_details': reasoning_details
    }), 201
