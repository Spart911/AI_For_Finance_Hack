from database import db
from Models.User import User

class Manager(db.Model):
    __tablename__ = 'managers'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Link to the User table
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    user = db.relationship('User', backref=db.backref('manager_profile', uselist=False))

    def __repr__(self):
        return f'<Manager {self.user.login}>'