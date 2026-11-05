import os
from flask import Flask
from .config import DevelopmentConfig, TestingConfig, ProductionConfig
from .main import main_bp
from .extensions import db, migrate

def create_app():
    app = Flask(__name__)

    env = os.getenv("APP_ENV", "development")

    if env == "production":
        app.config.from_object(ProductionConfig)
    elif env == "testing":
        app.config.from_object(TestingConfig)
    else:
        app.config.from_object(DevelopmentConfig)

    # just for proof:
    print("Selected config:", app.config.get("ENV", env))

    # init blueprints, extensions, etc. here later
    db.init_app(app)
    migrate.init_app(app, db)

    from . import models

    app.register_blueprint(main_bp)
    
    return app