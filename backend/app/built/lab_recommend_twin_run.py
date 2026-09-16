"""유형별 픽스처를 돌려 랩 스냅샷을 남긴다. `--set chungbuk|gyeonggi`.

제품 API를 루프하지 않는다. Twin 이웃만 프로필 API에서 읽고, 적합은 벤치 함수를 직접 호출한다.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import warnings
from datetime import date
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", message="overflow encountered in exp")

from app.built.db import get_built_engine
from app.built.lab_recommend_twin_bench import COLUMN_IDS, run_recommend_twin_bench
from app.built.lab_recommend_twin_router import _FIXTURE_SETS
from app.built.schemas import RegressionSelectionRequest

_REPO = Path(__file__).resolve().parents[3]
_TWINS_API = "http://127.0.0.1:8000"
WINDOW_YEARS = 5
OUT_BY_SET = {
    "chungbuk": _REPO / "docs" / "lab" / "recommend_twin_bench_run.json",
    "gyeonggi": _REPO / "docs" / "lab" / "recommend_twin_bench_run_gyeonggi.json",
}
SCENARIO = {
    "gross_area": 120.0,
    "land_area": 250.0,
    "building_age": 10.0,
    "road_width_label": "12미터미만",
}


def _twin_profile(asset_type: str) -> str:
    return "built_commercial" if asset_type == "commercial" else "general"


def _load_cases(set_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in _FIXTURE_SETS[set_id]:
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        defaults = data.get("defaults") or {}
        for case in data.get("cases") or []:
            codes = case.get("region_codes") or []
            if not codes:
                continue
            items.append(
                {
                    "case_id": case.get("case_id"),
                    "label": case.get("label") or codes[0],
                    "asset_type": defaults.get("asset_type"),
                    "region_code": codes[0],
                    "sample_group": case.get("sample_group"),
                    "tx_n": (case.get("strata") or {}).get("tx_n"),
                }
            )
    return items


def _fetch_twins(region_code: str, *, asset_type: str) -> dict[str, Any]:
    profile = _twin_profile(asset_type)
    q = (
        f"{_TWINS_API}/api/regional-profile/twins/{region_code}"
        f"?window_years={min(5, WINDOW_YEARS)}&top_k=5&scope=region&twin_profile={profile}"
    )
    with urllib.request.urlopen(q, timeout=30) as resp:
        data = json.load(resp)
    neighbors = []
    for n in data.get("neighbors") or []:
        code = str(n.get("twin_beopjungri_code") or n.get("twin_eupmyeondong_code") or "").strip()
        if not code:
            continue
        neighbors.append(
            {
                "region_code": code,
                "similarity_score": n.get("similarity_score"),
                "detail_scores": n.get("detail_scores"),
            }
        )
    as_of = data.get("as_of_month")
    return {
        "neighbors": neighbors,
        "profile_version": data.get("profile_version"),
        "profile_as_of_month": str(as_of) if as_of else None,
        "profile_window_years": data.get("window_years"),
        "twin_profile": profile,
        "neighbor_n": len(neighbors),
    }


def _slim_col(col: dict[str, Any]) -> dict[str, Any]:
    return {
        "n": col.get("n"),
        "search_cv_mape": col.get("search_cv_mape"),
        "confirm_cv_mape": col.get("confirm_cv_mape"),
        "y_hat": col.get("y_hat"),
        "ci_lower": col.get("ci_lower"),
        "ci_upper": col.get("ci_upper"),
        "pi_lower": col.get("pi_lower"),
        "pi_upper": col.get("pi_upper"),
        "skipped_reason": col.get("skipped_reason"),
        "predict_skipped_reason": col.get("predict_skipped_reason"),
        "blocks": col.get("blocks") or [],
        "response_scale": col.get("response_scale"),
    }


def _better(a: float | None, b: float | None) -> bool | None:
    if a is None or b is None:
        return None
    return a < b


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by: dict[str, Any] = {}
    for asset in ("commercial", "factory", "detached"):
        subset = [r for r in rows if r.get("asset_type") == asset and not r.get("error")]
        twin1_ok = [r for r in subset if (r.get("columns") or {}).get("twin1", {}).get("n")]
        def _cv(row, col, key):
            c = (row.get("columns") or {}).get(col) or {}
            return c.get(key)

        by[asset] = {
            "n_cases": sum(1 for r in rows if r.get("asset_type") == asset),
            "n_ok": len(subset),
            "n_error": sum(1 for r in rows if r.get("asset_type") == asset and r.get("error")),
            "n_twin_rank1": sum(1 for r in subset if r.get("rank1_region_code")),
            "n_twin1_search_lt_local": sum(
                1 for r in twin1_ok if _better(_cv(r, "twin1", "search_cv_mape"), _cv(r, "local", "search_cv_mape"))
            ),
            "n_twin1_confirm_lt_local": sum(
                1 for r in twin1_ok if _better(_cv(r, "twin1", "confirm_cv_mape"), _cv(r, "local", "confirm_cv_mape"))
            ),
            "n_twin2_confirm_lt_twin1": sum(
                1
                for r in twin1_ok
                if _better(_cv(r, "twin2", "confirm_cv_mape"), _cv(r, "twin1", "confirm_cv_mape"))
            ),
            "n_twin1_dummy_yhat": sum(
                1 for r in twin1_ok if (r.get("columns") or {}).get("twin1_dummy", {}).get("y_hat") is not None
            ),
        }
    return by


def _payload(rows: list[dict[str, Any]], *, status: str, set_id: str) -> dict[str, Any]:
    names = [p.name for p in _FIXTURE_SETS[set_id]]
    exclude_gu = set_id == "gyeonggi"
    basin_ko = "경기" if set_id == "gyeonggi" else "충북"
    return {
        "run_id": f"recommend-twin-bench-{set_id}-2026-09-11",
        "date": date.today().isoformat(),
        "basin": set_id,
        "decision": ["D-066", "D-073"],
        "status": status,
        "product_change": False,
        "resume": {
            "next_id": "product-follow" if status == "experimental" else "fixture-3types",
            "title": "스냅샷을 읽고 제품 반영 여부를 결정한다"
            if status == "experimental"
            else f"{basin_ko} 샘플을 돌려 스냅샷을 남긴다",
            "say": "실험 Twin은 1위만. 제품 Twin1(통과 Twin 전체)과 표본이 다르다. 더미·Twin1 축소는 이 표를 본 뒤에만.",
            "do_not": "전국 전수, 기본 통계 식 덮기, 제품 Twin1을 1위로 축소, 지역 더미를 Stage2 기본으로 켜기, 일반구·시군구 초점.",
            "how": f"관리자 ?tool=recommend-twin. {basin_ko} 읍면동만. 공업·단독 빈 칸은 실패가 아니라 결과다.",
        },
        "method": {
            "note": "읍면동 · 창 5년 · 시나리오 연면적 120 · 대지 250 · 연식 10 · 도로 12미터미만 · 용도 기준범주."
            + (" 일반구 산하 읍면동 제외." if exclude_gu else ""),
            "window_years": WINDOW_YEARS,
            "admin_level": "eupmyeondong",
            "exclude_general_gu": exclude_gu,
            "fixtures": names,
            "twin1_sample": "local + structure rank-1 only",
            "dummy": "region_leaf on Twin columns only; predict uses anchor intercept",
        },
        "summary": _summarize(rows),
        "rows": rows,
    }


def _write(rows: list[dict[str, Any]], *, status: str, set_id: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(_payload(rows, status=status, set_id=set_id), ensure_ascii=False, indent=2), encoding="utf-8")


def run(*, resume: bool = True, set_id: str = "chungbuk") -> Path:
    if set_id not in _FIXTURE_SETS:
        raise SystemExit(f"unknown set: {set_id}")
    out = OUT_BY_SET[set_id]
    cases = _load_cases(set_id)
    if not cases:
        raise SystemExit("픽스처 케이스가 없습니다.")
    engine = get_built_engine()
    if engine is None:
        raise SystemExit("BUILT_DATABASE_URL 없음")

    rows: list[dict[str, Any]] = []
    done: set[str] = set()
    if resume and out.is_file():
        prev = json.loads(out.read_text(encoding="utf-8"))
        if prev.get("basin") in (None, set_id):
            for row in prev.get("rows") or []:
                cid = str(row.get("case_id") or "")
                if cid and not row.get("error"):
                    rows.append(row)
                    done.add(cid)

    _write(rows, status="running", set_id=set_id, out=out)
    remaining = [c for c in cases if c["case_id"] not in done]
    print(f"recommend-twin-bench set={set_id} cases={len(cases)} resume={len(done)} todo={len(remaining)}", flush=True)

    with engine.connect() as conn:
        for i, case in enumerate(remaining, start=1):
            cid = case["case_id"]
            code = case["region_code"]
            asset = case["asset_type"]
            print(f"[{i}/{len(remaining)}] {cid} {asset} {code} …", flush=True)
            try:
                twins = _fetch_twins(code, asset_type=asset)
                req = RegressionSelectionRequest(
                    asset_type=asset,
                    region_codes=[code[:8]],
                    region_code_level="eupmyeondong",
                    window_years=WINDOW_YEARS,
                    contract_year_from=2019,
                    enrich=False,
                    profile_twin_neighbors=twins["neighbors"],
                    profile_version=twins["profile_version"],
                    profile_as_of_month=twins["profile_as_of_month"],
                    profile_window_years=twins["profile_window_years"],
                    run_stage2=False,
                    run_stage2_research=False,
                )
                out_row = run_recommend_twin_bench(conn, req=req, scenario=SCENARIO)
                cols = {c["id"]: _slim_col(c) for c in out_row.get("columns") or [] if c.get("id") in COLUMN_IDS}
                rows.append(
                    {
                        "case_id": cid,
                        "label": case.get("label"),
                        "asset_type": asset,
                        "region_code": out_row.get("region_code") or code,
                        "sample_group": case.get("sample_group"),
                        "tx_n": case.get("tx_n"),
                        "rank1_region_code": out_row.get("rank1_region_code"),
                        "rank1_skipped_reason": out_row.get("rank1_skipped_reason"),
                        "local_obs": out_row.get("local_obs"),
                        "twin_profile": twins["twin_profile"],
                        "neighbor_n": twins["neighbor_n"],
                        "stage1_blocks": out_row.get("stage1_blocks"),
                        "stage1_scale": out_row.get("stage1_scale"),
                        "columns": cols,
                    }
                )
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                rows.append({**case, "error": str(exc)})
                print(f"  skip: {exc}", flush=True)
            except Exception as exc:  # noqa: BLE001 — one case must not stop the batch
                rows.append({**case, "error": str(exc)})
                print(f"  error: {exc}", flush=True)
            _write(rows, status="running", set_id=set_id, out=out)

    _write(rows, status="experimental", set_id=set_id, out=out)
    print(f"wrote {out}", flush=True)
    return out


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Recommend Twin bench fixture snapshot")
    p.add_argument("--set", choices=sorted(_FIXTURE_SETS), default="chungbuk")
    p.add_argument("--fresh", action="store_true")
    args = p.parse_args()
    run(resume=not args.fresh, set_id=args.set)


if __name__ == "__main__":
    main()
