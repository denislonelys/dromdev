# ============================================================================
# IIStudio — Сессия (контекст диалога + история)
# ============================================================================

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.helpers import read_json, write_json
from utils.logger import logger

SESSIONS_DIR = Path(".iistudio/sessions")


@dataclass
class Message:
    role: str          # "user" / "assistant" / "system"
    content: str
    model_id: Optional[str] = None
    mode: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    latency_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "model_id": self.model_id,
            "mode": self.mode,
            "created_at": self.created_at,
            "latency_ms": self.latency_ms,
        }


class Session:
    """Сессия диалога с историей сообщений."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        mode: str = "text",
        model_id: Optional[str] = None,
    ) -> None:
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.mode = mode
        self.model_id = model_id
        self.messages: List[Message] = []
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.metadata: Dict[str, Any] = {}

    # ── Сообщения ────────────────────────────────────────────────────────────

    def add_user_message(self, content: str) -> Message:
        msg = Message(role="user", content=content, mode=self.mode)
        self.messages.append(msg)
        return msg

    def add_assistant_message(
        self,
        content: str,
        model_id: Optional[str] = None,
        latency_ms: Optional[float] = None,
    ) -> Message:
        msg = Message(
            role="assistant",
            content=content,
            model_id=model_id or self.model_id,
            mode=self.mode,
            latency_ms=latency_ms,
        )
        self.messages.append(msg)
        return msg

    def clear(self) -> None:
        self.messages.clear()
        logger.debug("История сессии {} очищена", self.session_id)

    @property
    def history(self) -> List[Dict[str, Any]]:
        return [m.to_dict() for m in self.messages]

    @property
    def last_user_message(self) -> Optional[str]:
        for msg in reversed(self.messages):
            if msg.role == "user":
                return msg.content
        return None

    @property
    def last_assistant_message(self) -> Optional[str]:
        for msg in reversed(self.messages):
            if msg.role == "assistant":
                return msg.content
        return None

    @property
    def message_count(self) -> int:
        return len(self.messages)

    # ── Персистентность ───────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "mode": self.mode,
            "model_id": self.model_id,
            "created_at": self.created_at,
            "messages": self.history,
            "metadata": self.metadata,
        }

    def save(self, directory: Path = SESSIONS_DIR) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.session_id}.json"
        write_json(path, self.to_dict())
        logger.debug("Сессия {} сохранена в {}", self.session_id, path)
        return path

    @classmethod
    def load(cls, session_id: str, directory: Path = SESSIONS_DIR) -> Optional["Session"]:
        path = directory / f"{session_id}.json"
        data = read_json(path)
        if not data:
            return None
        session = cls(
            session_id=data["session_id"],
            mode=data.get("mode", "text"),
            model_id=data.get("model_id"),
        )
        session.created_at = data.get("created_at", session.created_at)
        session.metadata = data.get("metadata", {})
        for m in data.get("messages", []):
            msg = Message(
                role=m["role"],
                content=m["content"],
                model_id=m.get("model_id"),
                mode=m.get("mode"),
                created_at=m.get("created_at", ""),
                latency_ms=m.get("latency_ms"),
            )
            session.messages.append(msg)
        logger.debug("Сессия {} загружена ({} сообщений)", session_id, len(session.messages))
        return session

    @classmethod
    def list_sessions(cls, directory: Path = SESSIONS_DIR) -> List[Dict[str, Any]]:
        if not directory.exists():
            return []
        result = []
        for path in sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            data = read_json(path)
            if data:
                result.append({
                    "session_id": data.get("session_id"),
                    "mode": data.get("mode"),
                    "model_id": data.get("model_id"),
                    "created_at": data.get("created_at"),
                    "message_count": len(data.get("messages", [])),
                })
        return result
