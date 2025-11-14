from database import db
from Models.User import User

class Employee(db.Model):
    __tablename__ = 'employees'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Link to the User table
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    user = db.relationship('User', backref=db.backref('employee_profile', uselist=False))
    
    # Link to Manager
    manager_id = db.Column(db.Integer, db.ForeignKey('managers.id'), nullable=True)
    manager = db.relationship('Manager', backref=db.backref('employees', lazy=True))

    def __repr__(self):
        return f'<Employee {self.user.login}>'