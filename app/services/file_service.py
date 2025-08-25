from __future__ import annotations
from typing import Tuple
import os
from flask import current_app
from ..extensions import db
from ..models import File, VectorStore
from .openai_client import get_openai_client


class FileSyncError(Exception):
    pass


class FileService:
    @staticmethod
    def upload_and_create(local_path: str, purpose: str = "assistants") -> File:
        if not os.path.isfile(local_path):
            raise FileSyncError("Datei existiert nicht")
        client = get_openai_client()
        try:
            remote = client.upload_file(local_path, purpose=purpose)
        except Exception as e:  # noqa: BLE001
            raise FileSyncError(f"Upload Fehler: {e}") from e
        f = File(
            openai_file_id=remote.get('id'),
            filename=os.path.basename(local_path),
            purpose=purpose,
            size_bytes=remote.get('bytes'),
        )
        db.session.add(f)
        db.session.commit()
        return f

    @staticmethod
    def pull_remote(purpose: str | None = None) -> Tuple[int, int]:
        client = get_openai_client()
        try:
            remote_files = client.list_files(purpose=purpose)
        except Exception as e:  # noqa: BLE001
            raise FileSyncError(f"Remote List Fehler: {e}") from e
        added = 0
        updated = 0
        for item in remote_files:
            rid = item.get('id')
            if not rid:
                continue
            existing = File.query.filter_by(openai_file_id=rid).first()
            if existing:
                new_name = item.get('filename') or existing.filename
                if existing.filename != new_name:
                    existing.filename = new_name
                    existing.size_bytes = item.get('bytes') or existing.size_bytes
                    updated += 1
            else:
                nf = File(
                    openai_file_id=rid,
                    filename=item.get('filename') or 'unnamed',
                    purpose=item.get('purpose') or 'assistants',
                    size_bytes=item.get('bytes'),
                )
                db.session.add(nf)
                added += 1
        db.session.commit()
        return added, updated

    @staticmethod
    def delete_remote_and_local(file_obj: File) -> None:
        client = get_openai_client()
        if file_obj.openai_file_id:
            try:
                client.delete_file(file_obj.openai_file_id)
            except Exception as e:  # noqa: BLE001
                raise FileSyncError(f"Remote Delete Fehler: {e}") from e
        db.session.delete(file_obj)
        db.session.commit()

    @staticmethod
    def attach_file_to_vector_store(file_obj: File, vector_store: VectorStore) -> dict:
        if not vector_store.openai_vector_store_id:
            raise FileSyncError("Vector Store hat keine remote ID")
        if not file_obj.openai_file_id:
            raise FileSyncError("File hat keine remote ID")
        client = get_openai_client()
        try:
            res = client.add_file_to_vector_store(vector_store.openai_vector_store_id, file_obj.openai_file_id)
        except Exception as e:  # noqa: BLE001
            raise FileSyncError(f"Attach Fehler: {e}") from e
        # Lokale Beziehung pflegen
        if file_obj not in vector_store.files:
            vector_store.files.append(file_obj)
            # Cache Felder aktualisieren
            file_obj.in_vector_store = True
            import json as _json
            ids = {vs.openai_vector_store_id for vs in file_obj.vector_stores if vs.openai_vector_store_id}
            file_obj.vector_store_ids_cache = _json.dumps(sorted(ids)) if ids else None
            db.session.commit()
        return res

    @staticmethod
    def detach_file_from_vector_store(file_obj: File, vector_store: VectorStore) -> None:
        """Entfernt lokale Zuordnung File <-> VectorStore (kein Remote Delete der Datei)."""
        if file_obj in vector_store.files:
            vector_store.files.remove(file_obj)
            # Cache neu berechnen
            import json as _json
            if file_obj.vector_stores:
                ids = {vs.openai_vector_store_id for vs in file_obj.vector_stores if vs.openai_vector_store_id}
                file_obj.in_vector_store = bool(ids)
                file_obj.vector_store_ids_cache = _json.dumps(sorted(ids)) if ids else None
            else:
                file_obj.in_vector_store = False
                file_obj.vector_store_ids_cache = None
            db.session.commit()
