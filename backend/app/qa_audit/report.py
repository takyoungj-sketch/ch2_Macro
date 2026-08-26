"""엔진 JSON → 사람이 읽는 보고 (LLM 없음. 수치 재발명 금지)."""

from __future__ import annotations

from typing import Any


def format_report(run: dict[str, Any]) -> str:
    diffs = run.get("diffs") or {}
    metrics = diffs.get("metrics") or {}
    lines = [
        "CH2 Macro QA 검증 (엔진 보고 · AI 재계산 아님)",
        "AI는 검증값을 생성하지 않으며, 검증 결과의 해석과 원인 분석에만 사용합니다.",
        f"판정: {run.get('verdict_ui') or run.get('verdict')}",
        f"대상: {run.get('region_name') or ''} {run.get('region_code')} "
        f"{run.get('region_level')} / {run.get('asset_type')} / {run.get('period_key')}",
        f"모드: {run.get('trigger')}  engine={run.get('engine_version')}",
        "",
        f"{'항목':<12} {'L1 원장':>14} {'L3 빌더':>14} {'저장 마트':>14} {'ΔL1-마트':>12} {'판정':<8}",
        "-" * 80,
    ]
    labels = {
        "n": "거래건수",
        "n_enriched": "보강조인",
        "sum_price": "금액합(만원)",
        "mean_price": "평균단가",
        "median_price": "중위단가",
    }
    for key, label in labels.items():
        m = metrics.get(key)
        if not m:
            continue
        lines.append(
            f"{label:<12} {_fmt(m.get('l1')):>14} {_fmt(m.get('l3')):>14} "
            f"{_fmt(m.get('mart')):>14} {_fmt(m.get('delta_l1_mart')):>12} "
            f"{m.get('grade') or '':<8}"
        )
        if m.get("reason"):
            lines.append(f"             {m['reason']}")
    checks = diffs.get("checks") or []
    if checks:
        lines.append("")
        lines.append("검증항목")
        for c in checks:
            lines.append(f"  {c.get('label')}: {c.get('grade')} — {c.get('detail')}")
    n_m = metrics.get("n") or {}
    if n_m:
        lines.append("")
        en = metrics.get("n_enriched") or {}
        if en:
            lines.append(
                f"원장 유효: {n_m.get('l1')}건 · 해시유일: {n_m.get('l3')}건 · "
                f"보강조인: {en.get('mart') if en.get('mart') is not None else en.get('l3')}건"
            )
        else:
            lines.append(
                f"원장 유효: {n_m.get('l1')}건 · 재계산: {n_m.get('l3')}건 · "
                f"기존 Mart: {_fmt(n_m.get('mart'))}건 · 차이: {_fmt(n_m.get('delta_l1_mart'))}건"
            )
    lines.append("")
    l2 = run.get("l2") or {}
    chain = l2.get("drop_chain") or {}
    if chain:
        lines.append(
            "L2 정제 추적: "
            f"전체 {chain.get('n_all')} → 무효 {chain.get('n_invalid')} → "
            f"단가제외 {chain.get('n_excluded_unit_price')} → "
            f"L1대상 {chain.get('n_l1_eligible')} "
            f"(needs_review {l2.get('n_needs_review')})"
        )
    causes = diffs.get("cause_candidates") or []
    if causes:
        lines.append("원인 후보:")
        for c in causes:
            lines.append(f"  - {c}")
    lines.append("원장·마트는 변경하지 않았습니다. 수정은 생산 파이프라인에서.")
    return "\n".join(lines)


def _fmt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:,.2f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)
