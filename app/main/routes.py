from flask import Blueprint, render_template, jsonify, current_app
from ..services.openai_client import get_openai_client
from ..models import Chat, Project

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    last_chats = Chat.query.order_by(Chat.created_at.desc()).limit(4).all()
    last_projects = Project.query.order_by(Project.created_at.desc()).limit(4).all()
    return render_template("main.html", last_chats=last_chats, last_projects=last_projects)


@bp.get("/openai/health")
def openai_health():
    try:
        client = get_openai_client()
        models = client.list_models()
        # Prüfen ob erwartete Modelle konfiguriert sind
        expected_chat = current_app.config.get("OPENAI_CHAT_MODEL")
        expected_worker = current_app.config.get("OPENAI_WORKER_MODEL")
        return jsonify({
            "sdk": "python-openai",
            "chat_model_configured": expected_chat,
            "worker_model_configured": expected_worker,
            "models_sample": models[:10],
            "ok": True
        })
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 500
