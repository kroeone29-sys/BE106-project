from flask import Blueprint, jsonify, request

from app.models import User

main_bp = Blueprint("main", __name__)

@main_bp.route("/ping")
def ping():
    return "OK from blueprint"

@main_bp.route("/health")
def health():
    return jsonify({"status": "ok"}), 200

@main_bp.route("/register", methods=["POST"])
def register():

    data = request.get_json()
    password = data.get("password")
    email = data.get("email")
    
    if not password:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid registration data",
                "details": {
                    "password": ["Password is required"]
                }
            }
        }), 400

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({
            "error": {
                "code": "EMAIL_TAKEN",
                "message": "Email is already taken",
                "details": {
                    "email": ["This email is already in use"]
                }
            }
        }), 409

    return jsonify({
        "id": 1,
        "username": "kevin",
        "created_at": "2026-11-05T12:34:56Z"
    }), 201