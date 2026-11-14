"""집합 2단계 공통 가드 — 실제 적용 모드(pipeline/collective/migrate_p2_keys), 범위 드라이런(scope_dryrun),
운영 확인 스크립트(prod_sync_check·prod_hash_compare)가 모두 이 모듈을 쓴다.

운영 서버에는 pipeline 이 배포되지 않으므로 이 파일은 표준 라이브러리 + SQLAlchemy 만 쓴다(운영 확인 폴더와 함께 복사).

- assert_local_target(engine | URL): **허용 목록 방식.** 드라이버가 최종 해석한 접속 정보로 호스트를 판정해 로컬 루프백만 허용.
    · URL 쿼리는 sslmode·connect_timeout·application_name 만 허용. 그 밖(dsn·service·host·hostaddr·options …)은 모두 거부
    · psycopg2 에 실제로 넘어갈 DSN(SQLAlchemy create_connect_args → psycopg2.extensions.make_dsn)을 parse_dsn 으로 풀어
      host·hostaddr 를 본다(`?dsn=host%3D…` 처럼 dsn 문자열 안에 숨은 호스트도 드러난다)
    · hostaddr 가 없으면 PGHOSTADDR, host 가 없으면 PGHOST 환경변수(libpq 규칙 — hostaddr 는 host 보다 먼저 쓰인다)
    · service(인자·PGSERVICE)·PGSERVICEFILE 이 있으면 실제 호스트를 알 수 없으므로 거부
    · host·hostaddr 가 하나라도 루프백(localhost·127.0.0.0/8·::1·유닉스 소켓)이 아니면 거부
- validate_result(obj, expected_targets, kind=…): compare 결과 파일 검증. 하나라도 어긋나면 「검증 못 함」.
    필수 필드·형식 / 측정 시각(미래 금지, 48시간 이내) / 대상 목록 일치 / 실패 기록 없음 / diff·unverified 모두 0
"""
from __future__ import annotations

import datetime as _dt
import ipaddress
import os
from typing import Any, Iterable, Mapping

PASS, DIFF, UNVERIFIED = "pass", "diff", "unverified"
MAX_AGE_H = 48
FUTURE_SKEW_S = 60
RESULT_KINDS = {"prod_sync_check", "prod_hash_compare", "prod_hash_pgcheck"}
REQUIRED_FIELDS = ("kind", "status", "left_db", "right_db", "targets", "created_at", "diff", "unverified", "failures")


class TargetError(RuntimeError):
    """접속 대상이 로컬 루프백이 아님(또는 판정 불가)."""


def _is_loopback(h: str) -> bool:
    h = h.strip()
    if not h:
        return False
    if h.startswith("/") or h.startswith("@"):          # 유닉스 소켓 디렉터리 / 추상 소켓
        return True
    if h.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(h.strip("[]")).is_loopback
    except ValueError:
        return False


ALLOWED_QUERY = frozenset({"sslmode", "connect_timeout", "application_name"})


def _url_of(target: Any):
    from sqlalchemy.engine import Engine, make_url

    if isinstance(target, Engine):
        return target.url
    return make_url(target) if not hasattr(target, "drivername") else target


def check_query(target: Any) -> None:
    """URL 쿼리 허용 목록. 허용 밖 키가 하나라도 있으면 TargetError(키 이름만 알리고 값은 출력하지 않음)."""
    bad = sorted(k for k in _url_of(target).query if k not in ALLOWED_QUERY)
    if bad:
        raise TargetError(f"URL 쿼리에 허용되지 않은 접속 옵션: {bad} (허용: {sorted(ALLOWED_QUERY)})")


def libpq_params(target: Any) -> dict:
    """psycopg2(libpq)가 최종으로 쓰는 접속 정보. target = Engine 또는 URL. 접속하지 않는다.
    SQLAlchemy create_connect_args → psycopg2.extensions.make_dsn(dsn 문자열 + 키워드 합치기) → parse_dsn."""
    from sqlalchemy import create_engine

    u = _url_of(target)
    if u.drivername == "postgresql":
        u = u.set(drivername="postgresql+psycopg2")
    eng = create_engine(u)
    try:
        _a, kw = eng.dialect.create_connect_args(eng.url)
    finally:
        eng.dispose()
    kw = dict(kw)
    try:
        from psycopg2.extensions import make_dsn, parse_dsn
    except ImportError:                                     # psycopg2 없으면 키워드 그대로(dsn 이 있으면 판정 불가)
        if "dsn" in kw:
            raise TargetError("dsn 접속 문자열을 풀 수 없음(psycopg2 없음)") from None
        return kw
    dsn = kw.pop("dsn", None)
    try:
        return dict(parse_dsn(make_dsn(dsn, **{k: v for k, v in kw.items() if v is not None})))
    except Exception as ex:  # noqa: BLE001
        raise TargetError(f"접속 정보를 해석할 수 없음: {type(ex).__name__}") from None


def final_hosts(kw: Mapping[str, Any], environ: Mapping[str, str] | None = None) -> list[str]:
    """libpq 가 실제로 접속할 주소 목록. 판정 불가(service)면 TargetError."""
    env = os.environ if environ is None else environ
    kw = {str(k).lower(): v for k, v in kw.items()}       # 대소문자 바꾼 키(HOST=…)도 같은 것으로 본다
    if kw.get("service") or env.get("PGSERVICE") or env.get("PGSERVICEFILE"):
        raise TargetError("service 접속 설정(service·PGSERVICE·PGSERVICEFILE) — 실제 호스트를 확인할 수 없음")
    hostaddr = str(kw.get("hostaddr") or env.get("PGHOSTADDR") or "")
    host = str(kw.get("host") or env.get("PGHOST") or "")
    out = [h for h in hostaddr.split(",") if h.strip()] + [h for h in host.split(",") if h.strip()]
    return out


def assert_local_target(target: Any, *, environ: Mapping[str, str] | None = None) -> list[str]:
    """로컬 루프백(localhost·127.0.0.0/8·::1·유닉스 소켓)만 허용. 값(비밀번호 등)은 메시지에 넣지 않는다."""
    check_query(target)
    kw = libpq_params(target)
    hosts = final_hosts(kw, environ)
    if not hosts:
        return ["(기본 유닉스 소켓)"]
    bad = [h for h in hosts if not _is_loopback(h)]
    if bad:
        raise TargetError("접속 대상이 로컬 루프백이 아님 — 중단(운영 접속 차단)")
    return hosts


def _parse_ts(v: Any) -> _dt.datetime | None:
    try:
        t = _dt.datetime.fromisoformat(str(v))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo is not None else None


def validate_result(obj: Any, expected_targets: Iterable[str], *, kind: str | Iterable[str] | None = None,
                    now: _dt.datetime | None = None, max_age_h: float = MAX_AGE_H) -> tuple[str, list[str]]:
    """결과 파일 검증 → (pass | diff | unverified, 사유 목록). 통과는 모든 조건이 맞을 때만.
    diff 는 「형식은 온전하고 차이가 있다」일 때, 나머지 어긋남은 모두 unverified."""
    why: list[str] = []
    if not isinstance(obj, dict):
        return UNVERIFIED, ["결과가 JSON 객체가 아님"]
    miss = [f for f in REQUIRED_FIELDS if f not in obj]
    if miss:
        return UNVERIFIED, [f"필수 필드 없음: {miss}"]
    kinds = {kind} if isinstance(kind, str) else set(kind) if kind else RESULT_KINDS
    if obj["kind"] not in kinds:
        why.append(f"결과 종류가 다름: {obj['kind']}")
    if obj["status"] not in (PASS, DIFF, UNVERIFIED):
        why.append(f"상태 값 형식 오류: {obj['status']}")
    t = _parse_ts(obj["created_at"])
    now = now or _dt.datetime.now(_dt.timezone.utc)
    if t is None:
        why.append("측정 시각 형식 오류(시간대 포함 ISO 필요)")
    else:
        if (t - now).total_seconds() > FUTURE_SKEW_S:
            why.append("측정 시각이 미래")
        if (now - t).total_seconds() > max_age_h * 3600:
            why.append(f"측정 시각이 {max_age_h}시간보다 오래됨")
    targets = obj["targets"]
    if not isinstance(targets, list) or not all(isinstance(x, str) and x for x in targets):
        why.append("대상 목록 형식 오류")
    elif sorted(set(targets)) != sorted(set(expected_targets)):
        why.append(f"대상 목록 불일치: {sorted(set(targets))} ≠ {sorted(set(expected_targets))}")
    if not (obj["left_db"] and obj["left_db"] == obj["right_db"] and obj["left_db"] in set(expected_targets)):
        why.append("비교한 두 DB 이름이 같지 않거나 대상이 아님")
    if not isinstance(obj["failures"], list):
        why.append("실패 기록 형식 오류")
    elif obj["failures"]:
        why.append(f"실패 기록 있음({len(obj['failures'])})")
    ndiff = obj["diff"]
    unv = obj["unverified"]
    if not isinstance(ndiff, int) or isinstance(ndiff, bool) or ndiff < 0:
        why.append("diff 형식 오류")
    if not isinstance(unv, list):
        why.append("unverified 형식 오류")
    elif unv:
        why.append(f"검증 못 함 항목 {len(unv)}")
    if why:
        return UNVERIFIED, why
    if ndiff or obj["status"] == DIFF:
        return DIFF, [f"차이 {ndiff}"]
    if obj["status"] != PASS:
        return UNVERIFIED, [f"상태가 통과가 아님: {obj['status']}"]
    return PASS, []
