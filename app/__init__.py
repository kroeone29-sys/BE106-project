
"""
Application factory and application-wide configuration.

This module creates and configures the Flask application, initializes
shared extensions, registers application blueprints, and defines
consistent HTTP error responses for request-processing failures.

Application setup is centralized here so development, testing, and
production environments use the same application structure.
"""

import os

from flask import Flask, jsonify
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from .config import DevelopmentConfig, TestingConfig, ProductionConfig
from .extensions import db, migrate
from .main import main_bp, admin_bp
from .auth import auth_bp
from .engine_logs.routes import engine_logs_bp


def create_app():
    """
    Create and configure the Flask application.

    Configuration is selected using the APP_ENV environment variable.
    The application then initializes its extensions, imports its models,
    registers its blueprints, and installs application-wide HTTP error
    handlers.

    Returns:
        Flask: The configured application instance.
    """
    app = Flask(__name__)

    env = os.getenv("APP_ENV", "development")

    if env == "production":
        app.config.from_object(ProductionConfig)
    elif env == "testing":
        app.config.from_object(TestingConfig)
    else:
        app.config.from_object(DevelopmentConfig)

    # Report the selected configuration during application startup.
    print("Selected config:", app.config.get("ENV", env))

    # Initialize extensions with this application instance.
    db.init_app(app)
    migrate.init_app(app, db)

    # Import models so SQLAlchemy and Flask-Migrate can discover them.
    from . import models

    # Register application routes.
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp)
    app.register_blueprint(engine_logs_bp)

    @app.errorhandler(BadRequest)
    def handle_bad_request(error):
        """
        Return a consistent JSON response for HTTP 400 errors.

        This handler covers malformed or missing JSON bodies rejected
        during request parsing.

        Returns:
            tuple: A JSON error response and HTTP 400 status.
        """
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request JSON",
                "details": {
                    "body": [
                        "A valid JSON request body is required."
                    ]
                }
            }
        }), 400

    @app.errorhandler(UnsupportedMediaType)
    def handle_unsupported_media_type(error):
        """
        Return a consistent JSON response for HTTP 415 errors.

        This handler covers requests whose Content-Type does not identify
        a supported JSON request body.

        Returns:
            tuple: A JSON error response and HTTP 415 status.
        """
        return jsonify({
            "error": {
                "code": "UNSUPPORTED_MEDIA_TYPE",
                "message": "Unsupported request media type",
                "details": {
                    "content_type": [
                        "Content-Type must be application/json."
                    ]
                }
            }
        }), 415

    return app

