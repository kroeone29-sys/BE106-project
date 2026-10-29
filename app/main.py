from flask import Blueprint

main_bp = Blueprint("main", __name__)

@main_bp.route("/ping")
def ping():
    return "OK from blueprint"