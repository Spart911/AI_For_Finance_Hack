from database import db

class LLMMemory(db.Model):
    __tablename__ = "llm_memory"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    info = db.Column(db.String(5000), nullable=False)

    # Use back_populates to match User.llm_memories
    user = db.relationship("User", back_populates="llm_memories", lazy=True)

    def __repr__(self):
        return f"<LLMMemory id={self.id} user={self.user_id}>"
