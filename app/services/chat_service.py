from typing import List, Dict, Any
from flask import current_app
from ..extensions import db
from ..models import Chat, Message, ChatRole
from .openai_client import get_openai_client


class ChatService:
    @staticmethod
    def create_chat(user_id: int, title: str, objective: str | None = None, model: str | None = None, project_id: int | None = None) -> Chat:
        chat = Chat(
            user_id=user_id,
            title=title,
            objective=objective,
            model=model or current_app.config.get("OPENAI_CHAT_MODEL"),
            project_id=project_id,
        )
        db.session.add(chat)
        db.session.flush()
        # Projekt-Dateien (nicht in Vector Stores) automatisch anhängen
        if project_id:
            from ..models import Project as _Proj, File as _File
            proj = _Proj.query.get(project_id)
            if proj:
                for f in proj.files:
                    # Nur Dateien ohne Zugehörigkeit zu einem Vector Store
                    if not f.vector_stores:
                        chat.files.append(f)
        db.session.commit()
        return chat

    @staticmethod
    def add_message(chat_id: int, role: str, content: str, openai_response_id: str | None = None) -> Message:
        msg = Message(chat_id=chat_id, role=role, content=content, openai_response_id=openai_response_id)
        db.session.add(msg)
        db.session.commit()
        return msg

    @staticmethod
    def generate_assistant_reply(chat: Chat) -> Message:
        # Ordnung nach Nachrichten-Zeitstempel (nicht Chat.created_at, sonst fehlt Tabelle im Query Context)
        from ..models import Message as _Msg  # lokale Import-Vermeidung zyklischer Probleme
        messages = [
            {"role": m.role, "content": m.content}
            for m in chat.messages.order_by(_Msg.created_at.asc()).all()
        ]
        client = get_openai_client()
        role: ChatRole | None = getattr(chat, 'chat_role', None)
        instructions = (role.instructions if role else None) or chat.objective or ""
        model = role.model if role else chat.model

        # Projekt-Dateien ohne Vector Stores zusätzlich berücksichtigen
        proj_file_ids: list[str] = []
        if chat.project:
            for f in chat.project.files:
                if not f.vector_stores and f.openai_file_id:
                    proj_file_ids.append(f.openai_file_id)

        # VectorStores: nur explizit dem Chat zugewiesene (kein automatischer Projekt-Fallback)
        vector_store_ids = [vs.openai_vector_store_id for vs in chat.vector_stores if vs.openai_vector_store_id]

        file_ids_final = [f.openai_file_id for f in chat.files if f.openai_file_id] + proj_file_ids
        response = client.create_chat_response(
            instructions=instructions,
            model=model,
            messages=messages,
            max_output_tokens=chat.max_output_tokens,
            vector_store_ids=vector_store_ids,
            file_ids=file_ids_final,
        )
        output_text = ChatService._extract_text_from_response(response)
        if not output_text or output_text.startswith('(Keine Antwort'):
            current_app.logger.warning(
                "[ChatService] Leere oder fehlende Antwort extrahiert response_id=%s raw_keys=%s",
                response.get('id'), list(response.keys())
            )
        # Protokoll-Anhang: verwendete Ressourcen aufführen
        try:
            res_suffix_lines = ["", "---", "Verwendete Ressourcen:"]
            if vector_store_ids:
                res_suffix_lines.append(f"VectorStores: {', '.join(vector_store_ids)}")
            else:
                res_suffix_lines.append("VectorStores: -")
            if file_ids_final:
                res_suffix_lines.append(f"Files: {', '.join(file_ids_final)}")
            else:
                res_suffix_lines.append("Files: -")
            output_text = output_text.rstrip() + "\n" + "\n".join(res_suffix_lines)
        except Exception as _e:  # noqa: BLE001
            current_app.logger.debug('[ChatService] Ressourcen-Anhang Fehler %s', _e)
        return ChatService.add_message(chat.id, "assistant", output_text, openai_response_id=response.get("id"))

    @staticmethod
    def _extract_text_from_response(response: Dict[str, Any]) -> str:
        """
        Robuste Extraktion von Text aus einer OpenAI Responses API Antwort.

        Unterstützte Muster (Beispiele):
        {
          "output": [
             {"type":"message", "content":[{"type":"output_text","text":"Hallo"}]}
          ]
        }

        oder vereinfachte Felder wie 'output_text', 'text', 'content'.

        Fehlerbehandlung: Falls ein 'error' Feld existiert, wird dessen Inhalt priorisiert
        als Fehlermeldung zurückgegeben.
        """

        # 1. Fehler explizit priorisieren
        err = response.get('error')
        if err:
            if isinstance(err, dict):
                # Häufige Felder: message, code, type
                msg = err.get('message') or err.get('error') or str(err)
                code = err.get('code') or err.get('status')
                etype = err.get('type')
                details = []
                if code:
                    details.append(f"code={code}")
                if etype:
                    details.append(f"type={etype}")
                suffix = f" ({', '.join(details)})" if details else ""
                return f"Fehler: {msg}{suffix}"
            if isinstance(err, str):
                return f"Fehler: {err}"

        collected: List[str] = []

        def collect_from_obj(obj: Any):
            # Rekursiver Sammler für verschiedene Strukturvarianten
            if obj is None:
                return
            if isinstance(obj, str):
                s = obj.strip()
                if s:
                    collected.append(s)
                return
            if isinstance(obj, dict):
                # Spezifische Keys bevorzugt
                if 'text' in obj and isinstance(obj['text'], str):
                    t = obj['text'].strip()
                    if t:
                        collected.append(t)
                # Manchmal liegt der Text in obj['content'] als str
                if 'content' in obj and isinstance(obj['content'], str):
                    t2 = obj['content'].strip()
                    if t2:
                        collected.append(t2)
                # Rekursiv über alle Werte (falls verschachtelt)
                for v in obj.values():
                    if isinstance(v, (dict, list)):
                        collect_from_obj(v)
                return
            if isinstance(obj, list):
                for item in obj:
                    collect_from_obj(item)
                return

        # 2. Output Feld rekursiv durchsuchen
        if 'output' in response:
            collect_from_obj(response.get('output'))
            if collected:
                # Duplikate in Reihenfolge entfernen
                seen = set()
                unique = []
                for t in collected:
                    if t not in seen:
                        seen.add(t)
                        unique.append(t)
                return '\n'.join(unique)

        # 3. Fallback einzelne Felder direkt
        for key in ("output_text", "text", "content", "message"):
            v = response.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()

        return "(Keine Antwort erhalten)"
