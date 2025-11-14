from flask import jsonify, request
from flasgger import swag_from
from Models.Chat import Chat, db
from Models.User import User


# ---------------------------------------------
# GET ALL CHATS
# ---------------------------------------------
@swag_from({
    'tags': ['Chats'],
    'responses': {
        200: {
            'description': 'Список чатов',
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
                                'name': {'type': 'string'},
                                'user_id': {'type': 'integer'}
                            }
                        }
                    }
                }
            }
        }
    }
})
def get_chats():
    chats = Chat.query.all()
    output = {
        'status': True if len(chats) > 0 else False,
        'message': "OK" if len(chats) > 0 else "Empty table",
        'data': []
    }
    for chat in chats:
        chat_data = {
            'id': chat.id,
            'name': chat.name,
            'user_id': chat.user_id
        }
        output['data'].append(chat_data)

    return jsonify(output)


# ---------------------------------------------
# GET CHAT BY ID
# ---------------------------------------------
@swag_from({
    'tags': ['Chats'],
    'parameters': [
        {
            'name': 'chat_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'ID чата'
        }
    ],
    'responses': {
        200: {
            'description': 'Информация о чате',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'integer'},
                            'name': {'type': 'string'},
                            'user_id': {'type': 'integer'}
                        }
                    }
                }
            }
        },
        404: {
            'description': 'Чат не найден',
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
def get_chat(chat_id):
    chat = Chat.query.get(chat_id)
    if chat:
        chat_data = {
            'id': chat.id,
            'name': chat.name,
            'user_id': chat.user_id
        }
        return jsonify({'status': True, 'message': 'OK', 'data': chat_data})
    else:
        return jsonify({'status': False, 'message': 'Chat not found'}), 404


# ---------------------------------------------
# CREATE CHAT
# ---------------------------------------------
@swag_from({
    'tags': ['Chats'],
    'consumes': ['application/x-www-form-urlencoded'],
    'parameters': [
        {
            'name': 'name',
            'in': 'formData',
            'type': 'string',
            'required': True,
            'description': 'Название чата'
        },
        {
            'name': 'user_id',
            'in': 'formData',
            'type': 'integer',
            'required': True,
            'description': 'ID пользователя-владельца'
        }
    ],
    'responses': {
        201: {
            'description': 'Чат успешно создан',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'chat_id': {'type': 'integer'}
                }
            }
        },
        400: {
            'description': 'Недостаточно данных',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            }
        },
        404: {
            'description': 'Пользователь не найден'
        }
    }
})
def add_chat():
    name = request.form.get('name')
    user_id = request.form.get('user_id')

    if not name or not user_id:
        return jsonify({'status': False, 'message': 'Missing required fields: name, user_id'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'status': False, 'message': 'User not found'}), 404

    new_chat = Chat(name=name, user_id=user_id)
    db.session.add(new_chat)
    db.session.commit()

    return jsonify({'status': True, 'message': 'Chat created successfully', 'chat_id': new_chat.id}), 201


# ---------------------------------------------
# UPDATE CHAT
# ---------------------------------------------
@swag_from({
    'tags': ['Chats'],
    'consumes': ['application/x-www-form-urlencoded'],
    'parameters': [
        {
            'name': 'chat_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'ID чата для обновления'
        },
        {
            'name': 'name',
            'in': 'formData',
            'type': 'string',
            'required': False,
            'description': 'Новое название чата'
        }
    ],
    'responses': {
        200: {
            'description': 'Чат успешно обновлен'
        },
        404: {
            'description': 'Чат не найден'
        }
    }
})
def update_chat(chat_id):
    chat = Chat.query.get(chat_id)
    if not chat:
        return jsonify({'status': False, 'message': 'Chat not found'}), 404

    name = request.form.get('name')
    if name:
        chat.name = name

    db.session.commit()
    return jsonify({'status': True, 'message': 'Chat updated successfully'})


# ---------------------------------------------
# DELETE CHAT
# ---------------------------------------------
@swag_from({
    'tags': ['Chats'],
    'parameters': [
        {
            'name': 'chat_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'ID чата'
        }
    ],
    'responses': {
        200: {
            'description': 'Чат удален'
        },
        404: {
            'description': 'Чат не найден'
        }
    }
})
def delete_chat(chat_id):
    chat = Chat.query.get(chat_id)
    if not chat:
        return jsonify({'status': False, 'message': 'Chat not found'}), 404

    db.session.delete(chat)
    db.session.commit()

    return jsonify({'status': True, 'message': 'Chat deleted successfully'})