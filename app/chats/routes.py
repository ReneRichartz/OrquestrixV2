from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..models import Chat, VectorStore, ChatRole, Project
from ..services.vector_store_service import VectorStoreService
from ..extensions import db
from ..services.chat_service import ChatService

bp = Blueprint("chats", __name__)

FAKE_USER_ID = 1  # V1 Platzhalter (alle Admin)


@bp.route("/")
def overview():
    page = request.args.get("page", 1, type=int)
    pagination = Chat.query.order_by(Chat.created_at.desc()).paginate(page=page, per_page=6)
    return render_template("chat_overview.html", pagination=pagination, chats=pagination.items)


@bp.route("/create", methods=["POST"])
def create():
    title = request.form.get("title") or "Neuer Chat"
    objective = request.form.get("objective")
    project_id = request.form.get('project_id', type=int)
    chat = ChatService.create_chat(FAKE_USER_ID, title, objective, project_id=project_id)
    flash("Chat erstellt", "success")
    return redirect(url_for("chats.view", chat_id=chat.id))


@bp.route("/<int:chat_id>", methods=["GET", "POST"])
def view(chat_id: int):
    chat = Chat.query.get_or_404(chat_id)
    if request.method == "POST":
        if 'message' in request.form:
            user_message = request.form.get("message")
            if user_message:
                ChatService.add_message(chat.id, "user", user_message)
                ChatService.generate_assistant_reply(chat)
                return redirect(url_for("chats.view", chat_id=chat.id))
        elif 'vector_update' in request.form:
            selected = request.form.getlist('vectors')
            ids = [int(x) for x in selected]
            VectorStoreService.set_chat_vector_stores(chat, ids)
            flash("Vector Stores aktualisiert", "success")
            return redirect(url_for("chats.view", chat_id=chat.id))
    all_vectors = VectorStore.query.order_by(VectorStore.name.asc()).all()
    all_projects = Project.query.order_by(Project.created_at.desc()).all()
    chat_roles = ChatRole.query.order_by(ChatRole.name.asc()).all()
    from ..models import Message as _Msg
    return render_template(
        "chat.html",
        chat=chat,
        messages=chat.messages.order_by(_Msg.created_at.asc()).all(),
        all_vectors=all_vectors,
        all_projects=all_projects,
        chat_roles=chat_roles,
    )


@bp.route('/<int:chat_id>/assign_project', methods=['POST'])
def assign_project(chat_id: int):
    chat = Chat.query.get_or_404(chat_id)
    pid = request.form.get('project_id', type=int)
    if pid:
        proj = Project.query.get(pid)
        chat.project = proj
    else:
        chat.project = None
    from ..extensions import db as _db
    _db.session.commit()
    flash('Projektzuordnung aktualisiert', 'success')
    return redirect(url_for('chats.view', chat_id=chat.id))


@bp.route("/<int:chat_id>/delete", methods=["POST"])
def delete(chat_id: int):
    chat = Chat.query.get_or_404(chat_id)
    proj_id = chat.project_id
    db.session.delete(chat)
    db.session.commit()
    flash("Chat gelöscht", "info")
    if proj_id:
        return redirect(url_for('projects.view', project_id=proj_id))
    return redirect(url_for("chats.overview"))
