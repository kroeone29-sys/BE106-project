import os

class Config:
    SECRET_KEY = os.environ.get("JWT_SECRET", "dev-placeholder-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    DEBUG = True

    # Dev fallback: if base class didn't set a DB URI, use local SQLite
    SQLALCHEMY_DATABASE_URI = (
        Config.SQLALCHEMY_DATABASE_URI
        or "sqlite:///dev.db"
    )
class TestingConfig(Config):
    TESTING = True
    DEBUG = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False