from typing import Tuple
from flask import current_app
from ..extensions import db
from ..models import Assistant
from .openai_client import get_openai_client


ALLOWED_ASSISTANT_MODELS = [
    "gpt-4.1",
    "gpt-4",
]


class AssistantSyncError(Exception):
    pass


class AssistantService:
    @staticmethod
    def create_and_sync(name: str, model: str, description: str | None = None, instructions: str | None = None) -> Assistant:
        if not name:
            raise AssistantSyncError("Name fehlt")
        if model not in ALLOWED_ASSISTANT_MODELS:
            raise AssistantSyncError(f"Model nicht erlaubt: {model}")
        client_wrapper = get_openai_client()
        client = client_wrapper.raw
        current_app.logger.info("[OpenAI] beta.assistants.create name=%s model=%s", name, model)
        try:
            oa = client.beta.assistants.create(
                name=name,
                description=description or "",
                model=model,
                instructions=instructions or "",
                tools=[{"type": "code_interpreter"}, {"type": "file_search"}],
                response_format="text",
            )
        except Exception as e:  # noqa: BLE001
            raise AssistantSyncError(f"OpenAI Create Fehler: {e}") from e

        assistant = Assistant(
            openai_assistant_id=getattr(oa, "id", None),
            name=name,
            description=description,
            model=model,
            instructions=instructions,
        )
        db.session.add(assistant)
        db.session.commit()
        return assistant

    @staticmethod
    def pull_remote() -> Tuple[int, int]:
        client_wrapper = get_openai_client()
        client = client_wrapper.raw
        current_app.logger.info("[OpenAI] beta.assistants.list pull start")
        try:
            remote_list = client.beta.assistants.list(limit=100)
        except Exception as e:  # noqa: BLE001
            raise AssistantSyncError(f"OpenAI List Fehler: {e}") from e

        added = 0
        updated = 0
        # remote_list.data expected
        data = getattr(remote_list, "data", [])
        for item in data:
            rid = getattr(item, "id", None)
            if not rid:
                continue
            existing = Assistant.query.filter_by(openai_assistant_id=rid).first()
            payload = {
                "name": getattr(item, "name", "Unnamed"),
                "description": getattr(item, "description", None),
                "model": getattr(item, "model", None),
                "instructions": getattr(item, "instructions", None),
            }
            if existing:
                for k, v in payload.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                new_a = Assistant(openai_assistant_id=rid, **payload)
                db.session.add(new_a)
                added += 1
        db.session.commit()
        return added, updated

    @staticmethod
    def delete_remote_and_local(assistant: Assistant) -> None:
        client_wrapper = get_openai_client()
        client = client_wrapper.raw
        current_app.logger.info("[OpenAI] beta.assistants.delete id=%s", assistant.openai_assistant_id)
        if assistant.openai_assistant_id:
            try:
                client.beta.assistants.delete(assistant.openai_assistant_id)
            except Exception as e:  # noqa: BLE001
                raise AssistantSyncError(f"Remote Delete Fehler: {e}") from e
        db.session.delete(assistant)
        db.session.commit()
