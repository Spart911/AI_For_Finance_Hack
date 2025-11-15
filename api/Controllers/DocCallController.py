from flask import Blueprint, request, jsonify
from flasgger import swag_from
from database import db
from Models.DocCall import DocCall
from Models.User import User
from Models.Document import Document

doc_call_bp = Blueprint("doc_call", __name__, url_prefix="/api/doc_call")


# -------------------------
# CREATE DocCall
# -------------------------
@doc_call_bp.route("/", methods=["POST"])
@swag_from({
    'tags': ['DocCall'],
    'parameters': [
        {'name': 'user_id', 'in': 'formData', 'type': 'integer', 'required': True},
        {'name': 'doc_id', 'in': 'formData', 'type': 'integer', 'required': True},
        {'name': 'call_count', 'in': 'formData', 'type': 'integer', 'required': False}
    ],
    'responses': {
        201: {'description': 'DocCall created'},
        400: {'description': 'Bad input'},
        404: {'description': 'User or Document not found'}
    }
})
def create_doc_call():
    user_id = request.form.get("user_id")
    doc_id = request.form.get("doc_id")
    call_count = request.form.get("call_count", 0)

    if not user_id or not doc_id:
        return jsonify({"status": False, "message": "user_id and doc_id are required"}), 400

    if not User.query.get(user_id):
        return jsonify({"status": False, "message": "User not found"}), 404

    if not Document.query.get(doc_id):
        return jsonify({"status": False, "message": "Document not found"}), 404

    dc = DocCall(user_id=user_id, doc_id=doc_id, call_count=call_count)
    db.session.add(dc)
    db.session.commit()

    return jsonify({"status": True, "doc_call_id": dc.id}), 201


# -------------------------
# GET ALL DocCalls
# -------------------------
@doc_call_bp.route("/", methods=["GET"])
@swag_from({
    'tags': ['DocCall'],
    'responses': {200: {'description': 'List of DocCall records'}}
})
def get_all_doc_calls():
    calls = DocCall.query.all()
    result = [
        {
            "id": c.id,
            "user_id": c.user_id,
            "doc_id": c.doc_id,
            "call_count": c.call_count
        }
        for c in calls
    ]
    return jsonify(result), 200


# -------------------------
# GET single DocCall
# -------------------------
@doc_call_bp.route("/<int:id>", methods=["GET"])
@swag_from({
    'tags': ['DocCall'],
    'parameters': [{'name': 'id', 'in': 'path', 'type': 'integer', 'required': True}],
    'responses': {
        200: {'description': 'DocCall entry'},
        404: {'description': 'Not found'}
    }
})
def get_doc_call(id):
    c = DocCall.query.get(id)
    if not c:
        return jsonify({"status": False, "message": "Not found"}), 404

    return jsonify({
        "id": c.id,
        "user_id": c.user_id,
        "doc_id": c.doc_id,
        "call_count": c.call_count
    }), 200


# -------------------------
# UPDATE DocCall
# -------------------------
@doc_call_bp.route("/<int:id>", methods=["PUT"])
@swag_from({
    'tags': ['DocCall'],
    'parameters': [
        {'name': 'id', 'in': 'path', 'type': 'integer', 'required': True},
        {'name': 'call_count', 'in': 'formData', 'type': 'integer', 'required': False}
    ],
    'responses': {
        200: {'description': 'Updated'},
        404: {'description': 'Not found'}
    }
})
def update_doc_call(id):
    c = DocCall.query.get(id)
    if not c:
        return jsonify({"status": False, "message": "Not found"}), 404

    call_count = request.form.get("call_count")
    if call_count is not None:
        c.call_count = int(call_count)

    db.session.commit()
    return jsonify({"status": True, "message": "Updated"}), 200


# -------------------------
# DELETE DocCall
# -------------------------
@doc_call_bp.route("/<int:id>", methods=["DELETE"])
@swag_from({
    'tags': ['DocCall'],
    'parameters': [{'name': 'id', 'in': 'path', 'type': 'integer', 'required': True}],
    'responses': {
        200: {'description': 'Deleted'},
        404: {'description': 'Not found'}
    }
})
def delete_doc_call(id):
    c = DocCall.query.get(id)
    if not c:
        return jsonify({"status": False, "message": "Not found"}), 404

    db.session.delete(c)
    db.session.commit()
    return jsonify({"status": True, "message": "Deleted"}), 200


# -------------------------
# INCREASE call_count (auto-create if none)
# -------------------------
@doc_call_bp.route("/<int:doc_id>/call", methods=["POST"])
@swag_from({
    'tags': ['DocCall'],
    'parameters': [
        {'name': 'doc_id', 'in': 'path', 'type': 'integer', 'required': True},
        {'name': 'user_id', 'in': 'formData', 'type': 'integer', 'required': True}
    ],
    'responses': {
        200: {'description': 'call_count increased'},
        400: {'description': 'user_id missing'},
        404: {'description': 'User or Document not found'}
    }
})
def increase_call_count(doc_id):
    user_id = request.form.get("user_id")

    if not user_id:
        return jsonify({"status": False, "message": "user_id required"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"status": False, "message": "User not found"}), 404

    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({"status": False, "message": "Document not found"}), 404

    dc = DocCall.query.filter_by(user_id=user_id, doc_id=doc_id).first()

    if not dc:
        dc = DocCall(user_id=user_id, doc_id=doc_id, call_count=1)
        db.session.add(dc)
    else:
        dc.call_count += 1

    db.session.commit()

    return jsonify({
        "status": True,
        "user_id": dc.user_id,
        "doc_id": dc.doc_id,
        "call_count": dc.call_count
    }), 200