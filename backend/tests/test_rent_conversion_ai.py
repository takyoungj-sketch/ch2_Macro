"""전환율 실험 종료 — AI·지식 팩이 채택 이유를 답하는지."""

from app.ai.constitution import classify_route
from app.ai.knowledge.product import product_knowledge_excerpt, product_knowledge_pack
from app.ai.orchestrator import handle_chat
from app.ai.schemas import AiChatRequest, AiContext, AiScope
from app.ai.targeted_qa import answer_conversion_method_question


def test_product_pack_rent_mentions_mean_simple():
    pack = product_knowledge_pack(app="rent")
    assert "mean_simple" in pack
    assert "한국부동산원" in pack
    excerpt = product_knowledge_excerpt(app="built", panel="", message="왜 단순평균 전환율인가요?")
    assert "hold-out" in excerpt
    assert "mean_simple" in excerpt


def test_targeted_conversion_answer():
    ans = answer_conversion_method_question(
        "왜 단순평균 전환율인가요?",
        {"r_selected": 5.08, "window_years": 5, "conversion_method": "mean_simple"},
    )
    assert ans is not None
    assert "단순평균" in ans
    assert "한국부동산원" in ans
    assert "5.08%" in ans
    assert "시세" in ans


def test_chat_why_simple_mean(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ai_open_mode", False)
    monkeypatch.setattr("app.ai.orchestrator.llm_configured", lambda: False)
    req = AiChatRequest(
        message="왜 단순평균 전환율인가요?",
        context=AiContext(
            app="rent",
            panel="RentListCard",
            purpose="methodology",
            scope=AiScope(region_label="서울특별시 강남구"),
            facts={
                "r_selected": 5.08,
                "window_years": 5,
                "conversion_applied": True,
                "conversion_method": "mean_simple",
            },
        ),
    )
    resp = handle_chat(req)
    assert "단순평균" in resp.answer
    assert "공식" in resp.answer or "한국부동산원" in resp.answer
    assert resp.route in ("explain", "opinion", "ch2", "statistics")


def test_chat_conversion_wins_over_open_mode(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ai_open_mode", True)
    req = AiChatRequest(
        message="적용 전환율은 공식값인가요?",
        context=AiContext(
            app="rent",
            panel="RentListCard",
            facts={"r_selected": 5.08, "window_years": 5, "conversion_applied": True},
        ),
    )
    resp = handle_chat(req)
    assert resp.route == "opinion"
    assert resp.llm_used is False
    assert "한국부동산원" in resp.answer
    assert "5.08%" in resp.answer


def test_conversion_not_refusal():
    assert classify_route("왜 단순평균 전환율인가요?") != "refusal"
    assert classify_route("적용 전환율은 공식값인가요?") != "refusal"


def test_product_pack_rent_includes_sangkwon_reb():
    pack = product_knowledge_pack(app="rent")
    assert "상업용부동산 임대동향조사" in pack
    assert "임대료 ≠ 임대수입" in pack
    assert "복리" in pack
    excerpt = product_knowledge_excerpt(app="rent", panel="SangkwonCard", message="공실률을 NOI에 곱하면 되나요?")
    assert "공실" in excerpt
    assert "hold-out" not in excerpt


def test_chat_sangkwon_not_conversion_bundle(monkeypatch):
    from app.ai.bundles.extractors import build_bundle
    from app.config import settings

    monkeypatch.setattr(settings, "ai_open_mode", False)
    ctx = AiContext(
        app="rent",
        panel="SangkwonCard",
        purpose="methodology",
        scope=AiScope(region_label="서울 종로구 · 광화문"),
        facts={"sec_nm": "광화문", "year": 2025, "annual": {"rent": {"small_retail": 109.71}}},
    )
    pack = build_bundle(ctx)
    assert pack.bundle_id == "sangkwon_reb"
    assert "광화문" in " ".join(pack.summary_lines)
