from database import db
import bcrypt
from Models.UserDepartment import user_department
from Models.Department import Department
from Models.Chat import Chat

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(50), unique=True)
    first_name = db.Column(db.String(50), unique=False)
    last_name = db.Column(db.String(50), unique=False)
    password = db.Column(db.String(500), unique=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    description = db.Column(db.Text, nullable=True)

    departments = db.relationship(
        'Department',
        secondary=user_department,
        lazy='subquery',
        backref=db.backref('users', lazy=True)
    )

    chats = db.relationship(
        'Chat',
        backref='user',
        lazy=True,
        cascade="all, delete"
    )

    @property
    def role(self):
        if hasattr(self, 'manager_profile') and self.manager_profile:
            return 'manager'
        elif hasattr(self, 'employee_profile') and self.employee_profile:
            return 'employee'
        else:
            return None


    @property
    def manager_id(self):
        """Return manager_id if user is employee, else None"""
        if self.role == 'employee':
            return self.employee_profile.manager_id
        return None
    

    def __init__(self, login, first_name, last_name, password=None, is_admin=False, description=None):
        self.login = login
        self.first_name = first_name
        self.last_name = last_name
        self.is_admin = is_admin
        self.description = description

        if password:
            self.set_password(password)

    def set_password(self, password):
        self.password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))

    def __repr__(self):
        return f'<User {self.login}>'