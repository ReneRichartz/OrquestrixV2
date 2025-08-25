from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from ..models import Assistant, File, ChatRole, Chat
from ..extensions import db
from ..services.assistant_service import AssistantService, AssistantSyncError
from ..services.vector_store_service import VectorStoreService, VectorStoreSyncError
from ..services.file_service import FileService, FileSyncError
from ..services.chat_role_service import ChatRoleService, ChatRoleServiceError
from ..models import VectorStore

bp = Blueprint("admin", __name__)


@bp.route("/")
def index():
    return render_template("admin.html")


# ---------------- Assistants Verwaltung ----------------
@bp.route("/assistants", methods=["GET"])
def assistants_list():
    assistants = Assistant.query.order_by(Assistant.created_at.desc()).all()
    return render_template("admin_assistants.html", assistants=assistants)


@bp.route("/assistants/create", methods=["POST"])
def assistants_create():
    name = request.form.get("name")
    model = request.form.get("model")
    description = request.form.get("description")
    instructions = request.form.get("instructions")
    try:
        AssistantService.create_and_sync(name=name, model=model, description=description, instructions=instructions)
        flash("Assistant erstellt & mit OpenAI synchronisiert", "success")
    except AssistantSyncError as e:
        flash(f"Fehler beim Erstellen: {e}", "error")
    return redirect(url_for("admin.assistants_list"))


@bp.route("/assistants/<int:assistant_id>/delete", methods=["POST"])
def assistants_delete(assistant_id: int):
    a = Assistant.query.get_or_404(assistant_id)
    try:
        AssistantService.delete_remote_and_local(a)
        flash("Assistant gelöscht", "info")
    except AssistantSyncError as e:
        flash(f"Löschen fehlgeschlagen: {e}", "error")
    return redirect(url_for("admin.assistants_list"))


@bp.route("/assistants/sync", methods=["POST"])
def assistants_sync():
    try:
        added, updated = AssistantService.pull_remote()
        flash(f"Sync abgeschlossen (neu: {added}, aktualisiert: {updated})", "success")
    except AssistantSyncError as e:
        flash(f"Sync fehlgeschlagen: {e}", "error")
    return redirect(url_for("admin.assistants_list"))


# ---------------- Vector Stores ----------------
@bp.route("/vectors", methods=["GET"])
def vectors_list():
    vectors = VectorStore.query.order_by(VectorStore.created_at.desc()).all()
    return render_template("admin_vectors.html", vectors=vectors)


@bp.route("/vectors/create", methods=["POST"])
def vectors_create():
    name = request.form.get("name")
    try:
        VectorStoreService.create_and_sync(name=name or "Unnamed Vector")
        flash("Vector Store erstellt", "success")
    except VectorStoreSyncError as e:
        flash(f"Fehler: {e}", "error")
    return redirect(url_for("admin.vectors_list"))


@bp.route("/vectors/sync", methods=["POST"])
def vectors_sync():
    try:
        added, updated = VectorStoreService.pull_remote()
        flash(f"Vector Sync (neu: {added}, aktualisiert: {updated})", "success")
    except VectorStoreSyncError as e:
        flash(f"Sync Fehler: {e}", "error")
    return redirect(url_for("admin.vectors_list"))


@bp.route("/vectors/files-sync", methods=["POST"])
def vectors_files_sync():
    updated_rel, total = VectorStoreService.sync_files_only()
    flash(f"File-Zuordnung Sync: Beziehungen geändert={updated_rel} Vectors={total}", "success")
    return redirect(url_for("admin.files_list"))


@bp.route("/vectors/<int:vector_id>/delete", methods=["POST"])
def vectors_delete(vector_id: int):
    vs = VectorStore.query.get_or_404(vector_id)
    try:
        VectorStoreService.delete_remote_and_local(vs)
        flash("Vector Store gelöscht", "info")
    except VectorStoreSyncError as e:
        flash(f"Löschen Fehler: {e}", "error")
    return redirect(url_for("admin.vectors_list"))


# ---------------- Files ----------------
@bp.route("/files", methods=["GET"])
def files_list():
    # Nur Dateien ohne Zuordnung anzeigen (doppelte Absicherung: Cache + Relation leer)
    files = File.query.filter(
        File.in_vector_store.is_(False),
        ~File.vector_stores.any()
    ).order_by(File.created_at.desc()).all()
    vectors = VectorStore.query.order_by(VectorStore.name.asc()).all()
    return render_template("admin_files.html", files=files, vectors=vectors)


@bp.route("/files/upload", methods=["POST"])
def files_upload():
    up = request.files.get("file")
    if not up or up.filename == "":
        flash("Keine Datei gewählt", "error")
        return redirect(url_for("admin.files_list"))
    # Temporär speichern in instance/uploads
    from pathlib import Path
    upload_dir = Path(current_app.instance_path) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = upload_dir / up.filename
    up.save(tmp_path)
    try:
        FileService.upload_and_create(str(tmp_path))
        flash("Datei hochgeladen", "success")
    except FileSyncError as e:
        flash(f"Upload Fehler: {e}", "error")
    return redirect(url_for("admin.files_list"))


@bp.route("/files/sync", methods=["POST"])
def files_sync():
    try:
        added, updated = FileService.pull_remote()
        flash(f"Files Sync (neu: {added}, aktualisiert: {updated})", "success")
    except FileSyncError as e:
        flash(f"Sync Fehler: {e}", "error")
    return redirect(url_for("admin.files_list"))


@bp.route("/files/<int:file_id>/delete", methods=["POST"])
def files_delete(file_id: int):
    f = File.query.get_or_404(file_id)
    try:
        FileService.delete_remote_and_local(f)
        flash("Datei gelöscht", "info")
    except FileSyncError as e:
        flash(f"Löschen Fehler: {e}", "error")
    return redirect(url_for("admin.files_list"))


@bp.route("/files/attach", methods=["POST"])
def files_attach():
    file_id = request.form.get("file_id", type=int)
    vector_id = request.form.get("vector_store_id", type=int)
    if not file_id or not vector_id:
        flash("ID fehlt", "error")
        return redirect(url_for("admin.files_list"))
    f = File.query.get_or_404(file_id)
    vs = VectorStore.query.get_or_404(vector_id)
    try:
        FileService.attach_file_to_vector_store(f, vs)
        flash("Datei an Vector Store angehängt (ingestion gestartet)", "success")
    except FileSyncError as e:
        flash(f"Attach Fehler: {e}", "error")
    return redirect(url_for("admin.files_list"))


@bp.route("/files/detach", methods=["POST"])
def files_detach():
    file_id = request.form.get("file_id", type=int)
    vector_id = request.form.get("vector_store_id", type=int)
    if not file_id or not vector_id:
        flash("ID fehlt", "error")
        return redirect(url_for("admin.files_list"))
    f = File.query.get_or_404(file_id)
    vs = VectorStore.query.get_or_404(vector_id)
    try:
        FileService.detach_file_from_vector_store(f, vs)
        flash("Zuordnung entfernt", "info")
    except FileSyncError as e:
        flash(f"Detach Fehler: {e}", "error")
    return redirect(url_for("admin.files_list"))


# ---------------- Chat Roles ----------------
@bp.route("/chat-roles", methods=["GET"])
def chat_roles_list():
    roles = ChatRole.query.order_by(ChatRole.name.asc()).all()
    return render_template("admin_chat_roles.html", roles=roles, edit_role=None)


@bp.route("/chat-roles/create", methods=["POST"])
def chat_roles_create():
    name = request.form.get('name')
    instructions = request.form.get('instructions')
    model = request.form.get('model')
    temperature = request.form.get('temperature', type=float)
    allowed_models = {'o3-pro','o4-mini','o3-mini'}
    if model and model not in allowed_models:
        flash('Ungültiges Modell', 'error')
        return redirect(url_for('admin.chat_roles_list'))
    try:
        ChatRoleService.create(
            name=name,
            instructions=instructions,
            model=model,
            temperature=temperature,
        )
        flash("Chat Rolle erstellt", "success")
    except ChatRoleServiceError as e:
        flash(str(e), "error")
    return redirect(url_for('admin.chat_roles_list'))

@bp.route('/chat-roles/<int:role_id>/edit', methods=['GET'])
def chat_roles_edit(role_id: int):
    roles = ChatRole.query.order_by(ChatRole.name.asc()).all()
    edit_role = ChatRole.query.get_or_404(role_id)
    return render_template('admin_chat_roles.html', roles=roles, edit_role=edit_role)

@bp.route('/chat-roles/<int:role_id>/update', methods=['POST'])
def chat_roles_update(role_id: int):
    role = ChatRole.query.get_or_404(role_id)
    name = request.form.get('name')
    model = request.form.get('model')
    instructions = request.form.get('instructions')
    temperature = request.form.get('temperature', type=float)
    if not name or not instructions:
        flash('Name und Instructions sind Pflicht', 'error')
        return redirect(url_for('admin.chat_roles_edit', role_id=role.id))
    allowed_models = {'o3-pro', 'o4-mini', 'o3-mini'}
    if model and model not in allowed_models:
        flash('Ungültiges Modell', 'error')
        return redirect(url_for('admin.chat_roles_edit', role_id=role.id))
    try:
        ChatRoleService.update(
            role,
            name=name.strip(),
            model=model or role.model,
            instructions=instructions,
            temperature=temperature,
        )
        flash('Rolle aktualisiert', 'success')
    except ChatRoleServiceError as e:  # type: ignore
        flash(str(e), 'error')
        return redirect(url_for('admin.chat_roles_edit', role_id=role.id))
    return redirect(url_for('admin.chat_roles_list'))


@bp.route("/chat-roles/<int:role_id>/delete", methods=["POST"])
def chat_roles_delete(role_id: int):
    role = ChatRole.query.get_or_404(role_id)
    try:
        ChatRoleService.delete(role)
        flash("Rolle gelöscht", "info")
    except Exception as e:  # noqa: BLE001
        flash(f"Löschen Fehler: {e}", "error")
    return redirect(url_for('admin.chat_roles_list'))


@bp.route("/chat-roles/<int:chat_id>/assign", methods=["POST"])
def chat_roles_assign(chat_id: int):
    chat = Chat.query.get_or_404(chat_id)
    role_id = request.form.get('role_id', type=int)
    if not role_id:
        flash("role_id fehlt", "error")
        return redirect(url_for('chats.view', chat_id=chat.id))
    role = ChatRole.query.get_or_404(role_id)
    ChatRoleService.assign_chat_role(chat, role)
    flash("Rolle zugewiesen", "success")
    return redirect(url_for('chats.view', chat_id=chat.id))

