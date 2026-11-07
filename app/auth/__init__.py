import jwt

from flask import Blueprint, jsonify, request, g, current_app

auth_bp = Blueprint("auth", __name__)

def jwt_required(fn):
    def wrapper(*args, **kwargs):
        # placeholder for now - real auth logic coming next
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing_or_malformed_token"}), 401

        token = auth_header.removeprefix("Bearer ").strip()
        try:
            payload = jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token_expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "invalid_token"}), 401

        g.user_id = int(payload["sub"])
        return fn(*args, **kwargs)
    return wrapper

@auth_bp.get("/verify")
@jwt_required
def verify():
    return jsonify({"ok": True}), 200
