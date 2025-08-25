from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..models import Project, File, WorkerLog, File as OrxFile
from ..extensions import db
# VectorStore / File Ingestion bewusst NICHT automatisch hier – ausgewählte Projektdateien werden als direkte Files übergeben (nicht in Vector Store ingestiert).

bp = Blueprint("projects", __name__)

FAKE_USER_ID = 1


@bp.route("/")
def overview():
    page = request.args.get("page", 1, type=int)
    pagination = Project.query.order_by(Project.created_at.desc()).paginate(page=page, per_page=6)
    return render_template("project_overview.html", pagination=pagination, projects=pagination.items)


@bp.route("/create", methods=["POST"])
def create():
    name = request.form.get("name") or "Neues Projekt"
    desc = request.form.get("description")
    project = Project(name=name, description=desc, user_id=FAKE_USER_ID)
    db.session.add(project)
    db.session.commit()
    flash("Projekt erstellt", "success")
    return redirect(url_for("projects.view", project_id=project.id))


@bp.route("/<int:project_id>")
def view(project_id: int):
    project = Project.query.get_or_404(project_id)
    # Zugeordnete Chats & Worker laden (Sortierung für konsistente Anzeige)
    chats = project.chats.order_by(Project.chats.prop.mapper.class_.created_at.desc()).all() if project.chats else []
    workers = project.workers.order_by(Project.workers.prop.mapper.class_.created_at.desc()).all() if project.workers else []
    # Verfügbare Dateien (nicht in Vector Stores) für explizite Auswahl
    from ..models import File as _File
    q = request.args.get('q', type=str, default='')
    only_selected = request.args.get('only_selected', default='0') == '1'
    # Doppelter Schutz: Cache-Flag + tatsächliche fehlende Relation
    base_query = _File.query.filter(_File.in_vector_store.is_(False), ~_File.vector_stores.any())
    if q:
        like = f"%{q}%"
        base_query = base_query.filter(_File.filename.ilike(like))
    if only_selected:
        sel_ids = [f.id for f in project.files]
        if sel_ids:
            base_query = base_query.filter(_File.id.in_(sel_ids))
        else:
            base_query = base_query.filter(False)
    available_files = base_query.order_by(_File.created_at.desc()).all()
    # Output File Mapping für Worker Logs (limit pro Worker 10)
    import json as _json
    output_ids: set[str] = set()
    for w in workers:
        for log in w.logs.limit(10):  # type: ignore[attr-defined]
            if log.output_file_ids:
                try:
                    ids = _json.loads(log.output_file_ids)
                except Exception:
                    ids = []
                if isinstance(ids, list):
                    for fid in ids:
                        if fid:
                            output_ids.add(fid)
    file_map = {}
    if output_ids:
        file_objs = OrxFile.query.filter(OrxFile.openai_file_id.in_(list(output_ids))).all()
        file_map = {f.openai_file_id: f for f in file_objs if f.openai_file_id}
    return render_template(
        "project.html",
        project=project,
        chats=chats,
        workers=workers,
        available_files=available_files,
        q=q,
        only_selected=only_selected,
        file_map=file_map,
    )


@bp.route('/<int:project_id>/files', methods=['POST'])
def update_files(project_id: int):
    project = Project.query.get_or_404(project_id)
    # Nur Dateien zulassen, die nicht in Vector Stores hängen
    selected_ids = request.form.getlist('file_ids')
    eligible = {f.id: f for f in File.query.filter(File.in_vector_store.is_(False)).all()}
    new_files = []
    for sid in selected_ids:
        try:
            iid = int(sid)
        except ValueError:
            continue
        f = eligible.get(iid)
        if f:
            new_files.append(f)
    # Setzen (altes Clear via Zuweisung)
    project.files = new_files
    db.session.commit()

    flash('Projekt-Dateien aktualisiert', 'success')
    return redirect(url_for('projects.view', project_id=project.id))


@bp.route("/<int:project_id>/delete", methods=["POST"])
def delete(project_id: int):
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash("Projekt gelöscht", "info")
    return redirect(url_for("projects.overview"))
