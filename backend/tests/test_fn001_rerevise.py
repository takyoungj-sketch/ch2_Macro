"""FN-001 재수정 1. 주소표 출력, 최악 단가, v2 라벨·입력·첨부 상한."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select

from app.ai import allowances as quota
from app.config import Settings, settings
from app.platform import fieldnote_ai_router as route
from app.platform.fieldnote_ai_access import FieldnoteAiAccess
from app.platform.fieldnote_ai_router import AiProxyRequest

_PREFIX = "data:image/jpeg;base64,"


class _Client:
    posts = 0
    payload = None
    content = '{"primary_name":"창고"}'

    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        pass

    async def post(self, *_args, **kwargs):
        type(self).posts += 1
        type(self).payload = kwargs["json"]
        return SimpleNamespace(status_code=200, json=lambda: {
            "model": "gpt-5-mini",
            "usage": {"prompt_tokens": 10, "completion_tokens": 4},
            "choices": [{"message": {"content": type(self).content}, "finish_reason": "stop"}],
        })


def _engine(tmp_path, name):
    engine = create_engine(f"sqlite:///{tmp_path / name}")
    quota.meta.create_all(engine)
    return engine


def _arm(monkeypatch, engine):
    _Client.posts = 0
    _Client.payload = None
    start = datetime(2026, 11, 1, tzinfo=timezone.utc)
    grant = quota.Grant(7, "bundle", start, start + timedelta(days=31))
    monkeypatch.setattr(settings, "openai_api_key", "not-a-real-key")
    monkeypatch.setattr(route.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(
        route,
        "resolve_fieldnote_ai_access",
        lambda *_args, **_kwargs: FieldnoteAiAccess("paid", grant.start, grant.end, None),
    )
    monkeypatch.setattr(quota, "grant_for", lambda *_args, **_kwargs: grant)
    return SimpleNamespace(get_bind=lambda: engine), grant


def _call(db, body, *, feature="photo_analysis_image", kind="short"):
    return asyncio.run(route._proxy_openai(
        body, None, db, kind=kind, user=SimpleNamespace(id=7, role="member"), feature=feature,
    ))


def _no_reservation(engine):
    with engine.connect() as conn:
        assert conn.execute(select(quota.balances)).all() == []
        assert conn.execute(select(quota.jobs)).all() == []


def test_worst_call_default_is_sheet_adjusted():
    assert Settings.model_fields["fieldnote_ai_worst_call_usd"].default == 0.025


def test_output_tokens_are_8000_for_sheet_and_4000_otherwise(tmp_path, monkeypatch):
    engine = _engine(tmp_path, "tokens.db")
    db, _grant = _arm(monkeypatch, engine)
    photo = AiProxyRequest(request_id="photo", messages=[{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": _PREFIX + "YQ=="}},
    ]}])
    _call(db, photo)
    assert _Client.payload["max_completion_tokens"] == 4000
    _Client.content = "정리한 문구"
    write = AiProxyRequest(request_id="write", messages=[{"role": "user", "content": "현장 메모"}])
    _call(db, write, feature="text_writing", kind="long")
    assert _Client.payload["max_completion_tokens"] == 4000
    _Client.content = '{"rows":[{"address":"서울시 중구 1"}]}'
    sheet = AiProxyRequest(request_id="sheet", messages=[{"role": "user", "content": [
        {"type": "text", "text": "주소"},
        {"type": "image_url", "image_url": {"url": _PREFIX + "YQ=="}},
    ]}])
    _call(db, sheet, feature="address_sheet_job", kind="sheet")
    assert _Client.payload["max_completion_tokens"] == 8000
    engine.dispose()


def test_v2_label_and_user_input_boundaries(tmp_path, monkeypatch):
    engine = _engine(tmp_path, "label.db")
    db, _grant = _arm(monkeypatch, engine)
    image = _PREFIX + "YQ=="
    allowed = AiProxyRequest(format=2, mode="short", request_id="label-100", photos=[{"image": image, "order": 1, "label": "가" * 100}])
    _call(db, allowed)
    assert _Client.posts == 1
    over = AiProxyRequest(format=2, mode="short", request_id="label-101", photos=[{"image": image, "order": 1, "label": "가" * 101}])
    with pytest.raises(HTTPException) as denied:
        _call(db, over)
    assert denied.value.status_code == 400 and denied.value.detail["code"] == "invalid_request"
    assert _Client.posts == 1
    note = "가" * 2000
    hints = [{"order": index, "text": "나" * 2000} for index in range(1, 4)]
    exact = AiProxyRequest(format=2, mode="long", request_id="text-8000", note=note, ocr_hints=hints, photos=[{"image": image, "order": 1}])
    _call(db, exact, kind="long")
    assert _Client.posts == 2
    too_long = AiProxyRequest(
        format=2, mode="long", request_id="text-8001", note=note, ocr_hints=hints,
        photos=[{"image": image, "order": 1, "label": "다"}],
    )
    with pytest.raises(HTTPException) as text_denied:
        _call(db, too_long, kind="long")
    assert text_denied.value.detail["code"] == "invalid_request"
    assert _Client.posts == 2
    with engine.connect() as conn:
        keys = {row[0] for row in conn.execute(select(quota.jobs.c.key)).all()}
    assert "label-101" not in keys and "text-8001" not in keys
    engine.dispose()


def test_v2_image_chars_use_the_legacy_cap(tmp_path, monkeypatch):
    engine = _engine(tmp_path, "image.db")
    db, _grant = _arm(monkeypatch, engine)
    exact = _PREFIX + ("A" * (20_000_000 - len(_PREFIX)))
    over = exact + "B"
    with pytest.raises(HTTPException) as denied:
        _call(db, AiProxyRequest(format=2, mode="short", request_id="image-over", photos=[{"image": over, "order": 1}]))
    assert denied.value.status_code == 400 and denied.value.detail["code"] == "invalid_request"
    assert _Client.posts == 0
    _no_reservation(engine)
    _call(db, AiProxyRequest(format=2, mode="short", request_id="image-exact", photos=[{"image": exact, "order": 1}]))
    assert _Client.posts == 1
    engine.dispose()
