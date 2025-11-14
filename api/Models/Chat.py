from database import db

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    # FK to User
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # One chat → many messages
    messages = db.relationship(
        'Message',
        backref='chat',
        lazy=True,
        cascade="all, delete"
    )

    def __init__(self, name, user_id):
        self.name = name
        self.user_id = user_id

    def __repr__(self):
        return f'<Chat {self.name}>'
