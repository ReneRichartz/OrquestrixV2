import os
from flask import Flask
from .extensions import db, migrate
from sqlalchemy import inspect, text
from dotenv import load_dotenv

# .env vor dem Import der Config laden
load_dotenv()
from .config import Config  # noqa: E402


def create_app(config_class: type = Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    # Falls Config leer war, Environment Key nachtragen
    _k = os.environ.get("OPENAI_API_KEY", "")
    if _k and not app.config.get("OPENAI_API_KEY"):
        app.config["OPENAI_API_KEY"] = _k
    print(f"[Orquestrix] OPENAI_API_KEY {'geladen (len='+str(len(_k))+')' if _k else 'FEHLT'}")

    # Init Extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Frühere Dev-Abkürzung (create_all bei fehlenden Tabellen) entfernt, um Migrationen zu erzwingen.
    # Falls wirklich Initial-Bootstrapping ohne Migrationen gewünscht ist, kann untenstehender Block reaktiviert werden.
    # with app.app_context():
    #     try:
    #         from . import models  # noqa: F401
    #         inspector = inspect(db.engine)
    #         if 'chat' not in inspector.get_table_names():
    #             app.logger.warning("Tabellen fehlen – führe db.create_all() aus (nur DEV)")
    #             db.create_all()
    #         app.logger.info("DB URI aktiv: %s", app.config.get('SQLALCHEMY_DATABASE_URI'))
    #     except Exception as e:
    #         app.logger.error("DB Initialisierungs-Check fehlgeschlagen: %s", e)

    # Register Blueprints
    from .main.routes import bp as main_bp
    from .chats.routes import bp as chats_bp
    from .projects.routes import bp as projects_bp
    from .workers.routes import bp as workers_bp
    from .admin.routes import bp as admin_bp
    from .auth.routes import bp as auth_bp
    from .files.routes import bp as files_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(chats_bp, url_prefix="/chats")
    app.register_blueprint(projects_bp, url_prefix="/projects")
    app.register_blueprint(workers_bp, url_prefix="/workers")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(files_bp, url_prefix="/files")

    # Simple health route
    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
