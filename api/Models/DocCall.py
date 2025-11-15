from database import db

class DocCall(db.Model):
    __tablename__ = "doc_call"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    doc_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    call_count = db.Column(db.BigInteger, default=0, nullable=False)

    user = db.relationship("User", back_populates="doc_calls", lazy=True)
    document = db.relationship("Document", back_populates="doc_calls", lazy=True)

    def __repr__(self):
        return f"<DocCall user={self.user_id} doc={self.doc_id} count={self.call_count}>"
