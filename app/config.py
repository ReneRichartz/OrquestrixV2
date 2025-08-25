import os


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DEFAULT_DB_FILE = os.path.join(INSTANCE_DIR, "orquestrix.db")


class Config:
    APP_NAME = "Orquestrix"
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change")
    # Präferiere absolute Pfadangabe, damit keine zweite leere DB entsteht
    DB_FILE = os.environ.get("DB_FILE", DEFAULT_DB_FILE)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{DB_FILE}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_CHAT_MODEL = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4.5")  # Platzhalter
    OPENAI_WORKER_MODEL = os.environ.get("OPENAI_WORKER_MODEL", "gpt-4.1")  # Platzhalter
    OPENAI_REQUEST_TIMEOUT = int(os.environ.get("OPENAI_REQUEST_TIMEOUT", "60"))  # Sekunden
    OPENAI_POLL_INTERVAL = float(os.environ.get("OPENAI_POLL_INTERVAL", "1.0"))  # Sekunden zwischen Polls
    OPENAI_POLL_TIMEOUT = int(os.environ.get("OPENAI_POLL_TIMEOUT", "120"))      # Max Wartezeit gesamt
