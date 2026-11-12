"""AI 세션 저장소.

현재 구현은 단일 uvicorn 워커 전제의 프로세스 메모리(`MemorySessionStore`)다.
세션 객체에 `ScreenEvidence` 같은 파이썬 객체가 들어 있어 그대로 직렬화되지 않는다.
워커를 늘리기 전에 `SessionStore` 를 Redis/플랫폼 DB 구현으로 교체하고 직렬화 형식을 정한다.
"""

from __future__ import annotations

import time
import uuid
from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional, Protocol

from app.config import settings

if TYPE_CHECKING:
    from app.ai.dialogue import ScreenEvidence


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
    owner: str | None = None
    turns: list[SessionTurn] = field(default_factory=list)
    context_snapshots: list[dict[str, Any]] = field(default_factory=list)
    analysis_history: list[dict[str, Any]] = field(default_factory=list)
    dialogue_evidence: ScreenEvidence | None = None
    dialogue_product_app: str | None = None

    def touch(self) -> None:
        self.updated_at = time.time()

    def add_turn(self, turn: SessionTurn) -> None:
        self.turns.append(turn)
        self.turns = self.turns[-40:]
        self.touch()

    def push_context(self, snapshot: dict[str, Any]) -> None:
        self.context_snapshots.append(snapshot)
        if len(self.context_snapshots) > 20:
            self.context_snapshots = self.context_snapshots[-20:]
        self.touch()

    def push_analysis(self, slot: dict[str, Any], *, max_slots: int = 12) -> None:
        self.analysis_history.append(slot)
        if len(self.analysis_history) > max_slots:
            self.analysis_history = self.analysis_history[-max_slots:]
        self.touch()


class SessionStore(Protocol):
    def get(self, session_id: str) -> AiSession | None: ...
    def put(self, session: AiSession) -> None: ...
    def purge_older_than(self, cutoff: float) -> None: ...


class MemorySessionStore:
    def __init__(self) -> None:
        self.items: dict[str, AiSession] = {}

    def get(self, session_id: str) -> AiSession | None:
        return self.items.get(session_id)

    def put(self, session: AiSession) -> None:
        self.items[session.session_id] = session

    def purge_older_than(self, cutoff: float) -> None:
        for sid in [sid for sid, s in self.items.items() if s.updated_at < cutoff]:
            del self.items[sid]


_backend: SessionStore = MemorySessionStore()


def set_session_store(store: SessionStore) -> None:
    global _backend
    _backend = store
_owner: ContextVar[str | None] = ContextVar("ai_session_owner", default=None)


@contextmanager
def session_owner(owner: str):
    token = _owner.set(owner)
    try:
        yield
    finally:
        _owner.reset(token)


def _ttl() -> float:
    return float(getattr(settings, "ai_session_ttl_seconds", 86400) or 86400)


def _purge_expired() -> None:
    _backend.purge_older_than(time.time() - _ttl())


def get_or_create(session_id: Optional[str]) -> AiSession:
    _purge_expired()
    owner = _owner.get()
    existing = _backend.get(session_id) if session_id else None
    if existing is not None and existing.owner == owner:
        return existing
    # HTTP clients cannot select a session id or acquire another owner's session.
    sid = (session_id if owner is None and existing is None else None) or str(uuid.uuid4())
    now = time.time()
    sess = AiSession(session_id=sid, created_at=now, updated_at=now, owner=owner)
    _backend.put(sess)
    return sess


def session_summary(session: AiSession, max_turns: int = 6) -> str:
    lines = []
    hist = session.analysis_history[-8:]
    if hist:
        lines.append("analysis_history:")
        for i, s in enumerate(hist, start=1):
            scope = (s.get("scope") or {}).get("region_label") or "—"
            lines.append(
                f"  #{i} {s.get('path_id')} n={s.get('n')} scope={scope} caveats={s.get('caveat_ids')}"
            )
    for t in session.turns[-max_turns:]:
        lines.append(f"{t.role}: {t.message[:200]}")
    return "\n".join(lines)
