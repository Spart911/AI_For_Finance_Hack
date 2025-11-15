import bcrypt
from database import db
from Models.Chat import Chat

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(50), unique=True)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    password = db.Column(db.String(500))
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Relationships
    chats = db.relationship('Chat', backref='user', lazy=True, cascade="all, delete")
    llm_memories = db.relationship('LLMMemory', back_populates='user', lazy=True, cascade="all, delete")

    # Optional relationships for DocCall and DocPermission
    doc_calls = db.relationship('DocCall', back_populates='user', lazy=True, cascade="all, delete")
    issued_permissions = db.relationship('DocPermission', foreign_keys='DocPermission.issuer_id', back_populates='issuer', lazy=True)
    received_permissions = db.relationship('DocPermission', foreign_keys='DocPermission.recipient_id', back_populates='recipient', lazy=True)

    @property
    def role(self):
        if hasattr(self, 'manager_profile') and self.manager_profile:
            return 'manager'
        elif hasattr(self, 'employee_profile') and self.employee_profile:
            return 'employee'
        return None

    @property
    def manager_id(self):
        return self.employee_profile.manager_id if self.role == 'employee' else None

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
