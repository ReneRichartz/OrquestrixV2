from __future__ import annotations
from typing import Optional
from flask import current_app
import time
from ..extensions import db
from ..models import Worker, WorkerLog, Assistant
from .openai_client import get_openai_client
from ..models import File as OrxFile


class WorkerServiceError(Exception):
    pass


class WorkerService:
    @staticmethod
    def create_worker(user_id: int, project_id: int, name: str, assistant: Optional[Assistant] = None, model: str | None = None) -> Worker:
        w = Worker(name=name, user_id=user_id, project_id=project_id, assistant=assistant, model=model or (assistant.model if assistant else None))
        db.session.add(w)
        db.session.commit()
        return w

    @staticmethod
    def run_once(worker: Worker, prompt: str) -> WorkerLog:
        """Ausführen eines einzelnen Thread-Runs gemäß README (Threads API).

        Schritte:
        1. Thread anlegen falls noch keiner existiert.
        2. Message (user) in Thread posten.
        3. Run starten mit assistant + tool_resources (1 VectorStore, n Files).
        4. Polling bis status terminal (completed/failed/cancelled) oder Timeout.
        5. Messages abrufen und letzten Assistant-Output extrahieren.
        6. Log persistieren inkl. Status & erzeugte File IDs (Code Interpreter Outputs).
        """
        if not prompt:
            raise WorkerServiceError("Prompt fehlt")
        client_wrapper = get_openai_client()
        client = client_wrapper.raw
        poll_interval = current_app.config.get('OPENAI_POLL_INTERVAL', 1.0)
        poll_timeout = current_app.config.get('OPENAI_POLL_TIMEOUT', 180)

        # 1. Thread sicherstellen / tool_resources aufbauen
        # Projekt-Dateien (nicht in VectorStores) + Worker-Dateien kombinieren
        project_file_ids = []
        if worker.project:
            for pf in worker.project.files:
                if not pf.vector_stores and pf.openai_file_id:
                    project_file_ids.append(pf.openai_file_id)
        worker_file_ids = [f.openai_file_id for f in worker.files if f.openai_file_id]
        combined = []
        seen = set()
        for fid in worker_file_ids + project_file_ids:
            if fid and fid not in seen:
                combined.append(fid)
                seen.add(fid)
        file_ids = combined[:20]

        # Genau ein VectorStore optional (nur wenn Worker selber einen hat)
        vector_store_id = None
        for vs in worker.vector_stores:
            if vs.openai_vector_store_id:
                vector_store_id = vs.openai_vector_store_id
                break

        tool_resources = {}
        if file_ids:
            tool_resources['code_interpreter'] = {'file_ids': file_ids}
        if vector_store_id:
            tool_resources['file_search'] = {'vector_store_ids': [vector_store_id]}

        if not worker.openai_thread_id:
            current_app.logger.info('[WorkerService] thread.create worker=%s tool_resources=%s', worker.id, tool_resources)
            thr = client.beta.threads.create(tool_resources=tool_resources if tool_resources else None)
            worker.openai_thread_id = getattr(thr, 'id', None)
            db.session.commit()
        else:
            # Bei vorhandenem Thread: Anhängen der user message geschieht später; Files können nicht direkt am Thread verändert werden ohne neuen Run.
            current_app.logger.debug('[WorkerService] reuse thread=%s worker=%s', worker.openai_thread_id, worker.id)

        thread_id = worker.openai_thread_id
        if not thread_id:
            raise WorkerServiceError('Thread Erstellung fehlgeschlagen')

        # 2. User Message hinzufügen
        current_app.logger.info('[WorkerService] threads.messages.create thread=%s', thread_id)
        client.beta.threads.messages.create(thread_id=thread_id, role='user', content=prompt)

        # Snapshot assistants_output Files vor dem Run (Heuristik für Fälle ohne direkte Referenzen)
        pre_output_file_ids: set[str] = set()
        try:
            pre_files = client_wrapper.list_files(purpose='assistants_output')  # type: ignore[attr-defined]
            for it in pre_files:
                rid = it.get('id') if isinstance(it, dict) else None
                if rid:
                    pre_output_file_ids.add(rid)
        except Exception:
            pass

        # 3. Run starten
        assistant_id = worker.assistant.openai_assistant_id if worker.assistant and worker.assistant.openai_assistant_id else None
        if not assistant_id:
            raise WorkerServiceError('Assistant ID fehlt für Worker')
        current_app.logger.info('[WorkerService] threads.runs.create thread=%s assistant=%s', thread_id, assistant_id)
        run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id, model=worker.model or worker.assistant.model)
        run_id = getattr(run, 'id', None)
        status = getattr(run, 'status', None)
        start_ts = time.time()
        # 4. Polling Run Status
        while status not in ('completed', 'failed', 'cancelled') and (time.time() - start_ts) < poll_timeout:
            time.sleep(poll_interval)
            run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
            status = getattr(run, 'status', None)
            current_app.logger.debug('[WorkerService] run poll thread=%s run=%s status=%s', thread_id, run_id, status)

        # Optional nach Abschluss: Steps bis alle completed (kleines Zusatzfenster)
        if status == 'completed':
            steps_poll_timeout = current_app.config.get('OPENAI_STEPS_POLL_TIMEOUT', 15)
            steps_poll_interval = min(poll_interval, 2.0)
            steps_start = time.time()
            def _all_steps_terminal(steps_obj) -> bool:
                data = getattr(steps_obj, 'data', [])
                for s in data:
                    st_status = getattr(s, 'status', None)
                    if st_status not in ('completed', 'failed', 'cancelled'):
                        return False
                return True if data else True
            try:
                while (time.time() - steps_start) < steps_poll_timeout:
                    steps_obj = client.beta.threads.runs.steps.list(thread_id=thread_id, run_id=run_id, limit=50)
                    if _all_steps_terminal(steps_obj):
                        break
                    time.sleep(steps_poll_interval)
            except Exception as e:  # noqa: BLE001
                current_app.logger.debug('[WorkerService] steps terminal polling skipped err=%s', e)

        # 5. Messages lesen
        output_text = ''
        output_file_ids: list[str] = []
        try:
            msgs = client.beta.threads.messages.list(thread_id=thread_id, order='desc', limit=50)
            data = getattr(msgs, 'data', [])
            for m in data:
                role = getattr(m, 'role', None)
                if role == 'assistant':
                    # Attachments (Experiment / Debug) ausgeben und nach File-IDs durchsuchen
                    try:
                        attachments = getattr(m, 'attachments', None)
                        if attachments:
                            current_app.logger.info('[WorkerService] message.id=%s attachments count=%s', getattr(m, 'id', None), len(attachments))
                            for idx, att in enumerate(attachments):
                                # In Dict umwandeln für Logging
                                if hasattr(att, 'to_dict'):
                                    try:
                                        att_dict = att.to_dict()  # type: ignore
                                    except Exception:  # noqa: BLE001
                                        att_dict = {}
                                elif isinstance(att, dict):
                                    att_dict = att
                                else:
                                    # generischer Fallback
                                    att_dict = {k: getattr(att, k) for k in dir(att) if not k.startswith('_') and k not in ('__class__',)}
                                current_app.logger.info('[WorkerService] attachment %s: %s', idx, att_dict)
                                # Mögliche File-ID Keys sammeln
                                for key in ('file_id', 'id', 'openai_file_id'):
                                    fid_candidate = att_dict.get(key)
                                    if isinstance(fid_candidate, str) and fid_candidate and fid_candidate not in output_file_ids:
                                        output_file_ids.append(fid_candidate)
                    except Exception as _e:  # noqa: BLE001
                        current_app.logger.debug('[WorkerService] attachments logging error %s', _e)
                    # content kann Liste sein
                    content_list = getattr(m, 'content', [])
                    parts = []
                    for c in content_list:
                        ctype = getattr(c, 'type', None)
                        if ctype == 'output_text':
                            txt = getattr(c, 'text', None)
                            if txt and getattr(txt, 'value', None):
                                parts.append(txt.value)
                        elif ctype == 'text':  # fallback older
                            txt_obj = getattr(c, 'text', None)
                            if txt_obj and getattr(txt_obj, 'value', None):
                                parts.append(txt_obj.value)
                        elif ctype == 'file_path':
                            fp = getattr(c, 'file_path', None)
                            if fp and getattr(fp, 'file_id', None):
                                output_file_ids.append(fp.file_id)
                    if parts and not output_text:
                        output_text = '\n'.join(parts)
        except Exception as e:  # noqa: BLE001
            current_app.logger.warning('[WorkerService] messages parsing error thread=%s err=%s', thread_id, e)

        if not output_text:
            output_text = '(Keine Antwort erhalten)'

        # Run Steps durchsuchen (immer – kann zusätzliche Files liefern)
        try:
            steps = client.beta.threads.runs.steps.list(thread_id=thread_id, run_id=run_id, limit=50)
            sdata = getattr(steps, 'data', [])
            extracted: set[str] = set(output_file_ids)

            def _collect(obj):  # rekursive Suche nach Keys 'file_id'
                if obj is None:
                    return
                # Objekt mit Attributen
                if hasattr(obj, 'file_id'):
                    fidv = getattr(obj, 'file_id', None)
                    if isinstance(fidv, str) and fidv:
                        extracted.add(fidv)
                # to_dict -> dict
                if hasattr(obj, 'to_dict'):
                    try:
                        d = obj.to_dict()  # type: ignore
                        _collect(d)
                    except Exception:  # noqa: BLE001
                        pass
                elif isinstance(obj, dict):
                    for k, v in list(obj.items()):
                        if k == 'file_id' and isinstance(v, str) and v:
                            extracted.add(v)
                        else:
                            _collect(v)
                elif isinstance(obj, (list, tuple, set)):
                    for it in obj:
                        _collect(it)
                else:
                    # Generischer Attribute-Scan (flach)
                    for attr in ('image', 'output', 'outputs', 'code_interpreter', 'step_details', 'tool_calls', 'content', 'data', 'parts'):
                        if hasattr(obj, attr):
                            _collect(getattr(obj, attr))

            for st in sdata:
                _collect(st)

            if extracted and set(output_file_ids) != extracted:
                output_file_ids = list(extracted)
                current_app.logger.info('[WorkerService] Output File IDs erweitert run=%s ids=%s', run_id, output_file_ids)
        except Exception as e:  # noqa: BLE001
            current_app.logger.debug('[WorkerService] steps parsing error run=%s err=%s', run_id, e)

        # Ressourcen-Protokoll anhängen (VectorStore + Input Files + Output Files)
        try:
            res_lines = ["", "---", "Verwendete Ressourcen:"]
            if vector_store_id:
                res_lines.append(f"VectorStore: {vector_store_id}")
            else:
                res_lines.append("VectorStore: -")
            if file_ids:
                res_lines.append(f"Input Files: {', '.join(file_ids)}")
            else:
                res_lines.append("Input Files: -")
            if output_file_ids:
                res_lines.append(f"Output Files: {', '.join(output_file_ids)}")
            else:
                res_lines.append("Output Files: -")
            output_text = output_text.rstrip() + "\n" + "\n".join(res_lines)
        except Exception as _e:  # noqa: BLE001
            current_app.logger.debug('[WorkerService] Ressourcen-Anhang Fehler %s', _e)

        # Debug Logging der Run Steps (konfigurierbar)
        if current_app.config.get('OPENAI_WORKER_DEBUG_STEPS', False):
            try:
                steps_dbg = client.beta.threads.runs.steps.list(thread_id=thread_id, run_id=run_id, limit=20)
                dbg_data = getattr(steps_dbg, 'data', [])
                preview = []
                for st in dbg_data[:5]:
                    preview.append({
                        'id': getattr(st, 'id', None),
                        'status': getattr(st, 'status', None),
                        'type': getattr(getattr(st, 'step_details', None), 'type', None),
                    })
                current_app.logger.debug('[WorkerService] steps_debug run=%s preview=%s total=%s', run_id, preview, len(dbg_data))
            except Exception as e:  # noqa: BLE001
                current_app.logger.debug('[WorkerService] steps debug logging failed run=%s err=%s', run_id, e)

        # Heuristik: Falls weiterhin keine Output Files gefunden -> diff assistants_output
        if not output_file_ids:
            try:
                post_files = client_wrapper.list_files(purpose='assistants_output')  # type: ignore[attr-defined]
                new_ids = []
                for it in post_files:
                    rid = it.get('id') if isinstance(it, dict) else None
                    if rid and rid not in pre_output_file_ids:
                        # ausschließen falls identisch zu input file ids
                        if rid not in file_ids:
                            new_ids.append(rid)
                if new_ids:
                    output_file_ids = new_ids
                    current_app.logger.info('[WorkerService] Output Files via diff identifiziert run=%s ids=%s', run_id, output_file_ids)
            except Exception as e:  # noqa: BLE001
                current_app.logger.debug('[WorkerService] diff heuristic failed run=%s err=%s', run_id, e)

        # 6. Log speichern
        import json as _json
        log = WorkerLog(
            worker_id=worker.id,
            input_text=prompt,
            output_text=output_text,
            openai_run_id=run_id,
            run_status=status,
            output_file_ids=_json.dumps(output_file_ids) if output_file_ids else None,
        )
        db.session.add(log)
        # Output Files lokal persistieren (falls neu)
        if output_file_ids:
            existing_map = {
                f.openai_file_id: f.id for f in OrxFile.query.filter(OrxFile.openai_file_id.in_(output_file_ids)).all()  # type: ignore[arg-type]
            }
            for fid in output_file_ids:
                if not fid or fid in existing_map:
                    continue
                # Metadaten abrufen
                try:
                    meta = client.files.retrieve(fid) if hasattr(client, 'files') else None  # type: ignore[attr-defined]
                    filename = None
                    size_bytes = None
                    if meta is not None:
                        # meta evtl. Objekt mit Attributen
                        if hasattr(meta, 'to_dict'):
                            mdict = meta.to_dict()  # type: ignore
                        elif isinstance(meta, dict):
                            mdict = meta
                        else:
                            mdict = {k: getattr(meta, k) for k in dir(meta) if not k.startswith('_')}
                        filename = mdict.get('filename') or mdict.get('name') or f'output_{fid[:8]}.txt'
                        size_bytes = mdict.get('bytes') or mdict.get('size')
                    nf = OrxFile(
                        openai_file_id=fid,
                        filename=filename or f'output_{fid[:8]}.txt',
                        purpose='assistants',
                        size_bytes=size_bytes,
                    )
                    db.session.add(nf)
                except Exception as _e:  # noqa: BLE001
                    current_app.logger.warning('[WorkerService] Output File Persist Fehler id=%s err=%s', fid, _e)
        db.session.commit()
        return log
