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

@main_bp.route("/engine-logs/<int:log_id>", methods=["GET"])
@jwt_required
def get_engine_log(log_id: int):
    """
    Retrieve a single EngineLog by its ID,
    
    This endpoint:
    - Requires a valid JWT (@jwt_required) and uses g.user_id as
    the caller identity.
    - Looks up an EngineLog row by the given `log_id`.
    - Returns 404 with the standard JSON error envelope when no
    row exists.
    
    Ownership notes
    - This version only distinguishes between "exists" and "does 
    not exist".
    - Handling the case where the log exists but belongs to a different user_id
    (e.g., 403 or non enumerating 404) is implemented in a
    later lesson.
    
    Args:
        log_id: Integer primary key of the EngineLog to to retrieve.
        
    Returns:
        A flask response object with:
        - 200 and a JSON representation of the EngineLog on 
        success.
        - 404 and the JSON error envelope if no EngineLog is 
        found for `log_id`.
        """

    # 1. Try to find the log by primary key
    log = EngineLog.query.get(log_id)

    # 2. If not found, return 404 with JSON error envelope
    if log is None:
        return jsonify({
            "error": {
                "code": "NOT_FOUND",
                "message": "EngineLog not found",
                "details": {
                    "log_id": log_id
                }
            }
        }), 404

    # 3. If found, return 200 with the serialized log
    return jsonify({
        "id": log.id,
        "user_id": log.user_id,
        "from_engine": log.from_engine,
        "to_engine": log.to_engine,
        "payload_id": log.payload_id,
        "created_at": log.created_at.isoformat(),
    }), 200

@main_bp.delete("/engine-logs/<int:log_id>")
@jwt_required
def delete_engine_log(log_id: int):
    """
    Permanently delete an existing EngineLog.

    This endpoint deletes one EngineLog row identified by
    `log_id`.

    Ownership is not enorced yet; any authenticated user can
    delete any existing EngineLog. A later change will restrict
    deletions to the owner or convert this into an archive flow.
    
    Behavior:
    - On success:
        - Looks up the EngineLog by `log_id`.
        - Delets the row from the database.
        - Commits the deletion.
        - Retuns 204 No Content with an empty response body.
    - If no EngineLog exists with the given ID:
        - Returns 404 NOT_FOUND with the standard error envelope.

    Authentication:
    - Requires a valid JWT in the Authoriaztion header.
    - Uses `@jwt_required` to populate `g.user_id`, but does not 
    check ownership yet.
    """

    # 1. Look up the EngineLog by primary key
    log = EngineLog.query.get(log_id)

    # 2. If not found, return 404 with the standard error envelope
    if log is None:
            return jsonify({
                "error": {
                    "code": "NOT_FOUND",
                    "message": "EngineLog not found",
                    "details": {
                        "log_id": log_id
                    }
                }
            }), 404

    # 3. Delete the row and commit the change
    db.session.delete(log)
    db.session.commit()

    # 4. Return 204 No Content to indicate successful deletion
    return "", 204

@main_bp.patch("/engine-logs/<int:log_id>")
@jwt_required
def update_engine_log(log_id: int):
    """
       Partially update and existing EngineLog.

    This endpoint updates one EngineLog row indentified 
    by `log_id`.

    Ownership is not enforced yet; any authenticated user can
    update any eisting EngineLog. A later change will restrict updates 
    to the owner and may tighten which fields are allowed. 

    Request Body:
-    - JSON object with any subset of these fields:
+    - JSON object that includes all of these fields:
         - `from_engine` (string)
         - `to_engine` (string)
         - `payload_id` (string or identifier type used in the app)
+    - All three fields are required, using the same validation rules
+      as the create endpoint.
     - The `user_id` is never acepted from the client and is not
       updatable through this endpoint

    Behavior:
-    - On suggess:
-        - Looks up the EngineLog by `log_id`.
-        - Validates that a JSON body is present.
-        - Validates fields using the same style as the create
-        endpoint (400 VALIDATION_ERROR with per-field messages).
-        - Applies updates only to allowed fields.
-        - Commits the change to the database.
-        - Returns 200 OK with the updated EngineLog in the same 
-        JSON shape as GET-by-ID and POST: `id`, `user_id`, `from_engine`, 
-        `to_engine`, `payload_id`, `created_at`.
+    - On success:
+        - Looks up the EngineLog by `log_id`.
+        - Validates that a JSON body is present.
+        - Validates that `from_engine`, `to_engine`, and `payload_id`
+          are all provided and valid, using the same style as the
+          create endpoint (400 VALIDATION_ERROR with per-field messages).
+        - Applies updates only to those allowed fields.
+        - Commits the change to the database.
+        - Returns 200 OK with the updated EngineLog in the same 
+          JSON shape as GET-by-ID and POST: `id`, `user_id`, `from_engine`, 
+          `to_engine`, `payload_id`, `created_at`.

    - If no EngineLog exists with the given ID:
        - Returns 404 NOT_FOUND with the standard error envelope.
    - If the request body is missing or invalid:
        - Returns 400 VALIDATION_ERROR with the same error shape
        and style as the create endpoint.

    Authentication:
    - Requires a valid JWT in the Authorization header.
    - Uses `@jwt_required` to populate `g.user_id`, but does not
    check ownership yet.
    """
    # 1. Try to find the log by primary key
    log = EngineLog.query.get(log_id)
    
    # 2. If not found, return 404 with JSON error envelope
    if log is None:
        return jsonify({
            "error": {
                "code": "NOT_FOUND",
                "message": "EngineLog not found",
                "details": {
                    "log_id": log_id
                }
            }
        }), 404

    # 3. Read and validate the JSON body (reuse create endpoint style)
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

    # 4. Extract and validate required fields (same rules as create)
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

    # 5. Apply updates and persist them
    log.from_engine = from_engine
    log.to_engine = to_engine
    log.payload_id = payload_id

    db.session.commit()

    # 6. Return the updated EngineLog in the standard shape
    return jsonify({
        "id": log.id,
        "user_id": log.user_id,
        "from_engine": log.from_engine,
        "to_engine": log.to_engine,
        "payload_id": log.payload_id,
        "created_at": log.created_at.isoformat()
    }), 200

   