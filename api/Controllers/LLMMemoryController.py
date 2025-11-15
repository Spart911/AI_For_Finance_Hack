from flask import Blueprint, request, jsonify
from flasgger import swag_from

from database import db
from Models.LLMMemory import LLMMemory
from Models.User import User

llm_memory_bp = Blueprint("llm_memory", __name__, url_prefix="/api/llm_memory")


# -------------------------
# CREATE memory
# -------------------------
@llm_memory_bp.route("/", methods=["POST"])
@swag_from({
    'tags': ['LLM Memory'],
    'parameters': [
        {'name': 'user_id', 'in': 'formData', 'type': 'integer', 'required': True},
        {'name': 'info', 'in': 'formData', 'type': 'string', 'required': True}
    ],
    'responses': {
        201: {'description': 'Memory record created'},
        400: {'description': 'Bad input'},
        404: {'description': 'User not found'}
    }
})
def create_memory():
    user_id = request.form.get("user_id")
    info = request.form.get("info")

    if not user_id or not info:
        return jsonify({"status": False, "message": "user_id and info are required"}), 400

    if not User.query.get(user_id):
        return jsonify({"status": False, "message": "User not found"}), 404

    memory = LLMMemory(user_id=user_id, info=info)
    db.session.add(memory)
    db.session.commit()

    return jsonify({"status": True, "id": memory.id}), 201


# -------------------------
# GET ALL memories
# -------------------------
@llm_memory_bp.route("/", methods=["GET"])
@swag_from({
    'tags': ['LLM Memory'],
    'responses': {200: {'description': 'List of all memories'}}
})
def get_all_memories():
    memories = LLMMemory.query.all()
    result = [{"id": m.id, "user_id": m.user_id, "info": m.info} for m in memories]
    return jsonify(result), 200


# -------------------------
# GET one memory
# -------------------------
@llm_memory_bp.route("/<int:id>", methods=["GET"])
@swag_from({
    'tags': ['LLM Memory'],
    'responses': {200: {'description': 'Memory entry'}, 404: {'description': 'Not found'}}
})
def get_memory(id):
    m = LLMMemory.query.get(id)
    if not m:
        return jsonify({"status": False, "message": "Not found"}), 404
    return jsonify({"id": m.id, "user_id": m.user_id, "info": m.info}), 200


# -------------------------
# UPDATE memory
# -------------------------
@llm_memory_bp.route("/<int:id>", methods=["PUT"])
@swag_from({
    'tags': ['LLM Memory'],
    'parameters': [
        {'name': 'info', 'in': 'formData', 'type': 'string', 'required': False}
    ],
    'responses': {200: {'description': 'Updated'}, 404: {'description': 'Not found'}}
})
def update_memory(id):
    m = LLMMemory.query.get(id)
    if not m:
        return jsonify({"status": False, "message": "Not found"}), 404

    info = request.form.get("info")
    if info:
        m.info = info

    db.session.commit()
    return jsonify({"status": True, "message": "Updated"}), 200


# -------------------------
# DELETE memory
# -------------------------
@llm_memory_bp.route("/<int:id>", methods=["DELETE"])
@swag_from({
    'tags': ['LLM Memory'],
    'responses': {200: {'description': 'Deleted'}, 404: {'description': 'Not found'}}
})
def delete_memory(id):
    m = LLMMemory.query.get(id)
    if not m:
        return jsonify({"status": False, "message": "Not found"}), 404

    db.session.delete(m)
    db.session.commit()
    return jsonify({"status": True, "message": "Deleted"}), 200


# -------------------------
# GET latest memory for a user
# -------------------------
@llm_memory_bp.route("/user/<int:user_id>/latest", methods=["GET"])
@swag_from({
    'tags': ['LLM Memory'],
    'responses': {
        200: {'description': 'Latest LLM memory for user'},
        404: {'description': 'No memory found'}
    }
})
def get_latest_memory(user_id):
    m = LLMMemory.query.filter_by(user_id=user_id).order_by(LLMMemory.id.desc()).first()
    if not m:
        return jsonify({"status": False, "message": "No memory found"}), 404
    return jsonify({"id": m.id, "user_id": m.user_id, "info": m.info}), 200
