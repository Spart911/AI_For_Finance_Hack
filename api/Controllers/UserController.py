from flask import jsonify, request
from Models.User import User, db
from Models.RefreshToken import RefreshToken
from Models.Employee import Employee
from Models.Manager import Manager
from datetime import datetime
from utils.jwt_utils import generate_access_token, generate_refresh_token, decode_access_token
from utils.auth_helpers import authenticate_user, create_new_user, build_auth_response

import json
from flask import jsonify, Blueprint
from flasgger import swag_from


def str_to_bool(value):
    """Convert form string values to Python boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes')
    return False


@swag_from({
    'tags': ['Users'],
    'description': 'Получить список всех пользователей',
    'responses': {
        200: {
            'description': 'Список пользователей успешно получен',
            'examples': {
                'application/json': [
                    {
                        'id': 1,
                        'login': 'john',
                        'first_name': 'John',
                        'last_name': 'Doe',
                        'password': 'hashed_value',
                        'is_admin': False,
                        'description': 'Some text',
                        'departments': [
                            {'id': 1, 'name': 'IT'}
                        ]
                    }
                ]
            }
        }
    }
})
def get_users():
    users = User.query.all()
    output = {'status': bool(users), 'message': "OK" if users else "Empty table", 'data': []}

    for user in users:
        role_info = None
        if user.role == 'manager':
            role_info = {'role': 'manager', 'id': user.manager_profile.id}
        elif user.role == 'employee':
            role_info = {'role': 'employee', 'id': user.employee_profile.id, 'manager_id': user.manager_id}

        output['data'].append({
            'id': user.id,
            'login': user.login,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'password': user.password,
            'is_admin': user.is_admin,
            'description': user.description,
            'role': role_info
        })

    return jsonify(output)


@swag_from({
    'tags': ['Users'],
    'description': 'Получить конкретного пользователя по ID',
    'parameters': [{'name': 'item_id', 'in': 'path', 'required': True, 'type': 'integer'}],
    'responses': {200: {'description': 'Пользователь найден'}, 404: {'description': 'Пользователь не найден'}}
})
def get_user(item_id):
    user = User.query.get(item_id)
    if not user:
        return jsonify({'status': False, 'message': 'User not found'}), 404

    role_info = None
    if user.role == 'manager':
        role_info = {'role': 'manager', 'id': user.manager_profile.id}
    elif user.role == 'employee':
        role_info = {'role': 'employee', 'id': user.employee_profile.id, 'manager_id': user.manager_id}

    return jsonify({
        'status': True,
        'message': 'OK',
        'data': {
            'id': user.id,
            'login': user.login,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'password': user.password,
            'is_admin': user.is_admin,
            'description': user.description,
            'role': role_info
        }
    })


"""
method=POST
POST body: login (unique), first_name, last_name, password

returns {
    status: true/false,
    message: OK / Error
    data = inserted user id if success
}
"""


@swag_from({
    'tags': ['Users'],
    'description': 'Создать нового пользователя с ролью',
    'parameters': [
        {'name': 'login', 'in': 'formData', 'type': 'string', 'required': True},
        {'name': 'first_name', 'in': 'formData', 'type': 'string', 'required': True},
        {'name': 'last_name', 'in': 'formData', 'type': 'string', 'required': True},
        {'name': 'password', 'in': 'formData', 'type': 'string', 'required': True},
        {'name': 'is_admin', 'in': 'formData', 'type': 'boolean'},
        {'name': 'description', 'in': 'formData', 'type': 'string'},
        {'name': 'role', 'in': 'formData', 'type': 'string', 'description': 'employee or manager'},
        {'name': 'manager_id', 'in': 'formData', 'type': 'integer', 'description': 'Only for employees'}
    ],
    'responses': {
        201: {'description': 'Пользователь успешно создан'},
        400: {'description': 'Некорректные данные'},
        409: {'description': 'Пользователь с таким логином уже существует'}
    }
})
def add_user():
    login = request.form.get('login')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    password = request.form.get('password')
    is_admin = str_to_bool(request.form.get('is_admin', False))
    description = request.form.get('description')
    role = request.form.get('role')
    manager_id = request.form.get('manager_id')

    if not login or not first_name or not last_name or not password:
        return jsonify({'status': False, 'message': 'Missing required fields'}), 400

    if User.query.filter_by(login=login).first():
        return jsonify({'status': False, 'message': 'User with this login already exists'}), 409

    new_user = User(
        login=login,
        first_name=first_name,
        last_name=last_name,
        password=password,
        is_admin=is_admin,
        description=description
    )
    db.session.add(new_user)
    db.session.flush()  # flush to get new_user.id for role assignment

    # Role assignment
    if role:
        role_lower = role.lower()
        if role_lower == 'manager':
            manager_profile = Manager(user_id=new_user.id)
            db.session.add(manager_profile)
        elif role_lower == 'employee':
            emp_manager_id = int(manager_id) if manager_id else None
            employee_profile = Employee(user_id=new_user.id, manager_id=emp_manager_id)
            db.session.add(employee_profile)

    db.session.commit()
    return jsonify({'status': True, 'message': 'User added successfully', 'user_id': new_user.id}), 201


@swag_from({
    'tags': ['Users'],
    'description': 'Обновить данные пользователя, включая роль',
    'parameters': [
        {'name': 'item_id', 'in': 'path', 'required': True, 'type': 'integer'},
        {'name': 'body', 'in': 'body', 'required': True, 'schema': {
            'type': 'object',
            'properties': {
                'login': {'type': 'string'},
                'first_name': {'type': 'string'},
                'last_name': {'type': 'string'},
                'password': {'type': 'string'},
                'is_admin': {'type': 'boolean'},
                'description': {'type': 'string'},
                'role': {'type': 'string', 'description': 'employee or manager'},
                'manager_id': {'type': 'integer', 'description': 'Only for employees'}
            }
        }}
    ],
    'responses': {
        200: {'description': 'Пользователь обновлен'},
        404: {'description': 'Пользователь не найден'},
        400: {'description': 'Некорректные данные'}
    }
})
def update_user(item_id):
    user = User.query.get(item_id)
    if not user:
        return jsonify({'status': False, 'message': 'User not found'}), 404

    login = request.form.get('login')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    password = request.form.get('password')
    is_admin = request.form.get('is_admin')
    description = request.form.get('description')
    role = request.form.get('role')
    manager_id = request.form.get('manager_id')

    # Update basic fields
    if login:
        if User.query.filter(User.id != item_id, User.login == login).first():
            return jsonify({'status': False, 'message': 'Login already taken'}), 409
        user.login = login
    if first_name:
        user.first_name = first_name
    if last_name:
        user.last_name = last_name
    if password:
        user.set_password(password)
    if is_admin is not None:
        user.is_admin = str_to_bool(is_admin)
    if description is not None:
        user.description = description

    # Update role
    if role:
        role_lower = role.lower()
        # Remove old roles
        if user.role == 'manager' and user.manager_profile:
            db.session.delete(user.manager_profile)
        elif user.role == 'employee' and user.employee_profile:
            db.session.delete(user.employee_profile)

        # Assign new role
        if role_lower == 'manager':
            db.session.add(Manager(user_id=user.id))
        elif role_lower == 'employee':
            emp_manager_id = int(manager_id) if manager_id else None
            db.session.add(Employee(user_id=user.id, manager_id=emp_manager_id))

    db.session.commit()
    return jsonify({'status': True, 'message': 'User updated successfully'})


@swag_from({
    'tags': ['Auth'],
    'consumes': ['application/x-www-form-urlencoded'],
    'parameters': [
        {
            'name': 'login',
            'in': 'formData',
            'type': 'string',
            'required': True,
            'description': 'Логин пользователя'
        },
        {
            'name': 'password',
            'in': 'formData',
            'type': 'string',
            'required': True,
            'description': 'Пароль пользователя'
        }
    ],
    'responses': {
        200: {
            'description': 'Успешная аутентификация',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'access_token': {'type': 'string'},
                            'refresh_token': {'type': 'string'},
                            'user': {
                                'type': 'object',
                                'properties': {
                                    'id': {'type': 'integer'},
                                    'login': {'type': 'string'}
                                }
                            }
                        }
                    }
                }
            }
        },
        401: {
            'description': 'Неверные учетные данные',
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
def login():
    login = request.form.get('login')
    password = request.form.get('password')

    result = authenticate_user(login, password)
    
    if 'error' in result and 'status_code' in result:
        return jsonify(result['error']), result['status_code']
    
    response_data, user = result
    return build_auth_response('Login successful', response_data)


@swag_from({
    'tags': ['Auth'],
    'consumes': ['application/x-www-form-urlencoded'],
    'parameters': [
        {
            'name': 'refresh_token',
            'in': 'formData',
            'type': 'string',
            'required': True,
            'description': 'Refresh токен для обновления access токена'
        }
    ],
    'responses': {
        200: {
            'description': 'Токен успешно обновлен',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'access_token': {'type': 'string'},
                            'refresh_token': {'type': 'string'}
                        }
                    }
                }
            }
        },
        400: {
            'description': 'Отсутствует refresh токен',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            }
        },
        401: {
            'description': 'Недействительный или просроченный токен',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            }
        },
        404: {
            'description': 'Пользователь не найден',
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
def refresh_token():
    refresh_token_str = request.form.get('refresh_token')
    
    if not refresh_token_str:
        return jsonify({'status': False, 'message': 'Refresh token is required'}), 400
    
    token_record = RefreshToken.query.filter_by(token=refresh_token_str).first()
    
    if not token_record or token_record.is_revoked or token_record.expires_at < datetime.utcnow():
        return jsonify({'status': False, 'message': 'Invalid or expired refresh token'}), 401
    
    user = User.query.get(token_record.user_id)
    if not user:
        return jsonify({'status': False, 'message': 'User not found'}), 404
    
    # Revoke the old refresh token
    token_record.is_revoked = True
    
    # Generate new tokens
    access_token = generate_access_token(user.id)
    new_refresh_token_str = generate_refresh_token()
    
    # Save new refresh token
    new_refresh_token = RefreshToken(token=new_refresh_token_str, user_id=user.id)
    db.session.add(new_refresh_token)
    db.session.commit()
    
    return jsonify({
        'status': True,
        'message': 'Token refreshed successfully',
        'data': {
            'access_token': access_token,
            'refresh_token': new_refresh_token_str
        }
    })


@swag_from({
    'tags': ['Auth'],
    'consumes': ['application/x-www-form-urlencoded'],
    'parameters': [
        {
            'name': 'login',
            'in': 'formData',
            'type': 'string',
            'required': True,
            'description': 'Логин нового пользователя (должен быть уникальным)'
        },
        {
            'name': 'first_name',
            'in': 'formData',
            'type': 'string',
            'required': True,
            'description': 'Имя нового пользователя'
        },
        {
            'name': 'last_name',
            'in': 'formData',
            'type': 'string',
            'required': True,
            'description': 'Фамилия нового пользователя'
        },
        {
            'name': 'password',
            'in': 'formData',
            'type': 'string',
            'required': True,
            'description': 'Пароль нового пользователя'
        }
    ],
    'responses': {
        201: {
            'description': 'Пользователь успешно зарегистрирован',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'access_token': {'type': 'string'},
                            'refresh_token': {'type': 'string'},
                            'user': {
                                'type': 'object',
                                'properties': {
                                    'id': {'type': 'integer'},
                                    'login': {'type': 'string'}
                                }
                            }
                        }
                    }
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
        },
        409: {
            'description': 'Пользователь с таким логином уже существует',
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
def register():
    login = request.form.get('login')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    password = request.form.get('password')

    result = create_new_user(login, first_name, last_name, password)
    
    if 'error' in result and 'status_code' in result:
        return jsonify(result['error']), result['status_code']
    
    response_data, user = result
    return build_auth_response('User registered successfully', response_data)

# ----------------------- MANAGER CRUD -----------------------

@swag_from({
    'tags': ['Managers'],
    'description': 'Get all managers',
    'responses': {200: {'description': 'List of managers'}}
})
def get_managers():
    managers = Manager.query.all()
    data = []
    for m in managers:
        data.append({
            'id': m.id,
            'user_id': m.user_id,
            'login': m.user.login,
            'first_name': m.user.first_name,
            'last_name': m.user.last_name,
            'description': m.user.description
        })
    return jsonify({'status': True, 'message': 'OK', 'data': data})


@swag_from({
    'tags': ['Managers'],
    'description': 'Get manager by ID',
    'parameters': [{'name': 'item_id', 'in': 'path', 'required': True, 'type': 'integer'}],
    'responses': {200: {'description': 'Manager found'}, 404: {'description': 'Manager not found'}}
})
def get_manager(item_id):
    manager = Manager.query.get(item_id)
    if not manager:
        return jsonify({'status': False, 'message': 'Manager not found'}), 404
    data = {
        'id': manager.id,
        'user_id': manager.user_id,
        'login': manager.user.login,
        'first_name': manager.user.first_name,
        'last_name': manager.user.last_name,
        'description': manager.user.description
    }
    return jsonify({'status': True, 'message': 'OK', 'data': data})


@swag_from({
    'tags': ['Managers'],
    'description': 'Create a new manager',
    'parameters': [
        {'name': 'user_id', 'in': 'formData', 'type': 'integer', 'required': True},
    ],
    'responses': {201: {'description': 'Manager created'}, 400: {'description': 'Invalid data'}}
})
def add_manager():
    user_id = request.form.get('user_id')
    if not user_id or Manager.query.filter_by(user_id=user_id).first():
        return jsonify({'status': False, 'message': 'Invalid or duplicate user_id'}), 400
    manager = Manager(user_id=user_id)
    db.session.add(manager)
    db.session.commit()
    return jsonify({'status': True, 'message': 'Manager added', 'data': {'id': manager.id}}), 201


@swag_from({
    'tags': ['Managers'],
    'description': 'Update manager (link to user)',
    'parameters': [
        {'name': 'item_id', 'in': 'path', 'required': True, 'type': 'integer'},
        {'name': 'user_id', 'in': 'formData', 'type': 'integer', 'required': True}
    ],
    'responses': {200: {'description': 'Manager updated'}, 404: {'description': 'Manager not found'}}
})
def update_manager(item_id):
    manager = Manager.query.get(item_id)
    if not manager:
        return jsonify({'status': False, 'message': 'Manager not found'}), 404
    user_id = request.form.get('user_id')
    if user_id:
        manager.user_id = user_id
    db.session.commit()
    return jsonify({'status': True, 'message': 'Manager updated'})


@swag_from({
    'tags': ['Managers'],
    'description': 'Delete manager by ID',
    'parameters': [{'name': 'item_id', 'in': 'path', 'required': True, 'type': 'integer'}],
    'responses': {200: {'description': 'Manager deleted'}, 404: {'description': 'Manager not found'}}
})
def delete_manager(item_id):
    manager = Manager.query.get(item_id)
    if not manager:
        return jsonify({'status': False, 'message': 'Manager not found'}), 404
    db.session.delete(manager)
    db.session.commit()
    return jsonify({'status': True, 'message': 'Manager deleted'})

# ----------------------- EMPLOYEE CRUD -----------------------

@swag_from({
    'tags': ['Employees'],
    'description': 'Get all employees',
    'responses': {200: {'description': 'List of employees'}}
})
def get_employees():
    employees = Employee.query.all()
    data = []
    for e in employees:
        data.append({
            'id': e.id,
            'user_id': e.user_id,
            'login': e.user.login,
            'first_name': e.user.first_name,
            'last_name': e.user.last_name,
            'description': e.user.description,
            'manager_id': e.manager_id
        })
    return jsonify({'status': True, 'message': 'OK', 'data': data})


@swag_from({
    'tags': ['Employees'],
    'description': 'Get employee by ID',
    'parameters': [{'name': 'item_id', 'in': 'path', 'required': True, 'type': 'integer'}],
    'responses': {200: {'description': 'Employee found'}, 404: {'description': 'Employee not found'}}
})
def get_employee(item_id):
    employee = Employee.query.get(item_id)
    if not employee:
        return jsonify({'status': False, 'message': 'Employee not found'}), 404
    data = {
        'id': employee.id,
        'user_id': employee.user_id,
        'login': employee.user.login,
        'first_name': employee.user.first_name,
        'last_name': employee.user.last_name,
        'description': employee.user.description,
        'manager_id': employee.manager_id
    }
    return jsonify({'status': True, 'message': 'OK', 'data': data})


@swag_from({
    'tags': ['Employees'],
    'description': 'Create a new employee',
    'parameters': [
        {'name': 'user_id', 'in': 'formData', 'type': 'integer', 'required': True},
        {'name': 'manager_id', 'in': 'formData', 'type': 'integer'}
    ],
    'responses': {201: {'description': 'Employee created'}, 400: {'description': 'Invalid data'}}
})
def add_employee():
    user_id = request.form.get('user_id')
    manager_id = request.form.get('manager_id')
    if not user_id or Employee.query.filter_by(user_id=user_id).first():
        return jsonify({'status': False, 'message': 'Invalid or duplicate user_id'}), 400
    employee = Employee(user_id=user_id, manager_id=manager_id)
    db.session.add(employee)
    db.session.commit()
    return jsonify({'status': True, 'message': 'Employee added', 'data': {'id': employee.id}}), 201


@swag_from({
    'tags': ['Employees'],
    'description': 'Update employee',
    'parameters': [
        {'name': 'item_id', 'in': 'path', 'required': True, 'type': 'integer'},
        {'name': 'user_id', 'in': 'formData', 'type': 'integer'},
        {'name': 'manager_id', 'in': 'formData', 'type': 'integer'}
    ],
    'responses': {200: {'description': 'Employee updated'}, 404: {'description': 'Employee not found'}}
})
def update_employee(item_id):
    employee = Employee.query.get(item_id)
    if not employee:
        return jsonify({'status': False, 'message': 'Employee not found'}), 404
    user_id = request.form.get('user_id')
    manager_id = request.form.get('manager_id')
    if user_id:
        employee.user_id = user_id
    if manager_id is not None:
        employee.manager_id = manager_id
    db.session.commit()
    return jsonify({'status': True, 'message': 'Employee updated'})


@swag_from({
    'tags': ['Employees'],
    'description': 'Delete employee by ID',
    'parameters': [{'name': 'item_id', 'in': 'path', 'required': True, 'type': 'integer'}],
    'responses': {200: {'description': 'Employee deleted'}, 404: {'description': 'Employee not found'}}
})
def delete_employee(item_id):
    employee = Employee.query.get(item_id)
    if not employee:
        return jsonify({'status': False, 'message': 'Employee not found'}), 404
    db.session.delete(employee)
    db.session.commit()
    return jsonify({'status': True, 'message': 'Employee deleted'})