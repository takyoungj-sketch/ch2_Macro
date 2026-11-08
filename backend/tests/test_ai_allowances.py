from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, update
from app.ai import allowances as q
from app.platform.fieldnote_ai_router import AiProxyRequest, validated_input


@pytest.fixture
def ledger(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'allowances.db'}", connect_args={"timeout": 10})
    q.meta.create_all(engine)
    start = datetime(2026, 11, 7, tzinfo=timezone.utc)
    yield engine, q.Grant(7, "bundle", start, start + timedelta(days=31))
    engine.dispose()


def start(ledger, feature="macro_question", units=1, key="one", digest="same"):
    e, g = ledger
    return q.reserve(e, g, feature, units, key, digest)


def test_success_replay_and_conflict(ledger):
    t = start(ledger)
    q.finish(t, {"answer": "saved"})
    assert start(ledger).replay == {"answer": "saved"}
    assert q.snapshot(*ledger)["items"][0]["used"] == 1
    q.finish(t, {"answer": "duplicate"})
    assert q.snapshot(*ledger)["items"][0]["used"] == 1
    with pytest.raises(HTTPException) as ex:
        start(ledger, digest="different")
    assert ex.value.status_code == 409


def test_failure_restores_units(ledger):
    t = start(ledger, "photo_analysis_image", 12)
    q.finish(t, error="provider_failed")
    photo = q.snapshot(*ledger)["items"][1]
    assert (photo["used"], photo["reserved"], photo["remaining"]) == (0, 0, 500)
    assert start(ledger, key="retry").replay is None


@pytest.mark.parametrize("feature,limit", [("macro_question",250),("photo_analysis_image",500),
                                               ("text_writing",100),("address_sheet_job",100)])
def test_last_unit_and_overflow(ledger, feature, limit):
    t = start(ledger, feature, limit-1)
    q.finish(t, {"ok": True})
    with pytest.raises(HTTPException) as ex:
        start(ledger, feature, 2, key="too_many")
    assert ex.value.status_code == 429
    t = start(ledger, feature, 1, key="last")
    q.finish(t, {"ok": True})
    with pytest.raises(HTTPException):
        start(ledger, feature, key="overflow")


def test_busy_and_cross_account(ledger):
    t = start(ledger)
    with pytest.raises(HTTPException) as ex:
        start(ledger, key="another")
    assert ex.value.detail["code"] == "ai_busy"
    e,g=ledger
    other = q.Grant(8,g.plan,g.start,g.end)
    assert q.reserve(e,other,"macro_question",1,"one","different").replay is None
    q.finish(t,error="cancelled")


def test_concurrent_final_unit(ledger):
    e,g=ledger
    t = start(ledger, units=249)
    q.finish(t,{"ok":True})
    def attempt(key):
        try:
            t=start(ledger,key=key)
            q.finish(t,{"ok":True})
            return True
        except HTTPException:
            return False
    with ThreadPoolExecutor(2) as pool:
        assert sum(pool.map(attempt,["a","b"])) == 1
    assert q.snapshot(e,g)["items"][0]["used"] == 250


def test_transaction_rolls_back_result_failure(ledger):
    t=start(ledger)
    with t.engine.begin() as c:
        c.execute(q.results.insert().values(request_id=t.id,payload="{}"))
    with pytest.raises(Exception):
        q.finish(t,{"ok":True})
    item=q.snapshot(*ledger)["items"][0]
    assert (item["used"],item["reserved"]) == (0,1)
    q.finish(t,error="result_failed")
    assert q.snapshot(*ledger)["items"][0]["reserved"] == 0


def test_internal_calls_not_extra_questions(ledger):
    t=start(ledger)
    with q.tracking(t):
        q.record_provider(model="gpt-5-mini",prompt_tokens=1000,completion_tokens=100,cached_tokens=500)
        q.record_provider(model="gpt-5-mini",prompt_tokens=100,completion_tokens=20,stage="validation")
    q.finish(t,{"ok":True})
    with t.engine.connect() as c:
        events=c.execute(select(q.calls)).mappings().all()
    assert len(events)==2
    assert events[0]["usd"]==pytest.approx(.0003375)
    assert q.snapshot(*ledger)["items"][0]["used"]==1


def test_unknown_model_never_silently_mini_price(ledger):
    t=start(ledger)
    with q.tracking(t):
        q.record_provider(model="future-model",prompt_tokens=2000,completion_tokens=500)
    with t.engine.connect() as c:
        row=c.execute(select(q.calls)).mappings().one()
    assert row["usd"] is None and row["status"]=="cost_unknown"


def test_abandoned_reservation_requires_operator_and_age(ledger):
    t = start(ledger)
    with pytest.raises(ValueError):
        q.release_abandoned(t.engine, t.id, "operator", "verified stopped")
    with t.engine.begin() as c:
        c.execute(update(q.jobs).where(q.jobs.c.id == t.id).values(created_at=q.now_utc()-timedelta(hours=1)))
    q.release_abandoned(t.engine,t.id,"operator","worker stopped; no result")
    assert q.snapshot(*ledger)["items"][0]["reserved"] == 0
    with pytest.raises(ValueError):
        q.release_abandoned(t.engine,t.id,"operator","duplicate")


def test_macro_route_success_and_replay(ledger, monkeypatch):
    from app.ai import router as routes
    from app.ai.schemas import AiChatResponse
    from app.config import settings
    from app.platform.deps import CurrentUser
    from starlette.requests import Request
    from starlette.responses import Response
    from app.ai.schemas import AiChatRequest
    user=CurrentUser(7,"test@example.invalid","tester","member")
    monkeypatch.setattr(settings,"ai_subscription_quota_enabled",True)
    monkeypatch.setattr(q,"request_user",lambda _: user)
    monkeypatch.setattr(q,"grant_for_user",lambda _: ledger)
    monkeypatch.setattr(routes,"check_ai_rate_limit",lambda _: None)
    invocations=[]
    def answer(_):
        invocations.append(1)
        return AiChatResponse(session_id="test",route="ch2",answer="result",llm_used=True)
    monkeypatch.setattr(routes,"handle_chat",answer)
    body=AiChatRequest(message="question",request_id="same")
    request=Request({"type":"http","headers":[]})
    routes.ai_chat(body,request,Response())
    replay=routes.ai_chat(body,request,Response())
    assert len(invocations)==1
    assert replay.quota["items"][0]["used"]==1


@pytest.mark.parametrize("error",["provider_unavailable","evidence_validation_failed"])
def test_macro_failed_answer_refunds(ledger, monkeypatch,error):
    from app.ai import router as routes
    from app.ai.schemas import AiChatResponse,AiChatRequest
    from app.config import settings
    from app.platform.deps import CurrentUser
    from starlette.requests import Request
    from starlette.responses import Response
    monkeypatch.setattr(settings,"ai_subscription_quota_enabled",True)
    monkeypatch.setattr(q,"request_user",lambda _: CurrentUser(7,"x","x","member"))
    monkeypatch.setattr(q,"grant_for_user",lambda _: ledger)
    monkeypatch.setattr(routes,"check_ai_rate_limit",lambda _: None)
    monkeypatch.setattr(routes,"handle_chat",lambda _: AiChatResponse(session_id="x",route="ch2",answer="failed",llm_used=True,error_code=error))
    routes.ai_chat(AiChatRequest(message="question",request_id="x"),Request({"type":"http","headers":[]}),Response())
    assert q.snapshot(*ledger)["items"][0]["used"]==0


def test_fieldnote_bundle_photo_settlement_and_failure(ledger, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from app.platform import fieldnote_ai_router as route
    from app.config import settings
    monkeypatch.setattr(settings,"ai_subscription_quota_enabled",True)
    monkeypatch.setattr(settings,"openai_api_key","not-a-real-key")
    monkeypatch.setattr(route,"_is_fieldnote_premium",lambda *_:True)
    monkeypatch.setattr(q,"grant_for",lambda *_:ledger[1])
    replies=[{"model":"gpt-5-mini","usage":{"prompt_tokens":100,"completion_tokens":30},
              "choices":[{"message":{"content":"{\"primary_name\":\"tree\"}"},"finish_reason":"stop"}]}]
    class Client:
        def __init__(self,**_):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*_):pass
        async def post(self,*_,**kw):
            assert kw["json"]["max_completion_tokens"] <= settings.ai_max_output_tokens
            return SimpleNamespace(status_code=200,json=lambda:replies[0])
    monkeypatch.setattr(route.httpx,"AsyncClient",Client)
    db=SimpleNamespace(get_bind=lambda:ledger[0]);user=SimpleNamespace(id=7,role="member")
    body=AiProxyRequest(request_id="photo",max_tokens=999999,messages=[{"role":"user","content":[image(),image("data:image/jpeg;base64,Yg==")]}])
    data=asyncio.run(route._proxy_openai(body,"device",db,kind="short",user=user))
    assert data["ch2_usage"]["items"][1]["used"]==2
    # Same request and normalized inputs reuse the stored response, not another charge.
    replay=asyncio.run(route._proxy_openai(body,"device",db,kind="short",user=user))
    assert replay["ch2_usage"]["items"][1]["used"]==2
    body.request_id="bad"
    replies[0]={"model":"gpt-5-mini","choices":[],"usage":{"prompt_tokens":100,"completion_tokens":0}}
    with pytest.raises(HTTPException):
        asyncio.run(route._proxy_openai(body,"device",db,kind="short",user=user))
    assert q.snapshot(*ledger)["items"][1]["used"]==2
    body.request_id="empty-sheet"
    body.response_format={"type":"json_object"}
    replies[0]={"model":"gpt-5-mini","choices":[{"message":{"content":"{\"rows\":[]}"}}],"usage":{}}
    with pytest.raises(HTTPException):
        asyncio.run(route._proxy_openai(body,"device",db,kind="sheet",user=user,feature="address_sheet_job"))
    assert q.snapshot(*ledger)["items"][3]["used"]==0
    body=AiProxyRequest(request_id="write",messages=[{"role":"user","content":"현장 메모"}])
    replies[0]={"model":"gpt-5-mini","choices":[{"message":{"content":"정리한 문구"}}],"usage":{}}
    asyncio.run(route._proxy_openai(body,"device",db,kind="long",user=user,feature="text_writing"))
    assert q.snapshot(*ledger)["items"][2]["used"]==1
    # Old released apps have no request_id; still count server-side image units.
    legacy = AiProxyRequest(messages=[{"role":"user","content":[image()]}])
    asyncio.run(route._proxy_openai(legacy,"device",db,kind="short",user=user))
    assert q.snapshot(*ledger)["items"][1]["used"]==3


def test_macro_only_and_upgrade_keeps_usage(ledger):
    e,g=ledger
    g=q.Grant(g.user_id,"macro",g.start,g.end)
    t=q.reserve(e,g,"macro_question",200,"all","x")
    q.finish(t,{"ok":True})
    with pytest.raises(HTTPException):
        q.reserve(e,g,"photo_analysis_image",1,"photo","x")
    up=q.Grant(g.user_id,"bundle",g.start,g.end)
    assert q.snapshot(e,up)["items"][0]["remaining"] == 50


def test_period_boundary_and_month_end(ledger):
    e,g=ledger
    t=start(ledger)
    new=q.Grant(g.user_id,g.plan,g.end,g.end+timedelta(days=31))
    q.finish(t,{"ok":True})
    assert q.snapshot(e,g)["items"][0]["used"]==1
    assert q.snapshot(e,new)["items"][0]["used"]==0
    anchor=datetime(2024,1,31,tzinfo=timezone.utc)
    assert q.month_after(anchor,1).day==29
    assert q.month_after(anchor,2).day==31


def test_subscription_source_and_actual_period(ledger):
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from types import SimpleNamespace
    e,g=ledger
    with e.begin() as c:
        c.execute(text("CREATE TABLE subscriptions (id INTEGER, user_id INTEGER, product TEXT, plan_id TEXT, source TEXT, status TEXT, created_at TEXT, current_period_end TEXT)"))
        c.execute(text("CREATE TABLE entitlements (user_id INTEGER, product TEXT, active BOOLEAN, expires_at TEXT)"))
        c.execute(text("INSERT INTO entitlements VALUES (7,'macro',TRUE,NULL),(7,'fieldnote',TRUE,NULL)"))
        c.execute(text("INSERT INTO subscriptions VALUES (1,7,'macro','macro_monthly','web_toss','active',:start,:end)"),{"start":g.start,"end":g.end})
    with Session(e) as db:
        grant=q.grant_for(db,SimpleNamespace(id=7),now=g.start+timedelta(days=2))
    assert grant.plan=="macro"  # two entitlements never imply a bundle
    assert grant.end==g.end and grant.start==g.start
    t=q.reserve(e,grant,"macro_question",1,"first","x");q.finish(t,{"ok":True})
    with e.begin() as c:
        c.execute(text("INSERT INTO subscriptions VALUES (2,7,'bundle','bundle_monthly','web_toss','active',:start,:end)"),{"start":g.start+timedelta(days=3),"end":g.end+timedelta(days=3)})
    with Session(e) as db:
        upgraded=q.grant_for(db,SimpleNamespace(id=7),now=g.start+timedelta(days=4))
    assert upgraded.plan=="bundle" and upgraded.start==g.start and upgraded.end==g.end
    assert q.snapshot(e,upgraded)["items"][0]["remaining"]==249


def image(url="data:image/jpeg;base64,YQ=="):
    return {"type":"image_url","image_url":{"url":url}}


def test_server_counts_and_deduplicates_images():
    body=AiProxyRequest(messages=[{"role":"user","content":[image(),image(),image("data:image/jpeg;base64,Yg==")]}])
    assert validated_input(body,"photo_analysis_image")==2
    assert len(body.messages[0]["content"])==2


@pytest.mark.parametrize("feature,messages", [
    ("photo_analysis_image",[{"role":"user","content":"no photo"}]),
    ("photo_analysis_image",[{"role":"user","content":[image("http://127.0.0.1/secret")]}]),
    ("text_writing",[{"role":"user","content":[image()]}]),
    ("address_sheet_job",[{"role":"user","content":"x"*40001}]),
])
def test_invalid_input_rejected_before_reservation(feature,messages):
    with pytest.raises(HTTPException):
        validated_input(AiProxyRequest(messages=messages),feature)
