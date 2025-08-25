from __future__ import annotations
from typing import Optional
from ..extensions import db
from ..models import ChatRole, Chat


class ChatRoleServiceError(Exception):
    pass


class ChatRoleService:
    @staticmethod
    def create(name: str, instructions: str, description: str | None = None, model: str | None = None,
               active: bool = True, temperature: float | None = None) -> ChatRole:
        if not name or not instructions:
            raise ChatRoleServiceError("Name und Instructions sind Pflicht")
        temp = 0.7 if temperature is None else max(0.0, min(1.0, float(temperature)))
        role = ChatRole(
            name=name.strip(),
            description=description,
            instructions=instructions,
            model=model or 'gpt-4.5',
            active=active,
            temperature=temp,
        )
        db.session.add(role)
        db.session.commit()
        return role

    @staticmethod
    def update(role: ChatRole, **kwargs) -> ChatRole:
        temp = kwargs.pop('temperature', None)
        for k, v in kwargs.items():
            if hasattr(role, k) and v is not None:
                setattr(role, k, v)
        if temp is not None:
            try:
                role.temperature = max(0.0, min(1.0, float(temp)))
            except Exception:  # noqa: BLE001
                pass
        db.session.commit()
        return role

    @staticmethod
    def delete(role: ChatRole) -> None:
        db.session.delete(role)
        db.session.commit()

    @staticmethod
    def assign_chat_role(chat: Chat, role: ChatRole) -> Chat:
        chat.chat_role = role
        # Übernimmt Parameter falls Chat noch default hat
        chat.model = role.model
        db.session.commit()
        return chat
