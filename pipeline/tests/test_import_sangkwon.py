from types import SimpleNamespace

import pytest

from pipeline.rent.import_sangkwon import (
    ImportValidationError,
    RETAIL_ASSETS,
    _is_local_engine,
    align_office_codes,
    validate_facts,
)


def _fact(asset: str, year: int, quarter: int, name: str = "서울", code: str = "1234567") -> dict:
    return {
        "asset_kind": asset,
        "year": year,
        "quarter": quarter,
        "sec_nm": name,
        "reb_code": code,
    }


def _retail_facts(*quarters: tuple[int, int]) -> list[dict]:
    return [_fact(asset, year, quarter) for asset in RETAIL_ASSETS for year, quarter in quarters]


def test_validate_facts_joins_office_q3_and_keeps_retail_history() -> None:
    office_history = [_fact("office", 2026, 2)]
    office_latest = [_fact("office", 2026, 2), _fact("office", 2026, 3)]
    retail_history = _retail_facts((2026, 1), (2026, 2))
    retail_latest = _retail_facts((2026, 1), (2026, 2), (2026, 3))

    facts = validate_facts(office_history, office_latest, retail_history, retail_latest)

    assert [(row["year"], row["quarter"]) for row in facts if row["asset_kind"] == "office"] == [
        (2026, 2),
        (2026, 3),
    ]
    assert len(facts) == len(office_history) + len(retail_latest) + 1


def test_validate_facts_rejects_office_code_length_change() -> None:
    with pytest.raises(ImportValidationError, match="코드 자릿수"):
        validate_facts(
            [_fact("office", 2026, 2, code="1234567")],
            [_fact("office", 2026, 3, code="12345678")],
            _retail_facts((2026, 2)),
            _retail_facts((2026, 2), (2026, 3)),
        )


def test_align_office_codes_uses_q3_code_for_same_region() -> None:
    history = [_fact("office", 2026, 2, name="공덕역", code="1114024")]
    latest = [_fact("office", 2026, 3, name="공덕역", code="11114120")]

    aligned, remapped = align_office_codes(history, latest)

    assert remapped == 1
    assert aligned[0]["reb_code"] == "11114120"


def test_validate_facts_rejects_retail_history_shrink() -> None:
    with pytest.raises(ImportValidationError, match="과거 분기가 줄었습니다"):
        validate_facts(
            [_fact("office", 2026, 2)],
            [_fact("office", 2026, 3)],
            _retail_facts((2026, 1), (2026, 2)),
            _retail_facts((2026, 2), (2026, 3)),
        )


@pytest.mark.parametrize("host, expected", [("localhost", True), ("127.0.0.1", True), ("db.prod", False)])
def test_only_local_database_hosts_are_allowed(host: str, expected: bool) -> None:
    engine = SimpleNamespace(url=SimpleNamespace(host=host))
    assert _is_local_engine(engine) is expected
