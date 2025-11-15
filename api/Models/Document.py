from database import db
    
class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)      # Имя документа
    path = db.Column(db.String(1024), nullable=False, unique=True)     # Путь к файлу

    doc_calls = db.relationship("DocCall", back_populates="document", lazy=True, cascade="all, delete")
    permissions = db.relationship("DocPermission", back_populates="document", lazy=True, cascade="all, delete")

    def __repr__(self):
        return f"<Document {self.name} ({self.id})>"