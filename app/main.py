"""
Application entrypoint and Flask app factory.

This module wires together the core extensions, blueprints, and configuration
for the backend service. Authentication is handled with JWTs, and role-based
authorization uses the User.role field in the database to protect admin-only
endpoints (for example, routes under the /admin prefix).
"""

from flask import Blueprint, jsonify, request, g

from app.models import User, EngineLog

from werkzeug.security import generate_password_hash
from app.extensions import db
from datetime import datetime, timedelta, timezone
import jwt
from flask import current_app
from app.auth import jwt_required


main_bp = Blueprint("main", __name__)
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

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

    hashed = generate_password_hash(password)

    user = User(email=email, password_hash=hashed)
    db.session.add(user)
    db.session.commit()

    return jsonify({
        "id": user.id,
        "email": user.email,
        "created_at": user.created_at.isoformat()
    }), 201

@main_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    password = data.get("password")
    email = data.get("email")

    if not password:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid login data",
                "details": {
                    "password": ["Password is required"]
                }
            }
        }), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({
            "error": {
                "code": "INVALID_CREDENTIALS",
                "message": "Invalid email or password",
                "details": {}
            }
        }), 401

    from werkzeug.security import check_password_hash
    if not check_password_hash(user.password_hash, password):
        return jsonify({
            "error": {
                "code": "INVALID_CREDENTIALS",
                "message": "Invalid email or password",
                "details": {}
            }
        }), 401

    now = datetime.now(timezone.utc)
    lifetime_seconds = current_app.config.get("JWT_LIFETIME_SECONDS")

    payload = {
        "sub": str(user.id),
        "role": "user", 
        "exp": now + timedelta(seconds=lifetime_seconds)
    }

    token = jwt.encode(
        payload,
        current_app.config.get("JWT_SECRET"),
        algorithm="HS256"
    )

    return jsonify({"token": token}), 200

@main_bp.route("/users/me", methods=["GET"])
@jwt_required
def get_my_profile():
    # user_id was stamped by jwt_required, based on the JWT payload
    user_id = g.user_id

    user = User.query.get(user_id)
    if user is None:
        return jsonify({
            "error": {
                "code": "USER_NOT_FOUND",
                "message": "User not found",
                "details": {}
            }
        }), 404 

    return jsonify({
        "id": user.id,
        "email": user.email,
        # add other SAFE fields if you have them
        "display_name": user.display_name,
    }), 200

@main_bp.route("/users/me", methods=["PATCH"])
@jwt_required
def update_my_profile():
    user_id = g.user_id

    user = User.query.get(user_id)
    if user is None:
        return jsonify({
            "error": {
                "code": "USER_NOT_FOUND",
                "message": "User not found",
                "details": {}
            }
        }), 404

    data = request.get_json() or {}

    # Only allow updating display_name
    if "display_name" not in data:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid update data",
                "details": {
                    "display_name": ["Display name is required"]
                }
            }
        }), 400

    user.display_name = data["display_name"]
    db.session.commit()

    return jsonify({
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
    }), 200

@admin_bp.route("/ping", methods=["GET"])
@jwt_required
def admin_ping():
    """
    Admin-only health check endpoint.

    This route verifies two things in order:

    1. Authentication: @jwt_required ensures the request carries a valid
       JWT. If the token is missing or invalid, , the jwt_required decorator
       returns a 401 and this function is never called.
    2. Authorization: once authenticated, we load the User from the database
       and check that user.role == "admin". Non-admin users receive 403.

    The role value is read from the trusted User record in the database,
    never from client-submitted JSON.
    """
    # Authentication has already happened via @jwt_required().
    # At this point we trust that get_jwt_identity() came from a verified token.
    user_id = getattr(g, "user_id", None)
    user = User.query.get(user_id)

    # Authorization: only admin users are allowed to access this route.
    if user is None or user.role != "admin":
        return jsonify({"error": "forbidden"}), 403

    # Happy path: authenticated admin user.
    return jsonify({"status": "admin-ok"}), 200

@main_bp.route("/engine-logs", methods=["GET"])
@jwt_required
def list_engine_logs():
    """
    List EngineLog records owned by the authenticated user.

    This endpoint:
    -Requires a valid JWT (via @jwt_required), wich sets 
    g.user_id.
    Queries the database for EngineLog rows where user_id 
    matches g.user_id.
    - Returns a 200 OK with a JSON array of engine log objects
    for that user only, never exposing other users' logs.
    """
    user_id = g.user_id

    # Query all EngineLogs for this user
    logs = EngineLog.query.filter_by(user_id=user_id).all()

    # serialize the logs to JSON
    log_data = [
        {
            "id": log.id,
            "user_id": log.user_id,
            "from_engine": log.from_engine,
            "to_engine": log.to_engine,
            "payload_id": log.payload_id,
            "created_at": log.created_at.isoformat()
        }
        for log in logs
    ]
    return jsonify(log_data), 200

@main_bp.route("/engine-logs", methods=["POST"])
@jwt_required
def create_engine_log():
    """
    Create a new EngineLog owned by the authenticated user.
    
    This endpoint:
    - Accepts a json body with engine handoff fields:
      - from_engine
      - to_engine
      - payload_id
    - Validates the request body and returns a 400 VALIDATION_ERROR 
    if any required fields are missing.
    - Creates a new EngineLog row with user_id taken from the g.user_id
    (never from client input) and persistes it with the ORM session.
    - On sucess, returns the created EngineLog as JSON with a 201 
    status code."
    """
    data = request.get_json()

    if data is None:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid engine log data",
                "details": {
                    "body": ["JSON body is required"]
                }
            }
        }), 400

    from_engine = data.get("from_engine")
    to_engine = data.get("to_engine")
    payload_id = data.get("payload_id")

    if not from_engine or not to_engine or not payload_id:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid engine log data",
                "details": {
                    "from_engine": ["from_engine is required"],
                    "to_engine": ["to_engine is required"],
                    "payload_id": ["payload_id is required"]
                }
            }
        }), 400

    user_id = g.user_id

    # Create a new EngineLog owned by this user
    log = EngineLog(
        from_engine=from_engine,
        to_engine=to_engine,
        payload_id=payload_id,
        user_id=user_id,
        created_at=datetime.now(timezone.utc)
    )
    # persist it to the database
    db.session.add(log)
    db.session.commit()

    # Return the created log as JSON
    return jsonify({
        "id": log.id,
        "user_id": log.user_id,
        "from_engine": log.from_engine,
        "to_engine": log.to_engine,
        "payload_id": log.payload_id,
        "created_at": log.created_at.isoformat()
    }), 201
