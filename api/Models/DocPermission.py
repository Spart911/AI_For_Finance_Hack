from datetime import datetime
from database import db

class DocPermission(db.Model):
    __tablename__ = "doc_permissions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    issuer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    doc_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    set_on = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    issuer = db.relationship("User", foreign_keys=[issuer_id], back_populates="issued_permissions")
    recipient = db.relationship("User", foreign_keys=[recipient_id], back_populates="received_permissions")
    document = db.relationship("Document", back_populates="permissions")

    def __repr__(self):
        return f"<DocPermission doc={self.doc_id} from={self.issuer_id} to={self.recipient_id}>"
