from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..extensions import db
from ..models import Worker, Project, Assistant, WorkerLog, File
from ..services.worker_service import WorkerService, WorkerServiceError

bp = Blueprint("workers", __name__)


FAKE_USER_ID = 1


@bp.route("/")
def index():
    workers = Worker.query.order_by(Worker.created_at.desc()).all()
    projects = Project.query.order_by(Project.name.asc()).all()
    assistants = Assistant.query.order_by(Assistant.name.asc()).all()
    return render_template("worker.html", workers=workers, projects=projects, assistants=assistants, current=None, logs=None)


@bp.route("/create", methods=["POST"])
def create():
    name = request.form.get('name') or 'Worker'
    project_id = request.form.get('project_id', type=int)
    assistant_id = request.form.get('assistant_id', type=int)
    project = Project.query.get_or_404(project_id)
    assistant = Assistant.query.get(assistant_id) if assistant_id else None
    w = WorkerService.create_worker(FAKE_USER_ID, project.id, name, assistant)
    flash('Worker erstellt', 'success')
    return redirect(url_for('workers.view', worker_id=w.id))


@bp.route("/<int:worker_id>")
def view(worker_id: int):
    worker = Worker.query.get_or_404(worker_id)
    logs = WorkerLog.query.filter_by(worker_id=worker.id).order_by(WorkerLog.created_at.desc()).limit(25).all()
    projects = Project.query.order_by(Project.name.asc()).all()
    assistants = Assistant.query.order_by(Assistant.name.asc()).all()
    # Output Files für alle Logs auflösen (Batch Query)
    import json as _json
    all_ids: set[str] = set()
    for l in logs:
        if l.output_file_ids:
            try:
                ids = _json.loads(l.output_file_ids)
            except Exception:
                ids = []
            if isinstance(ids, list):
                for fid in ids:
                    if fid:
                        all_ids.add(fid)
    file_objs = []
    if all_ids:
        file_objs = File.query.filter(File.openai_file_id.in_(list(all_ids))).all()
    by_openai = {f.openai_file_id: f for f in file_objs}
    # pro Log Liste vorbereiten
    for l in logs:
        l.output_files = []  # type: ignore[attr-defined]
        if l.output_file_ids:
            try:
                ids = _json.loads(l.output_file_ids)
            except Exception:
                ids = []
            if isinstance(ids, list):
                for fid in ids:
                    fo = by_openai.get(fid)
                    if fo:
                        l.output_files.append(fo)  # type: ignore[attr-defined]
    # Aggregierte Output Files (einmalige Liste)
    aggregated_output_files = []
    seen_fids = set()
    for l in logs:
        for fo in getattr(l, 'output_files', []) or []:  # type: ignore[attr-defined]
            if fo.openai_file_id and fo.openai_file_id not in seen_fids:
                aggregated_output_files.append(fo)
                seen_fids.add(fo.openai_file_id)
    return render_template(
        "worker.html",
        workers=[worker],
        current=worker,
        logs=logs,
        projects=projects,
        assistants=assistants,
        aggregated_output_files=aggregated_output_files,
    )


@bp.route("/<int:worker_id>/run", methods=["POST"])
def run(worker_id: int):
    worker = Worker.query.get_or_404(worker_id)
    prompt = request.form.get('prompt')
    try:
        WorkerService.run_once(worker, prompt)
        flash('Run abgeschlossen', 'success')
    except WorkerServiceError as e:
        flash(str(e), 'danger')
    return redirect(url_for('workers.view', worker_id=worker.id))


@bp.route('/<int:worker_id>/delete', methods=['POST'])
def delete(worker_id: int):
    worker = Worker.query.get_or_404(worker_id)
    proj_id = worker.project_id
    db.session.delete(worker)
    db.session.commit()
    flash('Worker gelöscht', 'info')
    # Falls aus Projektansicht gekommen -> zurück zum Projekt
    if proj_id:
        return redirect(url_for('projects.view', project_id=proj_id))
    return redirect(url_for('workers.index'))
