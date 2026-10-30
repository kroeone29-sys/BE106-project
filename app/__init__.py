import os
from flask import Flask
from .config import DevelopmentConfig, TestingConfig, ProductionConfig
from .main import main_bp

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

    app.register_blueprint(main_bp)
    
    return app