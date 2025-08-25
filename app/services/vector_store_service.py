from typing import Tuple
from flask import current_app
from ..extensions import db
from ..models import VectorStore, Chat, File
from .openai_client import get_openai_client


class VectorStoreSyncError(Exception):
    pass


class VectorStoreService:
    @staticmethod
    def create_and_sync(name: str) -> VectorStore:
        if not name:
            raise VectorStoreSyncError("Name fehlt")
        client = get_openai_client()
        try:
            remote = client.create_vector_store(name=name)
        except Exception as e:  # noqa: BLE001
            raise VectorStoreSyncError(f"Remote Create Fehler: {e}") from e
        vs = VectorStore(
            name=name,
            openai_vector_store_id=remote.get('id'),
            description=None,
        )
        db.session.add(vs)
        db.session.commit()
        return vs

    @staticmethod
    def pull_remote(limit: int = 100) -> Tuple[int, int]:
        client = get_openai_client()
        try:
            remote_list = client.list_vector_stores(limit=limit)
        except Exception as e:  # noqa: BLE001
            raise VectorStoreSyncError(f"Remote List Fehler: {e}") from e
        added = 0
        updated = 0
        for item in remote_list:
            rid = item.get('id')
            if not rid:
                continue
            existing = VectorStore.query.filter_by(openai_vector_store_id=rid).first()
            if existing:
                # update name if changed
                new_name = item.get('name') or existing.name
                if existing.name != new_name:
                    existing.name = new_name
                    updated += 1
            else:
                new_vs = VectorStore(openai_vector_store_id=rid, name=item.get('name') or 'Unnamed')
                db.session.add(new_vs)
                added += 1
        db.session.commit()

        # Nach Commit: Files je Vector Store abgleichen (Mapping aktualisiert)
        sync_errors: list[str] = []
        all_vectors = VectorStore.query.filter(VectorStore.openai_vector_store_id.isnot(None)).all()
        # Vorbereitung: Map FileID->Set VectorStore OpenAI IDs
        file_vs_map: dict[str, set[str]] = {}
        for vs in all_vectors:
            try:
                remote_files = client.list_vector_store_files(vs.openai_vector_store_id, limit=100)
            except Exception as e:  # noqa: BLE001
                sync_errors.append(f"VS {vs.id} list files Fehler: {e}")
                continue
            remote_file_ids = {rf.get('file_id') or rf.get('id') for rf in remote_files if rf.get('file_id') or rf.get('id')}
            # Lokale Files mit openai_file_id Index
            local_files_map = {f.openai_file_id: f for f in File.query.filter(File.openai_file_id.in_(remote_file_ids)).all() if f.openai_file_id}
            # Entfernen nicht mehr vorhandener Zuordnungen
            to_remove = [f for f in vs.files if f.openai_file_id and f.openai_file_id not in remote_file_ids]
            for f in to_remove:
                vs.files.remove(f)
            # Hinzufügen fehlender Zuordnungen
            for fid in remote_file_ids:
                lf = local_files_map.get(fid)
                if lf and lf not in vs.files:
                    vs.files.append(lf)
                if lf and lf.openai_file_id:
                    file_vs_map.setdefault(lf.openai_file_id, set()).add(vs.openai_vector_store_id or '')
        # Cache-Felder der Files aktualisieren
        import json as _json
        all_files = File.query.filter(File.openai_file_id.isnot(None)).all()
        for f in all_files:
            fid = f.openai_file_id
            vs_ids = file_vs_map.get(fid, set())
            f.in_vector_store = bool(vs_ids)
            f.vector_store_ids_cache = _json.dumps(sorted([vid for vid in vs_ids if vid])) if vs_ids else None
        if sync_errors:
            from flask import current_app
            for msg in sync_errors:
                current_app.logger.warning('[VectorStoreSync] %s', msg)
        db.session.commit()
        return added, updated

    @staticmethod
    def sync_files_only() -> tuple[int, int]:
        """Synchronisiert ausschließlich die File-Zuordnungen (ohne neue Vector Stores zu ziehen).

        Returns:
            (updated_relations, total_vectors_processed)
        """
        client = get_openai_client()
        from flask import current_app
        from ..models import File  # lokal um Zyklen zu vermeiden
        vectors = VectorStore.query.filter(VectorStore.openai_vector_store_id.isnot(None)).all()
        updated_rel = 0
        file_vs_map: dict[str, set[str]] = {}
        for vs in vectors:
            try:
                remote_files = client.list_vector_store_files(vs.openai_vector_store_id, limit=200)
            except Exception as e:  # noqa: BLE001
                current_app.logger.warning('[VectorStoreSync] files_only list Fehler vs=%s err=%s', vs.id, e)
                continue
            remote_file_ids = {rf.get('file_id') or rf.get('id') for rf in remote_files if rf.get('file_id') or rf.get('id')}
            local_files_map = {f.openai_file_id: f for f in File.query.filter(File.openai_file_id.in_(remote_file_ids)).all() if f.openai_file_id}
            # Entfernen nicht mehr existenter
            for f in list(vs.files):
                if f.openai_file_id and f.openai_file_id not in remote_file_ids:
                    vs.files.remove(f)
                    updated_rel += 1
            # Hinzufügen neuer
            for fid in remote_file_ids:
                lf = local_files_map.get(fid)
                if lf and lf not in vs.files:
                    vs.files.append(lf)
                    updated_rel += 1
                if lf and lf.openai_file_id:
                    file_vs_map.setdefault(lf.openai_file_id, set()).add(vs.openai_vector_store_id or '')
        # Cache aktualisieren
        import json as _json
        all_files = File.query.filter(File.openai_file_id.isnot(None)).all()
        for f in all_files:
            vs_ids = file_vs_map.get(f.openai_file_id, set())
            f.in_vector_store = bool(vs_ids)
            f.vector_store_ids_cache = _json.dumps(sorted([vid for vid in vs_ids if vid])) if vs_ids else None
        db.session.commit()
        return updated_rel, len(vectors)

    @staticmethod
    def delete_remote_and_local(vs: VectorStore) -> None:
        client = get_openai_client()
        if vs.openai_vector_store_id:
            try:
                client.delete_vector_store(vs.openai_vector_store_id)
            except Exception as e:  # noqa: BLE001
                raise VectorStoreSyncError(f"Remote Delete Fehler: {e}") from e
        db.session.delete(vs)
        db.session.commit()

    @staticmethod
    def set_chat_vector_stores(chat: Chat, vector_ids: list[int]) -> None:
        # Clear & reassign
        chat.vector_stores.clear()
        if vector_ids:
            stores = VectorStore.query.filter(VectorStore.id.in_(vector_ids)).all()
            for s in stores:
                chat.vector_stores.append(s)
        db.session.commit()
