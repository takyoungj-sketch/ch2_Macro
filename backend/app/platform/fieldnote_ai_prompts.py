"""FieldNote AI 프롬프트.

앱 f496ff2의 system 문장을 그대로 두고, 현장조사 보조 한 줄을 더한다.
구 형식의 user 텍스트는 그대로 두고, v2는 같은 구성으로 서버가 만든다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.config import settings
from app.platform.fieldnote_ai_access import PHOTO, SHEET, WRITE, raise_fieldnote_deny

_ASSISTANT_LINE = "FieldNote 현장조사 보조로만 답한다."
_UNCERTAIN = "불확실"
_OUTPUT_TOKENS = 4000
_DATA_URLS = ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")

_SHORT_SYSTEM = (
    "You are a Korean field appraisal assistant. SHORT mode: return one compact JSON with "
    "object_kind, primary_name, and a few key attributes. No verbose prose. No text outside JSON."
)
_LONG_SYSTEM = (
    "You are a Korean field appraisal assistant for real estate and movable assets "
    "(trees, machines, buildings). Output exactly one JSON object with primary_name, summary, "
    "and attributes. No prose outside JSON. Prefer survey-usable detail (e.g. exterior materials) "
    "over generic category labels."
)
_SHEET_SYSTEM = (
    "You extract Korean survey address lists from images. Preserve duplicate rows. "
    "Use address exactly \"불확실\" when uncertain. Output exactly one JSON object with a "
    "top-level 'rows' array. No prose outside JSON."
)
_WRITE_SYSTEM = (
    "사용자가 제공한 현장 메모를 이해하기 쉬운 한국어 조사 문구로 정리합니다. "
    "제공되지 않은 사실·수치·가격 판단을 추가하지 않습니다. 정리된 문구만 답하세요."
)

_PHOTO_CAP = {"short": 4, "long": 6, "sheet": 6}
_LEGACY_TEXT_CAP = 8000
_NOTE_CAP = 2000
_WRITE_CAP = 4000


@dataclass
class PreparedCall:
    messages: list
    units: int
    model: str
    temperature: float
    max_tokens: int
    response_format: dict | None


def _invalid() -> None:
    raise_fieldnote_deny("invalid_request")


def _system(mode: str) -> str:
    base = {"short": _SHORT_SYSTEM, "long": _LONG_SYSTEM, "sheet": _SHEET_SYSTEM, "write": _WRITE_SYSTEM}[mode]
    return f"{base}\n{_ASSISTANT_LINE}"


def _model() -> str:
    return (settings.openai_model or "gpt-5-mini").strip() or "gpt-5-mini"


def _output_tokens() -> int:
    ceiling = int(getattr(settings, "ai_max_output_tokens", _OUTPUT_TOKENS) or _OUTPUT_TOKENS)
    return min(_OUTPUT_TOKENS, ceiling)


def _data_url(url: object) -> str:
    if not isinstance(url, str) or not url.startswith(_DATA_URLS):
        _invalid()
    return url


def _limit_text(value: str, cap: int) -> str:
    if len(value) > cap:
        _invalid()
    return value


def _detail(mode: str, count: int) -> str:
    if mode == "sheet":
        return "high" if count <= 4 else "low"
    return "low"


def _user_content(text: str, images: list[str], detail: str):
    if not images:
        return text
    parts = []
    if text:
        parts.append({"type": "text", "text": text})
    for url in images:
        parts.append({"type": "image_url", "image_url": {"url": url, "detail": detail}})
    return parts


def _legacy_parts(messages) -> tuple[str, list[str]]:
    texts: list[str] = []
    images: list[str] = []
    seen: set[str] = set()
    size = 0
    for message in messages or []:
        if not isinstance(message, dict) or message.get("role") == "system":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            texts.append(content)
            continue
        if not isinstance(content, list):
            _invalid()
        for part in content:
            if not isinstance(part, dict):
                _invalid()
            if part.get("type") == "image_url":
                url = _data_url((part.get("image_url") or {}).get("url", ""))
                if url in seen:
                    continue
                seen.add(url)
                size += len(url)
                images.append(url)
            elif part.get("type") == "text":
                texts.append(str(part.get("text", "")))
            else:
                _invalid()
    if size > 20_000_000:
        _invalid()
    return "\n".join(texts), images


def _photo_lines(rows: list[tuple[int, str | None]], prefix: str) -> list[str]:
    return [f"- {prefix} #{order}" + (f" {label}" if label else "") for order, label in rows]


def _ocr_lines(rows: list[tuple[int, str | None]], hints: dict[int, str], prefix: str) -> list[str]:
    lines = []
    for order, _label in rows:
        ocr = hints.get(order, "")
        if not ocr:
            lines.append(f"- {prefix} #{order} OCR: (추출된 글자 없음)")
            continue
        indented = "\n".join(f"  {line}" for line in ocr.split("\n"))
        lines.append(f"- {prefix} #{order} OCR:\n{indented}")
    return lines


def _record_prompt(mode: str, rows: list[tuple[int, str | None]], note: str, hints: dict[int, str]) -> str:
    photo_lines = _photo_lines(rows, "사진")
    ocr_block = _ocr_lines(rows, hints, "사진")
    memo = f"메모: {note.strip() or '없음'}"
    if mode == "short":
        example = {
            "object_kind": "building",
            "object_kind_label": "건물",
            "primary_name": "경량철골 단층 창고",
            "summary": "칼라강판 외장 단층 창고로 보임.",
            "attributes": [
                {"key": "structure", "label": "구조", "value": "경량철골"},
                {"key": "exterior", "label": "외장재", "value": "칼라강판"},
                {"key": "use", "label": "용도", "value": "창고"},
            ],
            "alternates": [],
            "uncertainty_note": "",
            "next_check": "",
            "reasoning": "외장·개구부 형태",
        }
        lines = [
            "역할: 감정평가·현장조사 보조. **단문 모드** — 조사표에 바로 적을 핵심만.",
            "구글 렌즈식 웹 상품검색 금지. 분류·표기명·핵심 속성에만 집중.",
            "",
            "[절대 금지] '수목이다', '기계다', '건물이다'처럼 상위 범주만 말하지 마라.",
            "",
            "[필수 — 짧게]",
            "- object_kind / object_kind_label",
            "- primary_name: 구체 이름(예: 소나무(추정), 경량철골 단층 창고)",
            "- attributes: **최대 4개**, 사진에 보이는 핵심만(없으면 [])",
            "- summary: **한 문장** 또는 빈 문자열",
            "- alternates: 가능하면 []. 확신 낮을 때만 1개",
            "- uncertainty_note / next_check / reasoning: 필요할 때만 한 줄, 아니면 \"\"",
            "",
            "[종류별 attributes 힌트 — 해당 시 2~4개만]",
            "- 수목: species_hint, leaf, bark",
            "- 기계: equipment_type, brand, model",
            "- 건물: structure, exterior, use (층수·지붕은 보일 때만)",
            "",
            "[OCR] 오인식 가능. 사진 우선. 명판·모델명이 있으면 primary_name·attributes에 반영.",
            *ocr_block,
            "",
            "[object_kind] tree | machine | building | land | facility | defect | document | other | unclear",
            "",
            "출력: JSON 한 개만. 한국어. 군더더기 서술 금지.",
            "요청 형식 예시:",
            json.dumps(example, ensure_ascii=False, indent=2),
            "",
            "사진 정보:",
            *photo_lines,
            "",
            memo,
        ]
    else:
        example = {
            "object_kind": "building",
            "object_kind_label": "건물",
            "primary_name": "경량철골 단층 창고",
            "summary": "현장 조사표에 적을 한두 문장 요약.",
            "attributes": [
                {"key": "structure", "label": "구조", "value": "경량철골"},
                {"key": "exterior", "label": "외장재", "value": "칼라강판"},
                {"key": "roof", "label": "지붕", "value": "샌드위치패널"},
                {"key": "floors", "label": "층수", "value": "지상 1층"},
                {"key": "use", "label": "용도", "value": "창고"},
            ],
            "alternates": [{"name": "차선 후보명", "why_one_line": "사진에서 보인 단서 한 줄"}],
            "uncertainty_note": "무엇이 불명확한지 한 줄",
            "next_check": "더 확실히 하려면 어떻게 찍을지 한 줄(없으면 빈 문자열)",
            "reasoning": "후보를 고른 핵심 근거(짧게)",
        }
        lines = [
            "역할: 감정평가·현장조사 보조. **장문 모드** — 상세 조사·보고서 보조.",
            "구글 렌즈처럼 웹 상품검색을 흉내 내지 말고, **분류·표기명·조사 속성(외장재 등)** 에 집중하라.",
            "",
            "[절대 금지] '수목이다', '기계다', '건물이다'처럼 상위 범주만 말하지 마라.",
            "",
            "[필수]",
            "- primary_name: 현장 장부·조사표에 적을 구체 이름.",
            "- summary: 한국어 한두 문장 현장 요약(자유 서술).",
            "- attributes: 보이는 범위의 조사 속성 배열(없으면 []). 사진에 없는 값은 추측하지 말고 넣지 마라.",
            "",
            "[종류별 attributes 가이드]",
            "- 수목(tree): species_hint(수종 단서), leaf(잎), bark(수피), size_hint(크기감) 등.",
            "- 기계/설비(machine): equipment_type(장비종류), brand(브랜드), model(모델/형식), nameplate(명판 텍스트) 등.",
            "- 건물(building): structure(구조), exterior(외장재), roof(지붕), floors(층수), use(용도), openings(창·출입) 등.",
            "- 토지(land): land_use(이용상태), topography(지형), access(접근) 등.",
            "- 시설물(facility): facility_type, material, condition 등.",
            "- 하자(defect): defect_type, location, severity 등.",
            "- 문서/명판(document): visible_text, document_type 등.",
            "",
            "[수목·기계·건물 이름]",
            "- 수목: 통용 수종명. 확신 없으면 alternates 2~3개 + why_one_line에 잎·수피 근거.",
            "- 기계: 종류 + 가능하면 모델·명판 반영.",
            "- 건물: 구조·용도·외장재가 드러나면 primary_name·attributes에 반영(예: 경량철골 단층 창고).",
            "- 사진에 없으면 단정 금지. uncertainty_note·next_check에 반영.",
            "",
            "[OCR 참고 — 기기에서 자동 추출]",
            "- OCR은 오인식될 수 있다. OCR과 사진이 모순되면 **사진을 우선**하고 uncertainty_note에 적어라.",
            "- OCR에 명판·간판·라벨·모델명이 있으면 primary_name·attributes·alternates에 적극 반영.",
            *ocr_block,
            "",
            "[object_kind] 반드시 아래 중 하나의 문자열: tree | machine | building | land | facility | defect | document | other | unclear",
            "",
            "출력 규칙:",
            "- JSON 한 개만. 마크다운·코드펜스·설명 문장 바깥 텍스트 금지.",
            "- 한국어. 문장은 짧게. attributes.value도 짧게.",
            "",
            "요청할 JSON 형식 예시:",
            json.dumps(example, ensure_ascii=False, indent=2),
            "",
            "사진 정보:",
            *photo_lines,
            "",
            memo,
        ]
    return "\n".join(lines)


def _sheet_prompt(count: int, hints: dict[int, str]) -> str:
    example = {
        "rows": [
            {"seq": "1", "address": "OO시 OO구 OO동 산123-4", "note": "메모1", "note2": "메모2", "note3": "메모3"},
            {"seq": "2", "address": "OO시 OO구 OO리 456-7", "note": "첫째행", "note2": "둘째행", "note3": ""},
            {"seq": "3", "address": _UNCERTAIN, "note": "글자가 흐려 지번을 확정할 수 없음", "note2": "", "note3": ""},
        ]
    }
    ocr_lines = _ocr_lines([(order, None) for order in range(1, count + 1)], hints, "이미지")
    return "\n".join([
        "역할: 엑셀·스프레드시트·종이 문서·PDF 캡처 등 **형식이 제각각인** 표/목록에서 조사 대상 **지번·주소**를 행 단위로 추출한다.",
        "",
        "[OCR 힌트]",
        "- 아래 OCR은 기기에서 미리 읽은 원문이다. **글자·숫자 판독은 OCR을 우선 참고**하고, 이미지는 **행 순서·셀 경계·누락 여부** 확인용으로 쓴다.",
        "- OCR과 이미지가 충돌하면, 표에 **실제로 보이는 내용**만 근거로 삼는다. 보이지 않는 글자는 채우지 않는다.",
        *ocr_lines,
        "",
        "[주소 완성 — 한국 표준]",
        "- 행·열 형식은 사용자마다 다르다. 열 이름·순서에 얽매이지 말고, **한 필지(한 행)당 검색·장부에 쓸 완성 주소 한 줄**을 만든다.",
        "- 시·군·구, 읍·면·동·리, 산(임야), 본번·부번(예: 123-4) 등 **한국 지번·도로명 주소 체계**에 맞게 인접 셀·열을 이어 붙인다.",
        "- 같은 행에 흩어진 조각만 합친다. **추측으로 시·군·구·동·리·번지를 보충하지 않는다.**",
        "- 중복 공백·불필요한 쉼표는 정리한다.",
        "",
        "[중복 주소 — 필수]",
        "- **동일한 주소 문자열이 여러 행에 반복되어도 하나만 남기지 않는다.**",
        "- 표·목록에 보이는 **행마다 rows에 한 항목씩** 넣는다(중복 포함, 생략·병합·dedupe 금지).",
        "",
        "[불확실]",
        f'- 지번·주소를 표에 보이는 범위 안에서 **확신할 수 없으면** `address`에 정확히 "{_UNCERTAIN}"만 넣는다(다른 단어·영문 금지).',
        "- 불확실한 이유가 있으면 `note`에 짧게 적고, 확실하면 `note`는 비고 열 내용만 넣거나 빈 문자열.",
        "",
        "규칙:",
        "- 위→아래(또는 문서 읽기 순)로 행을 나열한다.",
        "- 순번·번호 열이 보이면 `seq`에 넣고, 없으면 빈 문자열.",
        "- 순번이 있는 행은 **숫자 순번 오름차순**이 되도록 `rows`를 구성한다.",
        "- 출력은 JSON 객체 한 개만. 마크다운·코드펜스·설명 문장 바깥 텍스트 금지.",
        '- 최상위 키는 반드시 "rows" 배열.',
        f"- 사용자가 보낸 이미지는 {count}장이다. 모든 이미지를 합쳐 **하나의 rows 배열**로 출력한다(이미지별 분리 금지).",
        "",
        "형식 예시:",
        json.dumps(example, ensure_ascii=False, indent=2),
    ])


def _mode(body, feature: str, kind: str) -> str:
    if feature == WRITE:
        return "write"
    if feature == SHEET:
        return "sheet"
    raw = str(getattr(body, "mode", None) or kind or "short").strip().lower()
    return raw if raw in ("short", "long") else "short"


def _hint_map(raw) -> dict[int, str]:
    if raw is None or raw == "":
        return {}
    if isinstance(raw, str):
        return {1: _limit_text(raw, _NOTE_CAP)}
    if not isinstance(raw, list):
        _invalid()
    hints = {}
    for item in raw:
        if not isinstance(item, dict):
            _invalid()
        hints[int(item.get("order") or 1)] = _limit_text(str(item.get("text") or ""), _NOTE_CAP)
    return hints


def _ordered_images(items) -> list[tuple[int, str | None, str]]:
    rows = []
    seen = set()
    for index, item in enumerate(items or [], start=1):
        if isinstance(item, str):
            order, label, url = index, None, item
        elif isinstance(item, dict):
            order = int(item.get("order") or index)
            label = str(item.get("label")).strip() if item.get("label") else None
            url = item.get("image") or item.get("url") or ""
        else:
            _invalid()
            continue
        url = _data_url(url)
        if url in seen:
            continue
        seen.add(url)
        rows.append((order, label, url))
    rows.sort(key=lambda row: row[0])
    return rows


def _messages(mode: str, text: str, images: list[str]) -> list:
    return [
        {"role": "system", "content": _system(mode)},
        {"role": "user", "content": _user_content(text, images, _detail(mode, len(images)))},
    ]


def _finish(mode: str, text: str, images: list[str], feature: str) -> PreparedCall:
    cap = _PHOTO_CAP.get(mode, 0)
    if feature in (PHOTO, SHEET) and not images:
        _invalid()
    if feature == WRITE and images:
        _invalid()
    if len(images) > cap:
        _invalid()
    if not images and not text.strip():
        _invalid()
    temperature = 0.1 if mode == "sheet" else 0.15
    response_format = None if mode == "write" else {"type": "json_object"}
    units = len(images) if feature == PHOTO else 1
    return PreparedCall(_messages(mode, text, images), units, _model(), temperature, _output_tokens(), response_format)


def prepare_fieldnote_call(body, feature: str, kind: str) -> PreparedCall:
    mode = _mode(body, feature, kind)
    if getattr(body, "format", None) == 2:
        return _prepare_v2(body, feature, mode)
    if not settings.fieldnote_ai_accept_legacy_format:
        _invalid()
    text, images = _legacy_parts(getattr(body, "messages", None))
    text = _limit_text(text, _LEGACY_TEXT_CAP)
    return _finish(mode, text, images, feature)


def _prepare_v2(body, feature: str, mode: str) -> PreparedCall:
    if feature == PHOTO:
        rows = _ordered_images(getattr(body, "photos", None))
        note = _limit_text(str(getattr(body, "note", None) or ""), _NOTE_CAP)
        hints = _hint_map(getattr(body, "ocr_hints", None))
        text = _record_prompt(mode, [(order, label) for order, label, _url in rows], note, hints)
        return _finish(mode, text, [url for _order, _label, url in rows], feature)
    if feature == SHEET:
        rows = _ordered_images(getattr(body, "images", None))
        hint = _limit_text(str(getattr(body, "hint", None) or ""), _NOTE_CAP)
        hints = {1: hint} if hint else {}
        text = _sheet_prompt(len(rows), hints)
        return _finish(mode, text, [url for _order, _label, url in rows], feature)
    source = _limit_text(str(getattr(body, "source_text", None) or ""), _WRITE_CAP)
    return _finish(mode, source, [], feature)
