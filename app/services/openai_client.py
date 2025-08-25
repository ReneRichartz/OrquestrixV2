from typing import Optional, List, Dict, Any
from flask import current_app
from openai import OpenAI
import openai as openai_pkg  # für Versionsinfo
import os
import time


class OpenAIClientWrapper:
    """Wrapper kapselt OpenAI Aufrufe (Responses, Threads, Assistants)."""

    def __init__(self, api_key: str):
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY fehlt (nicht in .env gesetzt)")
        try:
            timeout = current_app.config.get('OPENAI_REQUEST_TIMEOUT', 60)
            self._client = OpenAI(api_key=api_key, timeout=timeout)
        except TypeError as e:
            # Workaround für seltenen proxies Param Fehler durch Versions-Mismatch
            if 'proxies' in str(e):
                # Versuch: Neuinstallation/Upgrade Hinweis im Log (nutzt global importiertes current_app)
                current_app.logger.error("OpenAI Client Init Fehler (proxies). Bitte Abhängigkeiten aktualisieren. %s", e)
                raise
            raise

    @property
    def raw(self) -> OpenAI:
        return self._client

    # ---------------------- Chat (Responses API) ----------------------
    def create_chat_response(
        self,
        instructions: str,
        model: str,
        messages: List[Dict[str, Any]],
        max_output_tokens: int = 1024,
        vector_store_ids: Optional[List[str]] = None,
        file_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        # Tools: Nur file_search einbinden, wenn Vector Stores vorhanden (Struktur laut Vorgabe)
        tools: List[Dict[str, Any]] = []
        if vector_store_ids:
            tools.append({
                "type": "file_search",
                "vector_store_ids": vector_store_ids,
            })
        current_app.logger.info(
            "[OpenAI] responses.create model=%s tokens=%s vectors=%s files=%s tools=%s",
            model,
            max_output_tokens,
            vector_store_ids,
            file_ids,
            len(tools),
        )
        # Prompt-Anreicherung als Übergangslösung
        if vector_store_ids or file_ids:
            resource_note = "\n\n[Kontext Ressourcen]\n" + \
                (f"VectorStores: {', '.join(vector_store_ids)}\n" if vector_store_ids else "") + \
                (f"Files: {', '.join(file_ids)}\n" if file_ids else "")
            instructions = (instructions + resource_note) if instructions else resource_note

        kwargs: Dict[str, Any] = dict(
            model=model,
            instructions=instructions or "",
            max_output_tokens=max_output_tokens,
            parallel_tool_calls=True if tools else False,
            input=[
                {"role": m.get("role", "user"), "content": m.get("content")}
                for m in messages
            ],
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        # Detail Logging Payload (ohne evtl. große Inhalte abschneiden)
        try:
            preview_messages = [m.copy() for m in kwargs["input"]]
            for m in preview_messages:
                content = m.get("content")
                if isinstance(content, str) and len(content) > 300:
                    m["content"] = content[:300] + "…(truncated)"
            log_payload = {
                "model": kwargs.get("model"),
                "max_output_tokens": kwargs.get("max_output_tokens"),
                "instructions_len": len(kwargs.get("instructions", "")),
                "messages_count": len(kwargs.get("input", [])),
                "messages_preview": preview_messages,
                "tools": kwargs.get("tools"),
                "tool_choice": kwargs.get("tool_choice"),
                "vector_store_ids": vector_store_ids,
                "file_ids": file_ids,
            }
            current_app.logger.debug("[OpenAI] request_payload=%s", log_payload)
        except Exception as e:  # noqa: BLE001
            current_app.logger.warning("[OpenAI] request logging failed: %s", e)
        timeout = current_app.config.get('OPENAI_REQUEST_TIMEOUT', 60)
        response = self._client.responses.create(timeout=timeout, **kwargs)
        # Polling bis status == 'completed' oder Timeout
        poll_interval = current_app.config.get('OPENAI_POLL_INTERVAL', 1.0)
        poll_timeout = current_app.config.get('OPENAI_POLL_TIMEOUT', 120)
        start_ts = time.time()
        rid = getattr(response, 'id', None) or (response.get('id') if isinstance(response, dict) else None)
        status = getattr(response, 'status', None) or (response.get('status') if isinstance(response, dict) else None)
        while rid and status and status not in ('completed', 'failed', 'cancelled') and (time.time() - start_ts) < poll_timeout:
            time.sleep(poll_interval)
            try:
                polled = self._client.responses.retrieve(rid)
                status = getattr(polled, 'status', None) or (polled.get('status') if isinstance(polled, dict) else None)
                if status:
                    current_app.logger.debug('[OpenAI] poll response id=%s status=%s', rid, status)
                response = polled
            except Exception as e:  # noqa: BLE001
                current_app.logger.warning('[OpenAI] polling error id=%s err=%s', rid, e)
                break
        # Abschluss-Logging
        try:
            rdict = response.to_dict() if hasattr(response, 'to_dict') else response  # type: ignore
            preview = {
                'id': rdict.get('id'),
                'status': rdict.get('status'),
                'model': rdict.get('model'),
                'output_types': [o.get('type') for o in rdict.get('output', [])] if isinstance(rdict.get('output'), list) else None,
                'duration_sec': round(time.time() - start_ts, 2),
            }
            current_app.logger.debug('[OpenAI] response_final=%s', preview)
        except Exception as e:  # noqa: BLE001
            current_app.logger.warning('[OpenAI] final response logging failed: %s', e)
        return response.to_dict() if hasattr(response, 'to_dict') else response  # type: ignore

    def list_models(self) -> List[str]:
        current_app.logger.info("[OpenAI] models.list aufgerufen (python sdk version=%s)", getattr(openai_pkg, '__version__', 'unknown'))
        models = self._client.models.list()
        data = getattr(models, 'data', [])
        ids = [getattr(m, 'id', None) for m in data if getattr(m, 'id', None)]
        return ids

    # ---------------------- Vector Stores ----------------------
    def create_vector_store(self, name: str) -> Dict[str, Any]:
        current_app.logger.info("[OpenAI] vector_stores.create name=%s", name)
        vs = self._client.vector_stores.create(name=name)
        return vs.to_dict() if hasattr(vs, 'to_dict') else vs

    def list_vector_stores(self, limit: int = 100) -> List[Dict[str, Any]]:
        current_app.logger.info("[OpenAI] vector_stores.list limit=%s", limit)
        res = self._client.vector_stores.list(limit=limit)
        data = getattr(res, 'data', [])
        out: List[Dict[str, Any]] = []
        for item in data:
            if hasattr(item, 'to_dict'):
                out.append(item.to_dict())
            else:
                out.append({k: getattr(item, k) for k in dir(item) if not k.startswith('_')})
        return out

    def delete_vector_store(self, openai_id: str) -> bool:
        current_app.logger.info("[OpenAI] vector_stores.delete id=%s", openai_id)
        res = self._client.vector_stores.delete(openai_id)
        # Erwartet deleted true
        if hasattr(res, 'deleted'):
            return getattr(res, 'deleted')  # type: ignore
        if isinstance(res, dict):
            return bool(res.get('deleted'))
        return True

    # ---------------------- Files ----------------------
    def upload_file(self, filepath: str, purpose: str = "assistants") -> Dict[str, Any]:
        current_app.logger.info("[OpenAI] files.upload %s purpose=%s", filepath, purpose)
        with open(filepath, 'rb') as f:
            res = self._client.files.create(file=f, purpose=purpose)
        return res.to_dict() if hasattr(res, 'to_dict') else res

    def list_files(self, purpose: Optional[str] = None) -> List[Dict[str, Any]]:
        current_app.logger.info("[OpenAI] files.list purpose=%s", purpose)
        res = self._client.files.list(purpose=purpose) if purpose else self._client.files.list()
        data = getattr(res, 'data', [])
        out: List[Dict[str, Any]] = []
        for item in data:
            out.append(item.to_dict() if hasattr(item, 'to_dict') else {k: getattr(item, k) for k in dir(item) if not k.startswith('_')})
        return out

    def delete_file(self, file_id: str) -> bool:
        current_app.logger.info("[OpenAI] files.delete id=%s", file_id)
        res = self._client.files.delete(file_id)
        if hasattr(res, 'deleted'):
            return getattr(res, 'deleted')  # type: ignore
        if isinstance(res, dict):
            return bool(res.get('deleted'))
        return True

    # Einzelne File Metadaten abrufen
    def retrieve_file(self, file_id: str) -> dict:
        current_app.logger.info("[OpenAI] files.retrieve id=%s", file_id)
        meta = self._client.files.retrieve(file_id)
        return meta.to_dict() if hasattr(meta, 'to_dict') else meta  # type: ignore

    # File Inhalt laden (Bytes)
    def retrieve_file_content(self, file_id: str) -> bytes:
        current_app.logger.info("[OpenAI] files.content id=%s", file_id)
        try:
            # Neues SDK (>=1.0) liefert streaming Response
            content = self._client.files.content(file_id)
            if hasattr(content, 'read'):
                return content.read()  # type: ignore
            # Manchmal dict mit 'data'
            if isinstance(content, dict) and 'data' in content:
                return content['data']  # type: ignore
            if isinstance(content, (bytes, bytearray)):
                return bytes(content)
        except Exception as e:  # noqa: BLE001
            current_app.logger.debug('[OpenAI] files.content primary failed %s – fallback retrieve_content', e)
        # Fallback ältere Methode
        try:
            return self._client.files.retrieve_content(file_id)  # type: ignore[attr-defined]
        except Exception as e:  # noqa: BLE001
            current_app.logger.error('[OpenAI] file content retrieval failed id=%s err=%s', file_id, e)
            raise

    # Vector Store File Ingestion (Anhängen von Files an VectorStore mit Chunking)
    def add_file_to_vector_store(self, vector_store_id: str, file_id: str) -> Dict[str, Any]:
        current_app.logger.info("[OpenAI] vector_stores.files.create vs=%s file=%s", vector_store_id, file_id)
        # Static chunking laut Spezifikation (max_chunk_size_tokens=800, chunk_overlap_tokens=400)
        res = self._client.vector_stores.files.create(
            vector_store_id=vector_store_id,
            file_id=file_id,
            chunking_strategy={
                "type": "static",
                "static": {
                    "max_chunk_size_tokens": 800,
                    "chunk_overlap_tokens": 400,
                }
            }
        )
        return res.to_dict() if hasattr(res, 'to_dict') else res

    def list_vector_store_files(self, vector_store_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        current_app.logger.info("[OpenAI] vector_stores.files.list vs=%s", vector_store_id)
        res = self._client.vector_stores.files.list(vector_store_id=vector_store_id, limit=limit)
        data = getattr(res, 'data', [])
        out: List[Dict[str, Any]] = []
        for item in data:
            out.append(item.to_dict() if hasattr(item, 'to_dict') else {k: getattr(item, k) for k in dir(item) if not k.startswith('_')})
        return out

    def delete_vector_store_file(self, vector_store_id: str, file_id: str) -> bool:
        current_app.logger.info("[OpenAI] vector_stores.files.delete vs=%s file=%s", vector_store_id, file_id)
        res = self._client.vector_stores.files.delete(vector_store_id=vector_store_id, file_id=file_id)
        if hasattr(res, 'deleted'):
            return getattr(res, 'deleted')  # type: ignore
        if isinstance(res, dict):
            return bool(res.get('deleted'))
        return True


def get_openai_client() -> OpenAIClientWrapper:
    api_key = current_app.config.get("OPENAI_API_KEY", "")
    return OpenAIClientWrapper(api_key=api_key)
