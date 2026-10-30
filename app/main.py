from flask import Blueprint, jsonify

main_bp = Blueprint("main", __name__)

@main_bp.route("/ping")
def ping():
    return "OK from blueprint"

@main_bp.route("/health")
def health():
    return jsonify({"status": "ok"}), 200