"""L1 / L3 / 저장 마트 세 칸 대조 → PASS | REVIEW | ERROR | BLOCK | SKIP."""

from __future__ import annotations

from typing import Any, Literal

Verdict = Literal["PASS", "REVIEW", "ERROR", "BLOCK", "SKIP"]

RANK: dict[str, int] = {
    "SKIP": -1,
    "PASS": 0,
    "REVIEW": 1,
    "ERROR": 2,
    "BLOCK": 3,
}

SUM_EPS = 1.0  # 만원
MEAN_EPS = 0.15  # 단가 소수 1자리 반올림 여유
N_BLOCK_ABS = 20
N_BLOCK_RATIO = 0.05


def worst(*grades: str) -> str:
    picked = "PASS"
    best_rank = RANK["PASS"]
    saw_skip = False
    for g in grades:
        if g == "SKIP":
            saw_skip = True
            continue
        r = RANK.get(g, RANK["REVIEW"])
        if r > best_rank:
            best_rank = r
            picked = g
    if saw_skip and best_rank <= RANK["PASS"] and not any(
        g in ("PASS", "REVIEW", "ERROR", "BLOCK") for g in grades
    ):
        return "SKIP"
    if saw_skip and all(g == "SKIP" for g in grades):
        return "SKIP"
    return picked


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _max_abs_diff(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return max(abs(a - b) for a in values for b in values)


def grade_n(
    l1: int | None,
    l3: int | None,
    mart: int | None,
    *,
    specified: bool,
) -> tuple[str, str]:
    """건수는 0건 차이만 PASS. 빈 표본은 SKIP."""
    vals = [v for v in (l1, l3, mart) if v is not None]
    if not vals:
        return "BLOCK", "건수 산출 실패"
    if all(v == 0 for v in vals) and (mart in (None, 0)):
        return "SKIP", "대상 기간 유효 거래 0건"
    if l1 == 0 and (l3 in (None, 0)) and (mart in (None, 0)):
        return "SKIP", "대상 기간 유효 거래 0건"

    if mart is None and (l1 or 0) > 0:
        gap = l1 or 0
        if gap >= N_BLOCK_ABS:
            return "BLOCK", "저장 마트 행 없음 (원장 유효 건 존재)"
        return "ERROR", "저장 마트 행 없음 (원장 유효 건 존재)"

    present = [v for v in (l1, l3, mart) if v is not None]
    if len(set(present)) == 1:
        return "PASS", "건수 세 칸 일치"

    spread = _max_abs_diff([float(v) for v in present])
    base = max(v for v in present if v is not None) or 0
    if spread >= N_BLOCK_ABS or (base > 0 and spread / base >= N_BLOCK_RATIO):
        return "BLOCK", f"건수 괴리 {int(spread)}건"

    if l1 is not None and mart is not None and l1 != mart:
        return "ERROR", "원장 재집계와 저장 마트 건수 불일치"
    if l3 is not None and mart is not None and l3 != mart:
        return "ERROR", "빌더 재실행과 저장 마트 건수 불일치"
    if l1 is not None and l3 is not None and l1 != l3:
        return "ERROR", "원장 필터와 빌더 매핑 건수 불일치"
    return "REVIEW", "건수 차이 (원인 확인)"


def grade_sum(l1: float | None, l3: float | None, mart: float | None) -> tuple[str, str]:
    present = [v for v in (_f(l1), _f(l3), _f(mart)) if v is not None]
    if not present:
        return "REVIEW", "금액 합 없음"
    if _max_abs_diff(present) <= SUM_EPS:
        return "PASS", "금액 합 허용 오차 이내"
    spread = _max_abs_diff(present)
    return "REVIEW", f"금액 합 차이 {spread:.1f}만원 (반올림·필터 가능 — 원인 확인)"


def grade_stat(
    name: str,
    l1: float | None,
    l3: float | None,
    mart: float | None,
    *,
    n_grade: str,
    l2_explains: bool,
) -> tuple[str, str]:
    present = [v for v in (_f(l1), _f(l3), _f(mart)) if v is not None]
    if not present:
        return "REVIEW", f"{name} 없음"
    if _max_abs_diff(present) <= MEAN_EPS:
        return "PASS", f"{name} 허용 오차 이내"
    if n_grade == "PASS" and not l2_explains:
        return "REVIEW", f"{name} 차이 (제외 사유 미추적)"
    if n_grade == "PASS" and l2_explains:
        return "REVIEW", f"{name} 차이 (L2 제외 후보 있음)"
    return "REVIEW", f"{name} 차이"


def compare_metrics(
    l1: dict[str, Any],
    l3: dict[str, Any],
    mart: dict[str, Any],
    *,
    l2: dict[str, Any] | None = None,
    specified: bool = True,
    l3_error: str | None = None,
) -> dict[str, Any]:
    """지표별 등급 + 종합 판정."""
    if l3_error:
        return {
            "verdict": "BLOCK",
            "verdict_ui": "ERROR",
            "metrics": {
                "n": {"grade": "BLOCK", "reason": l3_error},
            },
            "checks": _checks_on_l3_error(l3_error),
            "cause_candidates": [f"L3 빌더 예외: {l3_error}"],
        }

    l2 = l2 or {}
    l2_explains = bool(
        (l2.get("n_excluded_unit_price") or 0)
        or (l2.get("n_needs_review") or 0)
        or (l2.get("n_invalid") or 0)
        or (l2.get("n_bad_region_code") or 0)
    )

    n_l1 = _i(l1.get("n"))
    n_l3 = _i(l3.get("n")) if l3.get("available", True) else None
    n_mart = _i(mart.get("n")) if not mart.get("missing") else None

    n_grade, n_reason = grade_n(n_l1, n_l3, n_mart, specified=specified)
    if n_grade == "SKIP":
        return {
            "verdict": "SKIP",
            "verdict_ui": "SKIP",
            "metrics": {
                "n": {
                    "grade": "SKIP",
                    "reason": n_reason,
                    "l1": n_l1,
                    "l3": n_l3,
                    "mart": n_mart,
                    "delta_l1_mart": None,
                }
            },
            "checks": [],
            "cause_candidates": ["대상 기간 유효 거래 없음 — 랜덤이면 재추출"],
        }

    s_grade, s_reason = grade_sum(
        _f(l1.get("sum_price")),
        _f(l3.get("sum_price")) if l3.get("available", True) else None,
        _f(mart.get("sum_price")) if not mart.get("missing") else None,
    )
    m_grade, m_reason = grade_stat(
        "평균단가",
        _f(l1.get("mean_price")),
        _f(l3.get("mean_price")) if l3.get("available", True) else None,
        _f(mart.get("mean_price")) if not mart.get("missing") else None,
        n_grade=n_grade,
        l2_explains=l2_explains,
    )
    d_grade, d_reason = grade_stat(
        "중위단가",
        _f(l1.get("median_price")),
        _f(l3.get("median_price")) if l3.get("available", True) else None,
        _f(mart.get("median_price")) if not mart.get("missing") else None,
        n_grade=n_grade,
        l2_explains=l2_explains,
    )

    causes = _cause_candidates(l1, l3, mart, l2, n_grade)
    verdict = worst(n_grade, s_grade, m_grade, d_grade)
    checks = build_checks(
        l1=l1,
        l2=l2,
        l3=l3,
        mart=mart,
        n_grade=n_grade,
        n_reason=n_reason,
        s_grade=s_grade,
    )
    return {
        "verdict": verdict,
        "verdict_ui": "ERROR" if verdict == "BLOCK" else verdict,
        "metrics": {
            "n": _metric_row(n_grade, n_reason, n_l1, n_l3, n_mart, is_int=True),
            "sum_price": _metric_row(
                s_grade,
                s_reason,
                _f(l1.get("sum_price")),
                _f(l3.get("sum_price")) if l3.get("available", True) else None,
                _f(mart.get("sum_price")) if not mart.get("missing") else None,
            ),
            "mean_price": _metric_row(
                m_grade,
                m_reason,
                _f(l1.get("mean_price")),
                _f(l3.get("mean_price")) if l3.get("available", True) else None,
                _f(mart.get("mean_price")) if not mart.get("missing") else None,
            ),
            "median_price": _metric_row(
                d_grade,
                d_reason,
                _f(l1.get("median_price")),
                _f(l3.get("median_price")) if l3.get("available", True) else None,
                _f(mart.get("median_price")) if not mart.get("missing") else None,
            ),
        },
        "checks": checks,
        "cause_candidates": causes,
    }


def _metric_row(
    grade: str,
    reason: str,
    l1: float | int | None,
    l3: float | int | None,
    mart: float | int | None,
    *,
    is_int: bool = False,
) -> dict[str, Any]:
    def _delta(a, b):
        if a is None or b is None:
            return None
        return (int(a) - int(b)) if is_int else round(float(a) - float(b), 4)

    return {
        "grade": grade,
        "reason": reason,
        "l1": l1,
        "l3": l3,
        "mart": mart,
        "delta_l1_mart": _delta(l1, mart),
        "delta_l3_mart": _delta(l3, mart),
        "delta_l1_l3": _delta(l1, l3),
    }


def _check(id_: str, label: str, grade: str, detail: str) -> dict[str, str]:
    ui = "ERROR" if grade == "BLOCK" else grade
    return {"id": id_, "label": label, "grade": ui, "detail": detail}


def _checks_on_l3_error(err: str) -> list[dict[str, str]]:
    return [
        _check("l3_recompute", "Mart 재계산", "ERROR", err),
        _check("mart_compare", "기존 Mart 대조", "ERROR", "재계산 실패로 대조 불가"),
    ]


def build_checks(
    *,
    l1: dict[str, Any],
    l2: dict[str, Any],
    l3: dict[str, Any],
    mart: dict[str, Any],
    n_grade: str,
    n_reason: str,
    s_grade: str,
) -> list[dict[str, str]]:
    """화면용 검증항목. 수치는 인자 JSON만 인용한다."""
    n_all = l2.get("n_all")
    n_elig = l2.get("n_l1_eligible")
    n_l1 = l1.get("n")
    n_l3 = l3.get("n") if l3.get("available", True) else None
    n_mart = None if mart.get("missing") else mart.get("n")
    n_inv = int(l2.get("n_invalid") or 0)
    n_dup = int(l2.get("n_hash_dup_groups") or 0)
    n_bad = int(l2.get("n_bad_region_code") or 0)
    n_excl = int(l2.get("n_excluded_unit_price") or 0)

    clean_grade = "PASS"
    clean_detail = f"원장 전체 {n_all} → 유효·단가통과 {n_elig}"
    if n_elig is not None and n_l1 is not None and int(n_elig) != int(n_l1):
        clean_grade = "REVIEW"
        clean_detail += f" · L1 재집계 {n_l1}과 불일치"

    valid_grade = "PASS" if n_inv == 0 else "REVIEW"
    valid_detail = f"is_valid=false {n_inv}건 · 단가제외 {n_excl}건"

    dup_grade = "PASS" if n_dup == 0 else "REVIEW"
    dup_detail = (
        f"hash 중복 그룹 {n_dup} (집합은 의미 중복 제거 없음)"
        if n_dup
        else "hash 중복 그룹 0"
    )

    code_grade = "PASS" if n_bad == 0 else "REVIEW"
    code_detail = f"지역코드 비정상 {n_bad}건"

    type_grade = "PASS"
    type_detail = f"요청 유형만 집계 · L1 {n_l1}건"
    if l1.get("asset_type") and l3.get("market_domain"):
        type_detail += f" · 마트 {l3.get('market_domain') or mart.get('market_domain')}"

    if l3.get("error") or l3.get("available") is False:
        l3_grade = "ERROR" if l3.get("error") else "REVIEW"
        l3_detail = str(l3.get("error") or l3.get("reason") or "L3 생략")
    elif n_l1 is not None and n_l3 is not None and int(n_l1) == int(n_l3):
        l3_grade = "PASS"
        l3_detail = f"빌더 재실행 {n_l3}건 (마트 WRITE 없음)"
    elif n_l3 is None:
        l3_grade = "REVIEW"
        l3_detail = "L3 건수 없음"
    else:
        l3_grade = "ERROR"
        l3_detail = f"원장 {n_l1} ≠ 재계산 {n_l3}"

    if mart.get("missing"):
        mart_grade = "ERROR" if (n_l1 or 0) > 0 else "REVIEW"
        mart_detail = "저장 마트 행 없음"
    elif n_grade == "PASS":
        mart_grade = "PASS" if s_grade == "PASS" else "REVIEW"
        mart_detail = (
            f"저장 마트 {n_mart}건"
            if s_grade == "PASS"
            else f"건수 일치 · 금액은 {s_grade}"
        )
    else:
        mart_grade = n_grade
        mart_detail = n_reason

    return [
        _check("ledger_n", "원장 거래건수", n_grade, f"L1 유효 {n_l1}건 · {n_reason}"),
        _check("clean_n", "정제 후 거래건수", clean_grade, clean_detail),
        _check("valid", "유효 데이터", valid_grade, valid_detail),
        _check("dup", "중복 데이터", dup_grade, dup_detail),
        _check("region_code", "지역코드", code_grade, code_detail),
        _check("asset_type", "유형 분류", type_grade, type_detail),
        _check("l3_recompute", "Mart 재계산", l3_grade, l3_detail),
        _check("mart_compare", "기존 Mart 대조", mart_grade, mart_detail),
    ]


def _cause_candidates(
    l1: dict[str, Any],
    l3: dict[str, Any],
    mart: dict[str, Any],
    l2: dict[str, Any],
    n_grade: str,
) -> list[str]:
    out: list[str] = []
    if n_grade in ("ERROR", "BLOCK", "REVIEW"):
        if l1.get("n") is not None and mart.get("missing"):
            out.append("원천(원장)에는 유효 건이 있으나 통계 마트 행이 없음")
        if (
            l1.get("n") is not None
            and l3.get("n") is not None
            and l1.get("n") != l3.get("n")
        ):
            out.append(
                "원장 지역코드 필터와 빌더 LATERAL 매핑이 다른 행을 고른 후보"
            )
        if (
            l3.get("n") is not None
            and not mart.get("missing")
            and l3.get("n") != mart.get("n")
        ):
            out.append("마트 as_of/부분 빌드·캐시 불일치 후보")
        if l2.get("n_excluded_unit_price"):
            out.append(
                f"단가 결측·0 제외 {l2['n_excluded_unit_price']}건 — 마트 필터와 원장 차이 확인"
            )
        if l2.get("n_needs_review"):
            out.append(f"needs_review {l2['n_needs_review']}건")
        if l2.get("n_invalid"):
            out.append(f"is_valid=false {l2['n_invalid']}건")
        if l2.get("n_bad_region_code"):
            out.append(f"지역코드 비정상 {l2['n_bad_region_code']}건")
        if l2.get("n_hash_dup_groups"):
            out.append(
                f"transaction_hash 중복 그룹 {l2['n_hash_dup_groups']} "
                f"(집합은 의미 중복 제거를 하지 않음 — 참고)"
            )
    if not out and n_grade == "PASS":
        out.append("세 칸 건수 일치 — 전국 보증이 아님")
    return out
