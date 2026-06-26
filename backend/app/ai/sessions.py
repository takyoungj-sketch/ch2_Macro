"""AI 세션 — in-memory MVP (운영 시 Redis 등으로 교체)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import settings


@dataclass
class SessionTurn:
    role: str
    message: str
    route: Optional[str] = None
    bundle_id: Optional[str] = None
    scope_label: Optional[str] = None


@dataclass
class AiSession:
    session_id: str
    created_at: float
    updated_at: float
    turns: list[SessionTurn] = field(default_factory=list)
    context_snapshots: list[dict[str, Any]] = field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = time.time()

    def add_turn(self, turn: SessionTurn) -> None:
        self.turns.append(turn)
        self.touch()

    def push_context(self, snapshot: dict[str, Any]) -> None:
        self.context_snapshots.append(snapshot)
        if len(self.context_snapshots) > 20:
            self.context_snapshots = self.context_snapshots[-20:]
        self.touch()


_store: dict[str, AiSession] = {}


def _ttl() -> float:
    return float(getattr(settings, "ai_session_ttl_seconds", 86400) or 86400)


def _purge_expired() -> None:
    now = time.time()
    ttl = _ttl()
    dead = [sid for sid, s in _store.items() if now - s.updated_at > ttl]
    for sid in dead:
        del _store[sid]


def get_or_create(session_id: Optional[str]) -> AiSession:
    _purge_expired()
    if session_id and session_id in _store:
        return _store[session_id]
    sid = session_id or str(uuid.uuid4())
    now = time.time()
    sess = AiSession(session_id=sid, created_at=now, updated_at=now)
    _store[sid] = sess
    return sess


def session_summary(session: AiSession, max_turns: int = 6) -> str:
    lines = []
    for t in session.turns[-max_turns:]:
        lines.append(f"{t.role}: {t.message[:200]}")
    return "\n".join(lines)
