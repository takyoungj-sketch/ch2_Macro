"""실측 수치는 서버의 fact 참조로만 삽입한다. 숫자 토큰 일치로 승인하지 않는다."""
from __future__ import annotations

import re
import secrets
from typing import Any
from app.ai3.schemas import Fact

_REF = re.compile(r"\{\{(f\d+)\}\}")
_VALUATION = re.compile(r"(?:매수|매도).{0,8}(?:추천|하세요)|적정가격.{0,4}(?:입니다|이다)|저평가.{0,4}(?:입니다|이다)|반드시.{0,6}(?:오르|내리)")
_EXCLUDE = {"transactions", "raw_rows", "raw", "points", "jibun_address", "road_address", "address", "sql"}


def redact_for_llm(data: Any) -> Any:
    """질문·대화에 실수로 붙인 비밀키와 개별 지번/도로명 번지를 전송 전에 가린다."""
    if isinstance(data, dict):
        return {redact_for_llm(k): redact_for_llm(v) for k, v in data.items() if k not in _EXCLUDE}
    if isinstance(data, list):
        return [redact_for_llm(x) for x in data]
    if not isinstance(data, str):
        return data
    value = re.sub(r"\bsk-[A-Za-z0-9_-]{12,}", "[비밀키 제외]", data)
    value = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~-]{12,}", "[인증값 제외]", value)
    value = re.sub(r"[가-힣A-Za-z0-9·]{2,40}(?:읍|면|동|리|로|길)\s+(?:산\s*)?\d+(?:-\d+)?(?:번지|호)?", "[개별 주소 제외]", value)
    return value


def external_view(data: Any, aliases: dict[str, str]) -> Any:
    """주소가 들어갈 수 있는 내부 대상키는 세션 전용 불투명 참조로 치환한다."""
    if isinstance(data, list):
        return [external_view(x, aliases) for x in data]
    if not isinstance(data, dict):
        return data
    out = {}
    for key, value in data.items():
        if key in _EXCLUDE:
            continue
        if key in ("building_key", "cluster_key", "target_key") and isinstance(value, str):
            if value in aliases:
                out[key] = value
                continue
            ref = next((ref for ref, raw in aliases.items() if raw == value), None)
            if ref is None:
                ref = "target-" + secrets.token_urlsafe(12)
                aliases[ref] = value
            out[key] = ref
        elif key in ("building_keys", "cluster_keys"):
            continue
        else:
            out[key] = external_view(value, aliases)
    return out


def extract_facts(data: Any, source: str, limit: int = 100) -> list[Fact]:
    output: list[Fact] = []

    def walk(value: Any, path: str) -> None:
        if len(output) >= limit:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                if key not in _EXCLUDE:
                    walk(child, f"{path}.{key}" if path else key)
        elif isinstance(value, list):
            for i, child in enumerate(value[:20]):
                walk(child, f"{path}[{i}]")
        elif value is not None:
            text = str(value)
            if len(text) <= 240:
                output.append(Fact(id=f"f{len(output)}", label=path, value=text, source=source))

    walk(data, "")
    return output


def render_grounded(prose: str, facts: list[Fact]) -> str | None:
    # 번호 목록의 순서는 실측값이 아니다. 문장 속 숫자는 그대로 검증한다.
    prose = re.sub(r"(?m)^([ \t]*)\d{1,2}[.)]\s+", r"\1- ", prose)
    lookup = {f.id: f.value for f in facts}
    ids = _REF.findall(prose)
    if any(i not in lookup for i in ids):
        return None
    unbound = _REF.sub("", prose)
    unbound = re.sub(r"(?<![A-Za-z0-9])(?:CH2|AI2|AI3)(?![A-Za-z0-9])", "", unbound)
    unbound = re.sub(r"(?<![A-Za-z0-9])P(?:25|50|75)(?![A-Za-z0-9])", "", unbound)
    # API 수치를 부호·단위가 달라진 자연어 수치로 바꾸지 않는다.
    if re.search(r"[0-9]|\{\{|\}\}", unbound) or _VALUATION.search(unbound):
        return None
    # 부호/단위/퍼센트는 fact 자체에 있어야 한다. 참조 앞뒤에 가산하지 않는다.
    if re.search(r"[+−–-]\s*\{\{|\}\}\s*(?:%|퍼센트|억|만원|원|배|㎡)", prose):
        return None
    return _REF.sub(lambda m: lookup[m.group(1)], prose).strip() or None
