"""AI 사용량 장부 테스트."""

from pathlib import Path

import pytest

from app.ai.usage_log import (
    AiQuotaExceeded,
    assert_quota_or_raise,
    estimate_usd,
    month_snapshot,
    record_llm_call,
)


@pytest.fixture
def usage_dir(tmp_path: Path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ai_usage_log_dir", str(tmp_path))
    monkeypatch.setattr(settings, "ai_monthly_call_limit", 200)
    monkeypatch.setattr(settings, "ai_monthly_budget_krw", 10000)
    monkeypatch.setattr(settings, "ai_usd_krw", 1400)
    return tmp_path


def test_estimate_gpt5_mini_cheaper_than_54():
    mini = estimate_usd(model="gpt-5-mini", prompt_tokens=4000, completion_tokens=800)
    v54 = estimate_usd(model="gpt-5.4-mini", prompt_tokens=4000, completion_tokens=800)
    assert mini < v54
    assert mini > 0


def test_record_and_snapshot(usage_dir: Path):
    record_llm_call(
        requested_model="gpt-5-mini",
        served_model="gpt-5-mini-2025-08-07",
        prompt_tokens=1000,
        completion_tokens=200,
    )
    snap = month_snapshot()
    assert snap["calls"] == 1
    assert snap["krw"] > 0
    assert snap["stopped"] is False
    assert "question" not in (snap["recent"][0] or {})
    files = list(usage_dir.glob("*.jsonl"))
    assert files
    text = files[0].read_text(encoding="utf-8")
    assert "MAPE" not in text


def test_quota_stops_at_call_limit(usage_dir: Path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ai_monthly_call_limit", 1)
    record_llm_call(
        requested_model="gpt-5-mini",
        served_model="gpt-5-mini",
        prompt_tokens=10,
        completion_tokens=5,
    )
    with pytest.raises(AiQuotaExceeded):
        assert_quota_or_raise()
