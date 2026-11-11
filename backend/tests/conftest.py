"""테스트 공통 설정."""

import pytest


@pytest.fixture(autouse=True)
def _isolated_ai_usage_log(tmp_path_factory, monkeypatch):
    """AI 사용량·질문 장부를 저장소 logs/ 가 아니라 임시 폴더에 쓴다."""
    from app.config import settings

    monkeypatch.setattr(settings, "ai_usage_log_dir", str(tmp_path_factory.mktemp("ai_usage")))
    # 미지원 파라미터 경고 JSONL 도 저장소 logs/ 가 아니라 임시 폴더에 쓴다(집합 1단계 C-05).
    monkeypatch.setattr(
        settings, "api_param_warn_path", str(tmp_path_factory.mktemp("api_param_warn") / "api_param_warn.jsonl")
    )
