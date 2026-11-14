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
    #: D-085 기능 표지 {"v":1,"used":[...]} — 이 턴의 답이 쓴 비공개 기능(현재 요청 ∪ 이전 근거).
    #: 재생할 때 feature_filter.replay_allowed 로 거른다. 표지가 없으면 비관리자에게 재생하지 않는다.
    features: Optional[dict] = None


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
    #: D-085 dialogue_evidence 의 기능 표지(만든 요청 ∪ 이어 쓴 이전 근거).
    dialogue_evidence_features: Optional[dict] = None
    dialogue_product_app: str | None = None

    def touch(self) -> None:
        self.updated_at = time.time()

    def add_turn(self, turn: SessionTurn) -> None:
        if turn.features is None:
            turn.features = _make_tag()
        self.turns.append(turn)
        self.turns = self.turns[-40:]
        self.touch()

    def push_context(self, snapshot: dict[str, Any]) -> None:
        _tag(snapshot)
        self.context_snapshots.append(snapshot)
        if len(self.context_snapshots) > 20:
            self.context_snapshots = self.context_snapshots[-20:]
        self.touch()

    def push_analysis(self, slot: dict[str, Any], *, max_slots: int = 12) -> None:
        _tag(slot)
        self.analysis_history.append(slot)
        if len(self.analysis_history) > max_slots:
            self.analysis_history = self.analysis_history[-max_slots:]
        self.touch()


FEATURE_TAG = "_features"


def _make_tag() -> dict:
    from app.ai.feature_filter import make_tag

    return make_tag()


def _tag(item: dict[str, Any]) -> None:
    """표지는 항상 남긴다(쓴 기능이 없으면 used=[]). 표지 없는 항목은 비관리자에게 재생되지 않는다."""
    if isinstance(item, dict):
        from app.ai.feature_filter import make_tag, tag_used

        prior = tag_used(item.get(FEATURE_TAG)) or frozenset()
        item[FEATURE_TAG] = make_tag(prior | set(make_tag()["used"]))


def purge_hidden(session: AiSession) -> None:
    """D-085: 현재 요청자에게 꺼진 기능을 쓴 세션 항목을 지운다(재생·previous 근거·History).
    기능 상태가 묶이지 않은 호출(내부)에서는 건드리지 않는다."""
    from app.ai.feature_filter import replay_allowed, scope_bound

    if not scope_bound():
        return
    session.turns = [t for t in session.turns if replay_allowed(t.features)]
    session.context_snapshots = [
        s for s in session.context_snapshots if isinstance(s, dict) and replay_allowed(s.get(FEATURE_TAG))
    ]
    session.analysis_history = [
        s for s in session.analysis_history if isinstance(s, dict) and replay_allowed(s.get(FEATURE_TAG))
    ]
    if session.dialogue_evidence is not None and not replay_allowed(session.dialogue_evidence_features):
        session.dialogue_evidence = None
        session.dialogue_evidence_features = None


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
        purge_hidden(existing)
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
