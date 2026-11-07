
import os


class Config:
    SECRET_KEY = os.environ.get("JWT_SECRET", "dev-placeholder-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-prod")
    JWT_LIFETIME_SECONDS = int(os.environ.get("JWT_LIFETIME_SECONDS", "60"))


class DevelopmentConfig(Config):
    DEBUG = True

    SQLALCHEMY_DATABASE_URI = (
        Config.SQLALCHEMY_DATABASE_URI
        or "sqlite:///" + os.path.abspath("dev.db")
    )


class TestingConfig(Config):
    TESTING = True
    DEBUG = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
