import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_API_BASE_URL = os.getenv("OPENAI_API_BASE_URL")
    MODEL_NAME = os.getenv("MODEL_NAME")
    TEMPERATURE = os.getenv("TEMPERATURE")
    MYSQL_URI = os.getenv("MYSQL_URI")
    ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "[*]")
    AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
    AZURE_DEPLOYMENT = os.getenv("AZURE_DEPLOYMENT")
    AZURE_OPENAI_BASE_URL = os.getenv("AZURE_OPENAI_BASE_URL")
    LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2")
    LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")

    DEBUG = False
    TESTING = False


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    DEBUG = True
    TESTING = True


def get_config():
    env = os.getenv("ENV", "dev")
    if env == "prod":
        return Config()
    elif env == "test":
        return TestingConfig()
    else:
        return DevelopmentConfig()
