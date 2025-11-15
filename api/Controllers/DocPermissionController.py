from flask import Blueprint, request, jsonify
from flasgger import swag_from
from datetime import datetime
from database import db
from Models.DocPermission import DocPermission
from Models.User import User
from Models.Document import Document

doc_permission_bp = Blueprint("doc_permission", __name__, url_prefix="/api/doc_permissions")


# -------------------------
# CREATE — issue permission
# -------------------------
@doc_permission_bp.route("/", methods=["POST"])
@swag_from({
    'tags': ['DocPermissions'],
    'parameters': [
        {'name': 'issuer_id', 'in': 'formData', 'type': 'integer', 'required': True},
        {'name': 'recipient_id', 'in': 'formData', 'type': 'integer', 'required': True},
        {'name': 'doc_id', 'in': 'formData', 'type': 'integer', 'required': True}
    ],
    'responses': {
        201: {'description': 'Permission granted'},
        400: {'description': 'Bad input'},
        404: {'description': 'User or Document not found'}
    }
})
def create_permission():
    issuer_id = request.form.get("issuer_id")
    recipient_id = request.form.get("recipient_id")
    doc_id = request.form.get("doc_id")

    if not issuer_id or not recipient_id or not doc_id:
        return jsonify({"status": False, "message": "issuer_id, recipient_id and doc_id are required"}), 400

    issuer = User.query.get(issuer_id)
    if not issuer:
        return jsonify({"status": False, "message": "Issuer not found"}), 404

    recipient = User.query.get(recipient_id)
    if not recipient:
        return jsonify({"status": False, "message": "Recipient not found"}), 404

    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({"status": False, "message": "Document not found"}), 404

    permission = DocPermission(
        issuer_id=issuer_id,
        recipient_id=recipient_id,
        doc_id=doc_id,
        set_on=datetime.utcnow()
    )
    db.session.add(permission)
    db.session.commit()

    return jsonify({"status": True, "permission_id": permission.id}), 201


# -------------------------
# GET ALL permissions
# -------------------------
@doc_permission_bp.route("/", methods=["GET"])
@swag_from({
    'tags': ['DocPermissions'],
    'responses': {
        200: {'description': 'List of permissions'}
    }
})
def get_all_permissions():
    permissions = DocPermission.query.all()
    result = [
        {
            "id": p.id,
            "issuer_id": p.issuer_id,
            "recipient_id": p.recipient_id,
            "doc_id": p.doc_id,
            "set_on": p.set_on.isoformat()
        }
        for p in permissions
    ]
    return jsonify(result), 200


# -------------------------
# GET one permission
# -------------------------
@doc_permission_bp.route("/<int:permission_id>", methods=["GET"])
@swag_from({
    'tags': ['DocPermissions'],
    'parameters': [
        {'name': 'permission_id', 'in': 'path', 'type': 'integer', 'required': True}
    ],
    'responses': {
        200: {'description': 'Permission entry'},
        404: {'description': 'Not found'}
    }
})
def get_permission(permission_id):
    p = DocPermission.query.get(permission_id)
    if not p:
        return jsonify({"status": False, "message": "Not found"}), 404

    return jsonify({
        "id": p.id,
        "issuer_id": p.issuer_id,
        "recipient_id": p.recipient_id,
        "doc_id": p.doc_id,
        "set_on": p.set_on.isoformat()
    }), 200


# -------------------------
# DELETE permission
# -------------------------
@doc_permission_bp.route("/<int:permission_id>", methods=["DELETE"])
@swag_from({
    'tags': ['DocPermissions'],
    'parameters': [
        {'name': 'permission_id', 'in': 'path', 'type': 'integer', 'required': True}
    ],
    'responses': {
        200: {'description': 'Deleted'},
        404: {'description': 'Not found'}
    }
})
def delete_permission(permission_id):
    p = DocPermission.query.get(permission_id)
    if not p:
        return jsonify({"status": False, "message": "Not found"}), 404

    db.session.delete(p)
    db.session.commit()
    return jsonify({"status": True, "message": "Deleted"}), 200


# -------------------------
# GET permissions given BY a user
# -------------------------
@doc_permission_bp.route("/user/<int:user_id>/given_permissions", methods=["GET"])
@swag_from({
    'tags': ['DocPermissions'],
    'parameters': [
        {'name': 'user_id', 'in': 'path', 'type': 'integer', 'required': True}
    ],
    'responses': {
        200: {'description': 'Permissions issued by user'},
        404: {'description': 'User not found'}
    }
})
def get_given_permissions(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"status": False, "message": "User not found"}), 404

    permissions = DocPermission.query.filter_by(issuer_id=user_id).all()
    result = [
        {
            "id": p.id,
            "recipient_id": p.recipient_id,
            "doc_id": p.doc_id,
            "set_on": p.set_on.isoformat()
        }
        for p in permissions
    ]
    return jsonify(result), 200


# -------------------------
# GET permissions received BY a user
# -------------------------
@doc_permission_bp.route("/user/<int:user_id>/received_permissions", methods=["GET"])
@swag_from({
    'tags': ['DocPermissions'],
    'parameters': [
        {'name': 'user_id', 'in': 'path', 'type': 'integer', 'required': True}
    ],
    'responses': {
        200: {'description': 'Permissions received by user'},
        404: {'description': 'User not found'}
    }
})
def get_received_permissions(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"status": False, "message": "User not found"}), 404

    permissions = DocPermission.query.filter_by(recipient_id=user_id).all()
    result = [
        {
            "id": p.id,
            "issuer_id": p.issuer_id,
            "doc_id": p.doc_id,
            "set_on": p.set_on.isoformat()
        }
        for p in permissions
    ]
    return jsonify(result), 200


# -------------------------
# GET permissions for a document
# -------------------------
@doc_permission_bp.route("/document/<int:doc_id>", methods=["GET"])
@swag_from({
    'tags': ['DocPermissions'],
    'parameters': [
        {'name': 'doc_id', 'in': 'path', 'type': 'integer', 'required': True}
    ],
    'responses': {
        200: {'description': 'Permissions for the document'},
        404: {'description': 'Document not found'}
    }
})
def get_document_permissions(doc_id):
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({"status": False, "message": "Document not found"}), 404

    permissions = DocPermission.query.filter_by(doc_id=doc_id).all()
    result = [
        {
            "id": p.id,
            "issuer_id": p.issuer_id,
            "recipient_id": p.recipient_id,
            "set_on": p.set_on.isoformat()
        }
        for p in permissions
    ]
    return jsonify(result), 200