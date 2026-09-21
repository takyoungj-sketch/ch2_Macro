"""연립·다세대 층 효용 0차 — building_key 적격 표.

재실행 (backend에서):
  python -m app.rowhouse_lab.floor_elevator_screen
  python -m app.rowhouse_lab.floor_elevator_screen --screen-only
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection, Engine

from app.collective.db import get_collective_engine
from app.land_lab.area_elasticity_screen import period_bounds_for_window
from app.rowhouse_lab.floor_elevator import (
    ASSET_TYPE,
    EXP1_N_MIN,
    N_SENSITIVITY,
    REGION_TYPES,
    WINDOW_YEARS,
    classify_region_type,
    exp1_gate,
    ident_window_45,
    n_tier_flags,
)
from app.rowhouse_lab.floor_elevator_fit import run_phase1, run_phase2a, run_phase2b, run_phase3
from app.rowhouse_lab.floor_elevator_attach import attach_elevator, purpose_by_building, write_attach_csv

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "lab" / "rowhouse_floor_elevator_screen.json"
KEEP_LAB_KEYS = (
    "verdict",
    "answers",
    "next",
    "limits",
    "resume",
    "phase1",
    "elevator",
    "phase2b",
    "phase2a",
    "phase3",
)


def latest_as_of_month(conn: Connection) -> date:
    raw = conn.execute(
        text(
            """
            SELECT MAX(contract_date)::date
            FROM collective_transactions
            WHERE is_valid = TRUE
              AND asset_type = :asset
              AND contract_date IS NOT NULL
            """
        ),
        {"asset": ASSET_TYPE},
    ).scalar()
    if raw is None:
        raise RuntimeError("연립·다세대 contract_date 없음")
    d = raw if isinstance(raw, date) else date.fromisoformat(str(raw)[:10])
    return date(d.year, d.month, 1)


def build_screen_sql() -> str:
    return """
        WITH tx AS (
            SELECT
                t.building_key,
                t.display_name,
                t.addr1,
                t.addr2,
                t.addr3,
                t.sigungu_code,
                t.sido_code,
                t.housing_subtype,
                t.building_year,
                t.floor,
                t.exclusive_area,
                t.unit_price
            FROM collective_transactions t
            WHERE t.asset_type = :asset
              AND t.is_valid = TRUE
              AND t.contract_date >= :p_start
              AND t.contract_date <= :p_end
              AND t.unit_price > 0
              AND t.exclusive_area > 0
              AND t.floor IS NOT NULL
        ),
        mx AS (
            SELECT building_key, MAX(floor)::float8 AS max_floor_tx, COUNT(*)::int AS n_raw
            FROM tx
            GROUP BY building_key
        )
        SELECT
            t.building_key,
            MAX(t.display_name) AS display_name,
            MAX(t.addr1) AS addr1,
            MAX(t.addr2) AS addr2,
            MAX(t.addr3) AS addr3,
            MAX(t.sigungu_code) AS sigungu_code,
            MAX(t.sido_code) AS sido_code,
            MAX(t.housing_subtype) AS housing_subtype,
            COUNT(*)::int AS n,
            COUNT(*) FILTER (WHERE t.floor = 1)::int AS n_1,
            COUNT(*) FILTER (
                WHERE t.floor > 1 AND t.floor < m.max_floor_tx
            )::int AS n_mid,
            COUNT(*) FILTER (
                WHERE t.floor = m.max_floor_tx AND m.max_floor_tx >= 2
            )::int AS n_top,
            COUNT(*) FILTER (WHERE t.floor < 1)::int AS n_below,
            m.max_floor_tx,
            COUNT(DISTINCT t.floor)::int AS n_floor_values,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.exclusive_area)::float8 AS median_area,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.building_year)::float8 AS median_year
        FROM tx t
        JOIN mx m ON m.building_key = t.building_key
        GROUP BY t.building_key, m.max_floor_tx
    """


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:
        return None
    return x


def row_from_agg(r: dict[str, Any]) -> dict[str, Any]:
    n = int(r.get("n") or 0)
    n_1 = int(r.get("n_1") or 0)
    n_mid = int(r.get("n_mid") or 0)
    n_top = int(r.get("n_top") or 0)
    mx = _f(r.get("max_floor_tx"))
    sido = str(r.get("addr1") or "")
    sigungu = str(r.get("addr2") or "")
    rt = classify_region_type(sido, sigungu)
    flags = n_tier_flags(n)
    eligible = exp1_gate(n=n, n_1=n_1, n_mid=n_mid, max_floor=mx, n_min=EXP1_N_MIN)
    rec = {
        "building_key": str(r.get("building_key") or "").strip(),
        "display_name": str(r.get("display_name") or "").strip(),
        "sido_name": sido,
        "sigungu_name": sigungu,
        "addr3": str(r.get("addr3") or "").strip() or None,
        "housing_subtype": str(r.get("housing_subtype") or "").strip() or None,
        "region_type": rt,
        "n": n,
        "n_1": n_1,
        "n_mid": n_mid,
        "n_top": n_top,
        "n_below": int(r.get("n_below") or 0),
        "max_floor_tx": mx,
        "n_floor_values": int(r.get("n_floor_values") or 0),
        "median_area": _f(r.get("median_area")),
        "median_year": _f(r.get("median_year")),
        "eligible": eligible,
        "ident_45": ident_window_45(mx),
        **flags,
    }
    return rec


def fetch_phase1_tx_sql() -> str:
    """적격 building_key expanding IN. ANY 금지."""
    return """
        SELECT
            t.building_key,
            t.floor,
            t.exclusive_area,
            t.unit_price,
            t.contract_year,
            t.contract_month,
            t.addr1,
            t.addr2,
            t.housing_subtype,
            t.beopjungri_code,
            t.lot_number,
            t.building_year
        FROM collective_transactions t
        WHERE t.asset_type = :asset
          AND t.is_valid = TRUE
          AND t.contract_date >= :p_start
          AND t.contract_date <= :p_end
          AND t.unit_price > 0
          AND t.exclusive_area > 0
          AND t.floor >= 1
          AND t.building_key IN :building_keys
    """


def fetch_phase1_tx(
    conn: Connection,
    *,
    keys: list[str],
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:
    cleaned = [str(k).strip() for k in keys if str(k).strip()]
    if not cleaned:
        return []
    sql = fetch_phase1_tx_sql()
    if len(cleaned) == 1:
        sql = sql.replace("AND t.building_key IN :building_keys", "AND t.building_key = :building_key")
        rows = conn.execute(
            text(sql),
            {
                "asset": ASSET_TYPE,
                "p_start": period_start,
                "p_end": period_end,
                "building_key": cleaned[0],
            },
        ).mappings().all()
        return [dict(r) for r in rows]
    stmt = text(sql).bindparams(bindparam("building_keys", expanding=True))
    rows = conn.execute(
        stmt,
        {
            "asset": ASSET_TYPE,
            "p_start": period_start,
            "p_end": period_end,
            "building_keys": cleaned,
        },
    ).mappings().all()
    return [dict(r) for r in rows]


def _dir_ko(d: str) -> str:
    return {"plus": "가산", "minus": "감가", "ns": "유의하지 않음", "split": "갈림", "na": "추정 실패"}.get(d, d)


def _pct_ko(pct: float | None) -> str:
    if pct is None:
        return "—"
    return f"{pct * 100:.1f}%"


def apply_phase1_copy(copy: dict[str, Any], summary: dict[str, Any], phase1: dict[str, Any]) -> None:
    pooled = phase1.get("pooled") or {}
    delta = phase1.get("building_delta") or {}
    agree_mid = str(phase1.get("type_agree_mid") or "na")
    agree_top = str(phase1.get("type_agree_top") or "na")
    n_sig_mid = ",".join(f"n≥{t}" for t in (phase1.get("n_sig_mid") or [])) or "없음"
    n_sig_top = ",".join(f"n≥{t}" for t in (phase1.get("n_sig_top") or [])) or "없음"
    type_sig_mid = ",".join(phase1.get("type_sig_mid") or []) or "없음"
    type_sig_top = ",".join(phase1.get("type_sig_top") or []) or "없음"
    label = (
        f"실험 1. 최상은 유형에서 {_dir_ko(agree_top)}이 모인다. "
        f"중간은 풀에서 작고 n≥20부터 ns. 전국 한 γ 아님. 제품 식 미변경."
    )
    copy["verdict"]["code"] = "phase1"
    copy["verdict"]["label"] = label
    copy["verdict"]["choices"] = [
        {
            "id": "national-gamma",
            "label": "전국 한 층 효과를 본결과로 쓴다",
            "selected": False,
            "why": f"중간 유의 유형={type_sig_mid}. 최상 유의 유형={type_sig_top}. 풀 γ는 참고만.",
        },
        {
            "id": "product-formula",
            "label": "연립 효용지수 기본 칸을 지금 바꾼다",
            "selected": False,
            "why": "실험 1만. 중간은 n에 약하다. 승강기 2a·2b 전. D-xxx 없음.",
        },
        {
            "id": "keep-fe",
            "label": "층은 건물 FE, 승강기는 건물 사이로 나눈다",
            "selected": True,
            "why": "승강기는 아직 미부착. FE와 주효과를 한 식에 넣지 않는다.",
        },
    ]
    copy["answers"] = [
        {
            "q": "비교가능 연립·다세대 건물이 있는가",
            "a": (
                f"스캔 {summary['n_buildings_scanned']} · 적격 {summary['n_eligible']} · "
                f"n≥20 {summary['n_sensitivity'].get('20', 0)} · "
                f"n≥50 {summary['n_ge_50']} · 4~5층 {summary['n_ident_45']}"
            ),
            "evidence": "창 5년. 단가·γ로 고르지 않음. 승강기 미부착.",
        },
        {
            "q": "같은 건물에서 중간·최상 단가가 1층과 다른가",
            "a": (
                f"풀 중간 {_dir_ko(str(pooled.get('dir_mid')))} {_pct_ko(pooled.get('pct_mid'))} "
                f"(p={pooled.get('p_mid')}) · 최상 {_dir_ko(str(pooled.get('dir_top')))} "
                f"{_pct_ko(pooled.get('pct_top'))} (p={pooled.get('p_top')}). "
                f"중간 유의 n={n_sig_mid} · 최상 유의 n={n_sig_top}."
            ),
            "evidence": (
                f"n={pooled.get('n')} · 건물 {pooled.get('n_buildings')}. "
                f"중간 유의 유형={type_sig_mid} · 최상 유의 유형={type_sig_top}. "
                "ln(단가)=FE+중간+최상+ln(면적)+반기. 연식 없음. 승강기 없음."
            ),
        },
        {
            "q": "건물 중위 Δ와 FE 부호가 같은가",
            "a": (
                f"중간 중위 Δ {_pct_ko(delta.get('median_delta_mid'))} "
                f"(가산 {delta.get('n_pos_mid')}/{delta.get('n_mid')}) · "
                f"{'부호 갈림' if bool(phase1.get('sign_disagree_mid')) else '부호 같음'}."
            ),
            "evidence": "건물별 1층 vs 중간 중위 단가 비. OLS 대체 아님. 부트스트랩 95% CI는 1차 표.",
        },
    ]
    for item in copy.get("next") or []:
        if item.get("id") == "exp1-fe":
            item["status"] = "done"
    copy["limits"] = [
        "화면 회귀 탭의 금액 OLS·한 단지 p값은 파일럿이다.",
        "아파트 상대층(저·중·고 %)을 칸으로 쓰지 않았다.",
        "승강기는 아직 안 붙였다. FE와 주효과를 한 식에 넣지 않는다.",
        "전국 한 γ는 본결과가 아니다. 중간은 n≥20에서 ns. 유형 표를 본다.",
        "제품 효용지수 n≥50·상대층 기본값은 바꾸지 않았다.",
    ]
    copy["resume"] = {
        "next_id": "title-elevator",
        "title": "표제부 승강기 부착",
        "say": (
            "실험 1 기록. 최상 가산은 n·유형에서 모인다. 중간은 작고 n≥20부터 ns. "
            "다음은 표제부 [45]·[46]을 표본 행으로 검증해 붙인 뒤 2b."
        ),
        "do_not": "제품 층 칸을 바꾸지 않는다. 승강기 주효과를 FE 식에 넣지 않는다. 전수 웹검색으로 표본을 만들지 않는다.",
        "how": "계획 SSOT docs/lab/ROWHOUSE_FLOOR_ELEVATOR_LAB.md. 관리자 ?tool=rowhouse-floor.",
    }


def apply_phase2_copy(
    copy: dict[str, Any],
    summary: dict[str, Any],
    elev: dict[str, Any],
    phase2b: dict[str, Any],
    phase2a: dict[str, Any],
) -> None:
    po = (phase2b or {}).get("pooled") or {}
    bal = (phase2a or {}).get("balance") or {}
    level = (phase2a or {}).get("level") or {}
    skipped = (phase2a or {}).get("level_skipped")
    theta_top = _dir_ko(str(po.get("dir_theta_top") or "na"))
    theta_mid = _dir_ko(str(po.get("dir_theta_mid") or "na"))
    label = (
        f"실험 2b. 최상×승강기 {theta_top} {_pct_ko(po.get('pct_theta_top'))}. "
        f"중간×승강기 {theta_mid}. 2a 균형 칸 {bal.get('n_cells_both', 0)}/{bal.get('n_cells', 0)}. "
        "제품 식 미변경."
    )
    copy["verdict"]["code"] = "phase2"
    copy["verdict"]["label"] = label
    copy["verdict"]["choices"] = [
        {
            "id": "national-gamma",
            "label": "전국 한 층 효과를 본결과로 쓴다",
            "selected": False,
            "why": "실험 1·2b 모두 전국 한 숫자를 헤드라인으로 쓰지 않는다.",
        },
        {
            "id": "product-formula",
            "label": "연립 효용지수 기본 칸을 지금 바꾼다",
            "selected": False,
            "why": "2b θ와 2a 균형만. 실험 3·D-xxx 없음.",
        },
        {
            "id": "keep-fe",
            "label": "층은 건물 FE, 승강기는 건물 사이로 나눈다",
            "selected": True,
            "why": "2b는 FE+상호작용만. 2a δ는 FE 없이 수준. 한 식에 넣지 않았다.",
        },
    ]
    copy["answers"].append(
        {
            "q": "표제부 승강기를 적격 건물에 붙일 수 있는가",
            "a": (
                f"유 {elev.get('n_yes', 0)} · 무 {elev.get('n_no', 0)} · "
                f"미상 {elev.get('n_unknown', 0)} (혼합 {elev.get('n_mixed', 0)}) · "
                f"PNU {elev.get('n_pnu_hit', 0)}/{elev.get('n_pnu', 0)}"
            ),
            "evidence": "원본 [45] 승용 · [46] 비상. 표본 행으로 인덱스 검증. 제품 building 스키마 미변경.",
        }
    )
    copy["answers"].append(
        {
            "q": "승강기 있는 건물에서 윗층 기울기가 다른가",
            "a": (
                f"θ 중간 {theta_mid} {_pct_ko(po.get('pct_theta_mid'))} "
                f"(p={po.get('p_theta_mid')}) · θ 최상 {theta_top} "
                f"{_pct_ko(po.get('pct_theta_top'))} (p={po.get('p_theta_top')}). "
                f"유 {phase2b.get('n_yes')} · 무 {phase2b.get('n_no')}동."
            ),
            "evidence": "건물 FE 유지. 승강기 주효과 없음. "
            + (po.get("reason") or f"n={po.get('n')}"),
        }
    )
    if skipped:
        a2 = (
            f"4~5층 유 {bal.get('n_yes')} · 무 {bal.get('n_no')} · "
            f"양쪽 있는 칸 {bal.get('n_cells_both')}/{bal.get('n_cells')}. δ는 아직 안 읽음."
        )
        ev2 = "균형 표 게이트(유·무 각 ≥30, 양쪽 칸 ≥3) 미달. 인과 아님."
    else:
        a2 = (
            f"δ {_dir_ko(str(level.get('dir') or 'na'))} {_pct_ko(level.get('pct'))} "
            f"(p={level.get('p')}). 인과 %가 아니다."
        )
        ev2 = f"n={level.get('n')} · 건물 {level.get('n_buildings')}. FE 없음. 시군구 대신 유형+연식대+반기."
    copy["answers"].append(
        {
            "q": "비슷한 4~5층에서 승강기 유무가 단가 수준을 바꾸는가",
            "a": a2,
            "evidence": ev2,
        }
    )
    for item in copy.get("next") or []:
        if item.get("id") in {"title-elevator", "exp2b"}:
            item["status"] = "done"
        if item.get("id") == "exp2a":
            item["status"] = "done" if not skipped else "planned"
            if skipped:
                item["gate"] = "균형 표 기록. δ는 칸이 찰 때"
    copy["limits"] = [
        "화면 회귀 탭의 금액 OLS·한 단지 p값은 파일럿이다.",
        "승강기 주효과를 건물 FE와 한 식에 넣지 않았다.",
        "2a δ는 인과가 아니다. 신축·RC·규모와 같이 움직인다.",
        "6층+에서 승강기 주효과를 읽지 않았다.",
        "제품 효용지수 n≥50·상대층 기본값은 바꾸지 않았다.",
    ]
    next_id = "exp3" if not skipped else "exp2a"
    copy["resume"] = {
        "next_id": next_id,
        "title": "실험 3 구성" if not skipped else "실험 2a 균형 보강",
        "say": (
            f"2b θ 최상 {theta_top}. 2a 유 {bal.get('n_yes')} / 무 {bal.get('n_no')}. "
            + ("다음은 방향이 체급·연식에서 같은지." if not skipped else "δ는 균형 칸이 더 찰 때.")
        ),
        "do_not": "제품 층 칸을 바꾸지 않는다. 2a δ를 인과 %로 쓰지 않는다. 전수 웹검색으로 표본을 만들지 않는다.",
        "how": "계획 SSOT docs/lab/ROWHOUSE_FLOOR_ELEVATOR_LAB.md. 관리자 ?tool=rowhouse-floor.",
    }


def apply_phase3_copy(copy: dict[str, Any], phase3: dict[str, Any]) -> None:
    agree_top = str(phase3.get("agree_theta_top") or "na")
    agree_mid = str(phase3.get("agree_theta_mid") or "na")
    po = (phase3 or {}).get("pooled") or {}
    sketch = (phase3 or {}).get("sketch") or {}
    yes = sketch.get("yes") or {}
    no = sketch.get("no") or {}
    if agree_top == "split":
        headline = "실험 3. 최상×승강기 방향이 구성에서 갈린다. 전국 한 칸 금지."
    elif agree_top == "plus":
        headline = (
            f"실험 3. 최상×승강기 가산이 체급·연식·수도권에서 모인다 "
            f"({_pct_ko(po.get('pct_theta_top'))}). 제품 칸은 아직."
        )
    elif agree_top == "minus":
        headline = "실험 3. 최상×승강기 감가가 구성에서 모인다. 제품 칸은 아직."
    else:
        headline = "실험 3. 최상×승강기 구성 칸이 유의하지 않다. 제품 칸은 아직."
    copy["verdict"]["code"] = "phase3"
    copy["verdict"]["label"] = headline
    copy["verdict"]["choices"] = [
        {
            "id": "national-gamma",
            "label": "전국 한 층 효과를 본결과로 쓴다",
            "selected": False,
            "why": "실험 3은 슬라이스 합의만. 전국 한 숫자를 헤드라인으로 쓰지 않는다.",
        },
        {
            "id": "product-formula",
            "label": "연립 효용지수 기본 칸을 지금 바꾼다",
            "selected": False,
            "why": "1·2b·3 기록. D-xxx·Insight 없음. 랩 스케치만.",
        },
        {
            "id": "keep-fe",
            "label": "층은 건물 FE, 승강기는 건물 사이로 나눈다",
            "selected": True,
            "why": "적격 건물을 계수로 다시 고르지 않았다. 스케치는 2b γ+θ.",
        },
    ]
    copy["answers"].append(
        {
            "q": "층×승강기 방향이 체급·연식·수도권에서 같은가",
            "a": (
                f"θ 최상 {_dir_ko(agree_top)} · θ 중간 {_dir_ko(agree_mid)}. "
                f"합의 칸 {','.join(phase3.get('agree_slices_top') or []) or '없음'}. "
                f"기지 {phase3.get('n_known')}동 (적격 {phase3.get('n_eligible')})."
            ),
            "evidence": "같은 적격·승강기 기지 풀. 수도권=서울·경기·인천. 6층+는 참고. 연립/다세대는 표제부 용도.",
        }
    )
    copy["answers"].append(
        {
            "q": "랩 스케치(1층=100)는 어떻게 읽나",
            "a": (
                f"무승강기 중간 {no.get('mid')} · 최상 {no.get('top')} / "
                f"유승강기 중간 {yes.get('mid')} · 최상 {yes.get('top')}."
            ),
            "evidence": sketch.get("note") or "건물 안 지수. 제품 칸 아님.",
        }
    )
    for item in copy.get("next") or []:
        if item.get("id") == "exp3":
            item["status"] = "done"
    copy["limits"] = [
        "화면 회귀 탭의 금액 OLS·한 단지 p값은 파일럿이다.",
        "적격 건물을 단가·γ·θ로 다시 고르지 않았다.",
        "6층+·n≥50은 참고. 5층 무승강기는 얇을 수 있다.",
        "2a δ는 인과가 아니다. 매칭은 아직.",
        "제품 효용지수 n≥50·상대층 기본값은 바꾸지 않았다.",
    ]
    copy["resume"] = {
        "next_id": "parked-product",
        "title": "제품·Insight 보류",
        "say": (
            f"실험 3 θ 최상 {_dir_ko(agree_top)}. 랩 스케치만. "
            "다음은 제품 칸·Insight·2a 매칭을 열지 여부."
        ),
        "do_not": "제품 층 칸을 바꾸지 않는다. 전국 한 %를 Insight에 넣지 않는다. 2a δ를 인과로 쓰지 않는다.",
        "how": "계획 SSOT docs/lab/ROWHOUSE_FLOOR_ELEVATOR_LAB.md. 관리자 ?tool=rowhouse-floor.",
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [r for r in rows if r.get("eligible")]
    by_type: dict[str, dict[str, int]] = {}
    for t in REGION_TYPES:
        sub = [r for r in eligible if r.get("region_type") == t]
        by_type[t] = {
            "eligible": len(sub),
            "ident_45": sum(1 for r in sub if r.get("ident_45")),
            "n_ge_50": sum(1 for r in sub if r.get("n_ge_50")),
        }
    n_sens = {str(t): sum(1 for r in eligible if r.get(f"n_ge_{t}")) for t in N_SENSITIVITY}
    return {
        "n_buildings_scanned": len(rows),
        "n_eligible": len(eligible),
        "n_ident_45": sum(1 for r in eligible if r.get("ident_45")),
        "n_ge_50": sum(1 for r in eligible if r.get("n_ge_50")),
        "n_sensitivity": n_sens,
        "by_type": by_type,
        "elevator_attached": False,
    }


def default_lab_copy() -> dict[str, Any]:
    return {
        "verdict": {
            "code": "screen_only",
            "label": "0차 적격 표. 전국 한 층 % · 제품 식 변경은 하지 않는다.",
            "choices": [
                {
                    "id": "national-gamma",
                    "label": "전국 한 층 효과를 본결과로 쓴다",
                    "selected": False,
                    "why": "실험 1도 유형·최고층에서 부호가 갈릴 수 있다.",
                },
                {
                    "id": "product-formula",
                    "label": "연립 효용지수 기본 칸을 지금 바꾼다",
                    "selected": False,
                    "why": "0차 표만. 1·2a·2b 전. D-xxx 없음.",
                },
                {
                    "id": "keep-fe",
                    "label": "층은 건물 FE, 승강기는 건물 사이로 나눈다",
                    "selected": True,
                    "why": "승강기는 건물 상수라 FE와 공선이다.",
                },
            ],
        },
        "answers": [
            {
                "q": "비교가능 연립·다세대 건물이 있는가",
                "a": "0차 표. n≥10·1층≥3·중간≥3·최고층≥4",
                "evidence": "단가·γ로 고르지 않음. 승강기는 아직 미부착.",
            }
        ],
        "next": [
            {
                "id": "exp1-fe",
                "status": "planned",
                "title": "실험 1 건물 FE 층 더미",
                "ask": "같은 건물에서 1층 대비 중간·최상 ln(단가)가 다른가",
                "gate": "0차 적격. ln(단가). 연식과 시점 동시 금지. 승강기 넣지 않음",
            },
            {
                "id": "title-elevator",
                "status": "planned",
                "title": "표제부 승강기 부착",
                "ask": "승용·비상 승강기 수([45]·[46])를 건물에 붙일 수 있는가",
                "gate": "표본 행으로 인덱스 검증. 전수 웹검색 금지",
            },
            {
                "id": "exp2b",
                "status": "planned",
                "title": "실험 2b 층×승강기",
                "ask": "승강기 있는 건물에서 윗층 기울기가 다른가",
                "gate": "건물 FE 유지. 주효과 없음. 부착 후",
            },
            {
                "id": "exp2a",
                "status": "planned",
                "title": "실험 2a 4~5층 수준",
                "ask": "비슷한 4~5층에서 승강기 유무가 단가 수준을 바꾸는가",
                "gate": "연식대×층×유형 균형 표 먼저. 6층+ 본표본 아님. FE 없음",
            },
            {
                "id": "exp3",
                "status": "planned",
                "title": "실험 3 구성",
                "ask": "방향이 체급·연식·수도권에서 같은가",
                "gate": "적격 건물을 계수로 다시 고르지 않음",
            },
            {
                "id": "product-formula",
                "status": "blocked",
                "title": "제품 층 칸·지도",
                "ask": "연립 효용지수를 1/중간/최상으로 바꾸는가",
                "gate": "1·2b·3 기록 후. D-xxx 없음",
            },
        ],
        "limits": [
            "화면 회귀 탭의 금액 OLS·한 단지 p값은 파일럿이다.",
            "아파트 상대층(저·중·고 %)을 칸으로 쓰지 않았다.",
            "승강기는 0차에 아직 안 붙였다. FE와 주효과를 한 식에 넣지 않는다.",
            "제품 효용지수 n≥50·상대층 기본값은 바꾸지 않았다.",
        ],
        "resume": {
            "next_id": "exp1-fe",
            "title": "실험 1 건물 FE",
            "say": "0차 적격 표 다음. ln(단가)=건물FE+중간+최상+ln(면적)+시점. 승강기 넣지 않음.",
            "do_not": "금액 OLS를 본식으로 쓰지 않는다. FE 식에 연식과 시점을 같이 넣지 않는다. 전국 한 γ를 본결과로 쓰지 않는다.",
            "how": "계획 SSOT docs/lab/ROWHOUSE_FLOOR_ELEVATOR_LAB.md. 관리자 ?tool=rowhouse-floor.",
        },
    }


def run_screen(
    *,
    engine_bind: Engine,
    as_of_month: date | None = None,
    window_years: int = WINDOW_YEARS,
    phase1: bool = True,
    phase2: bool = True,
    phase3: bool = True,
    refresh_elevator: bool = False,
) -> dict[str, Any]:
    db = engine_bind.connect()
    try:
        as_of = as_of_month or latest_as_of_month(db)
        period_start, period_end = period_bounds_for_window(as_of, window_years)
        rows = db.execute(
            text(build_screen_sql()),
            {
                "asset": ASSET_TYPE,
                "p_start": period_start,
                "p_end": period_end,
            },
        ).mappings().all()
        cells = [row_from_agg(dict(r)) for r in rows]
        copy = default_lab_copy()
        summary = _summarize(cells)
        copy["answers"] = [
            {
                "q": "비교가능 연립·다세대 건물이 있는가",
                "a": (
                    f"스캔 {summary['n_buildings_scanned']} · 적격 {summary['n_eligible']} · "
                    f"n≥20 {summary['n_sensitivity'].get('20', 0)} · "
                    f"n≥50 {summary['n_ge_50']} · 4~5층 {summary['n_ident_45']}"
                ),
                "evidence": "창 5년. 단가·γ로 고르지 않음. n≥50은 제품 지수 스모크 후보일 뿐.",
            }
        ]
        payload = {
            "date": date.today().isoformat(),
            "status": "phase0_screen",
            "as_of_month": as_of.isoformat(),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "window_years": window_years,
            "product_change": False,
            "summary": summary,
            "cells": cells,
            **copy,
        }
        if not phase1:
            return payload
        keys = [c["building_key"] for c in cells if c.get("eligible") and c.get("building_key")]
        tx = fetch_phase1_tx(db, keys=keys, period_start=period_start, period_end=period_end)
        phase1_out = run_phase1(tx, cells)
        apply_phase1_copy(copy, summary, phase1_out)
        payload["phase1"] = phase1_out
        payload["status"] = "phase1_fit"
        payload["verdict"] = copy["verdict"]
        payload["answers"] = copy["answers"]
        payload["next"] = copy["next"]
        payload["limits"] = copy["limits"]
        payload["resume"] = copy["resume"]
        if not phase2:
            return payload
        elev_by_key, elev_sum, csv_rows = attach_elevator(tx, refresh=refresh_elevator)
        write_attach_csv(csv_rows)
        summary["elevator_attached"] = bool(elev_sum.get("ok"))
        payload["summary"] = summary
        payload["elevator"] = elev_sum
        phase2b = run_phase2b(tx, cells, elev_by_key)
        phase2a = run_phase2a(tx, cells, elev_by_key)
        apply_phase2_copy(copy, summary, elev_sum, phase2b, phase2a)
        payload["phase2b"] = phase2b
        payload["phase2a"] = phase2a
        payload["status"] = "phase2"
        payload["verdict"] = copy["verdict"]
        payload["answers"] = copy["answers"]
        payload["next"] = copy["next"]
        payload["limits"] = copy["limits"]
        payload["resume"] = copy["resume"]
        if not phase3:
            return payload
        purpose_by_key = purpose_by_building(tx)
        phase3_out = run_phase3(tx, cells, elev_by_key, purpose_by_key)
        apply_phase3_copy(copy, phase3_out)
        payload["phase3"] = phase3_out
        payload["status"] = "phase3"
        payload["verdict"] = copy["verdict"]
        payload["answers"] = copy["answers"]
        payload["next"] = copy["next"]
        payload["limits"] = copy["limits"]
        payload["resume"] = copy["resume"]
        return payload
    finally:
        db.close()


def write_phase3_csv(phase3: dict[str, Any], path: Path) -> None:
    groups = (
        ("pooled", {"all": (phase3 or {}).get("pooled") or {}}),
        ("floor", (phase3 or {}).get("by_max_floor") or {}),
        ("cap", (phase3 or {}).get("by_cap") or {}),
        ("age", (phase3 or {}).get("by_age") or {}),
        ("n", (phase3 or {}).get("by_n") or {}),
        ("purpose", (phase3 or {}).get("by_purpose") or {}),
    )
    rows: list[dict[str, Any]] = []
    fields = [
        "group",
        "slice",
        "ok",
        "n",
        "n_buildings",
        "n_elev_yes",
        "n_elev_no",
        "dir_theta_mid",
        "pct_theta_mid",
        "p_theta_mid",
        "dir_theta_top",
        "pct_theta_top",
        "p_theta_top",
        "reason",
    ]
    for group, mapping in groups:
        for name, fit in mapping.items():
            if not isinstance(fit, dict):
                continue
            rows.append(
                {
                    "group": group,
                    "slice": name,
                    "ok": bool(fit.get("ok")),
                    "n": fit.get("n"),
                    "n_buildings": fit.get("n_buildings"),
                    "n_elev_yes": fit.get("n_elev_yes"),
                    "n_elev_no": fit.get("n_elev_no"),
                    "dir_theta_mid": fit.get("dir_theta_mid"),
                    "pct_theta_mid": fit.get("pct_theta_mid"),
                    "p_theta_mid": fit.get("p_theta_mid"),
                    "dir_theta_top": fit.get("dir_theta_top"),
                    "pct_theta_top": fit.get("pct_theta_top"),
                    "p_theta_top": fit.get("p_theta_top"),
                    "reason": fit.get("reason") or "",
                }
            )
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def write_payload(payload: dict[str, Any], path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    old: dict[str, Any] = {}
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            old = {}
    cells = payload.get("cells") or []
    csv_path = path.with_suffix(".csv")
    eligible = [c for c in cells if c.get("eligible")]
    if eligible:
        fields = list(eligible[0].keys())
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(eligible)
    slim = {k: v for k, v in payload.items() if k != "cells"}
    slim["cells_csv"] = csv_path.name
    slim["n_csv_rows"] = len(eligible)
    for key in KEEP_LAB_KEYS:
        if key not in slim and key in old:
            slim[key] = old[key]
    p3 = slim.get("phase3")
    if p3:
        p3_csv = path.parent / "rowhouse_floor_elevator_phase3.csv"
        write_phase3_csv(p3, p3_csv)
        slim["phase3_csv"] = p3_csv.name
    path.write_text(json.dumps(slim, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="연립·다세대 층 효용 0차·1·2차")
    p.add_argument("--as-of", default="", help="YYYY-MM-01. 비우면 원장 최신월")
    p.add_argument("--window", type=int, default=WINDOW_YEARS)
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--screen-only", action="store_true", help="0차 표만")
    p.add_argument("--no-phase2", action="store_true", help="실험 1까지만")
    p.add_argument("--no-phase3", action="store_true", help="실험 2까지만")
    p.add_argument("--refresh-elevator", action="store_true", help="표제부 승강기 캐시 무시")
    args = p.parse_args()
    eng = get_collective_engine()
    if eng is None:
        raise SystemExit("COLLECTIVE_DATABASE_URL 없음")
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    payload = run_screen(
        engine_bind=eng,
        as_of_month=as_of,
        window_years=int(args.window),
        phase1=not args.screen_only,
        phase2=not args.screen_only and not args.no_phase2,
        phase3=not args.screen_only and not args.no_phase2 and not args.no_phase3,
        refresh_elevator=bool(args.refresh_elevator),
    )
    write_payload(payload, Path(args.out))
    s = payload["summary"]
    print(
        f"scanned={s['n_buildings_scanned']} eligible={s['n_eligible']} "
        f"ident45={s['n_ident_45']} n50={s['n_ge_50']}",
        flush=True,
    )
    ph = payload.get("phase1")
    if ph:
        po = ph.get("pooled") or {}
        print(
            f"phase1 n={po.get('n')} buildings={po.get('n_buildings')} "
            f"mid={po.get('dir_mid')} {po.get('pct_mid')} top={po.get('dir_top')} {po.get('pct_top')}",
            flush=True,
        )
    ev = payload.get("elevator") or {}
    if ev:
        print(
            f"elev yes={ev.get('n_yes')} no={ev.get('n_no')} unk={ev.get('n_unknown')} mixed={ev.get('n_mixed')}",
            flush=True,
        )
    p2 = (payload.get("phase2b") or {}).get("pooled") or {}
    if p2:
        print(
            f"phase2b theta_mid={p2.get('dir_theta_mid')} {p2.get('pct_theta_mid')} "
            f"theta_top={p2.get('dir_theta_top')} {p2.get('pct_theta_top')} reason={p2.get('reason')}",
            flush=True,
        )
    p3 = payload.get("phase3") or {}
    if p3:
        sk = p3.get("sketch") or {}
        print(
            f"phase3 agree_top={p3.get('agree_theta_top')} agree_mid={p3.get('agree_theta_mid')} "
            f"sketch_yes_top={(sk.get('yes') or {}).get('top')}",
            flush=True,
        )
    print(f"wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
