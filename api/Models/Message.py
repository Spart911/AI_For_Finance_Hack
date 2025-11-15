from database import db

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(2048), unique=False)
    time = db.Column(db.DateTime, unique=False)
    type = db.Column(db.Boolean) # 0 - text, 1 - audio
    sender = db.Column(db.Boolean) # 0 - user, 1 - server
    chat_id = db.Column(db.Integer, db.ForeignKey('chat.id'), nullable=False)


    def __init__(self, message, time, type, sender, chat_id):  
        self.message = message 
        self.time = time
        self.type = type
        self.sender = sender
        self.chat_id = chat_id

    def __repr__(self):
        return '<Message %r>' % self.message
