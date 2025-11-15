from database import db  
from flask import Blueprint
from Models.Document import Document

document_bp = Blueprint("document_bp", __name__)

# ------------------ CRUD Functions ------------------

# GET /api/documents/ — все документы
def get_documents():
    docs = Document.query.all()
    return jsonify([{"id": d.id, "name": d.name, "path": d.path} for d in docs])

# GET /api/documents/<id> — один документ
def get_document(item_id):
    doc = Document.query.get(item_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    return jsonify({"id": doc.id, "name": doc.name, "path": doc.path})

# POST /api/documents/ — создать документ
def add_document():
    data = request.json
    doc = Document(name=data["name"], path=data["path"])
    db.session.add(doc)
    db.session.commit()
    return jsonify({"id": doc.id, "name": doc.name, "path": doc.path})

# PUT /api/documents/<id> — обновить документ
def update_document(item_id):
    data = request.json
    doc = Document.query.get(item_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    doc.name = data.get("name", doc.name)
    doc.path = data.get("path", doc.path)
    db.session.commit()
    return jsonify({"id": doc.id, "name": doc.name, "path": doc.path})

# DELETE /api/documents/<id> — удалить документ
def delete_document(item_id):
    doc = Document.query.get(item_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    db.session.delete(doc)
    db.session.commit()
    return jsonify({"status": "deleted"})
