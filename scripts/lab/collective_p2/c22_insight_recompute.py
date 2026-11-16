"""Phase C-2 리허설용 — Macro Insight 14·08·03·12 재계산 비교 준비. (지금 실행하지 않음. C-2 반영 리허설 뒤 실행)

공개 Insight 숫자는 정적 스냅샷(frontend-insight/src/copy/insight*.ts)이다. 키 변경 영향만 보려면 같은 기간으로
  before = 진짜 로컬 DB(읽기 전용)   after = 리허설 DB(*_p2r)
두 번 다시 계산해 비교하고, 공개 스냅샷 값을 옆에 둔다(공개값 ≠ before 는 그 뒤 적재된 거래 탓일 수 있다).

  python c22_insight_recompute.py run --side before
  python c22_insight_recompute.py run --side after
  python c22_insight_recompute.py compare            → logs/collective_p2/insight/compare.md

- 생성기는 하위 프로세스로 돌리고 `PGOPTIONS=-c default_transaction_read_only=on` 을 준다(어느 DB 에도 쓰지 못함).
  after 는 접속 DB 이름이 *_p2r 인지 확인한다.
- 생성기의 출력 경로(docs/lab/*.json 고정)는 하위 프로세스 안에서 logs/collective_p2/insight/<side>/ 로 바꾼다(커밋 파일 덮지 않음).
- 기간은 공개 스냅샷과 같게 고정한다(03·08: as_of 2026-08-01 → 2021-09~2026-08). 12 는 연간(2021–2025)이라 as_of 무관.
- 14(동일 지번 아파트·오피스텔)의 생성기 `backend/app/collective/apt_officetel_same_building_lab.py` 는 main 에 없다
  (wip/ai-revision-20261109 에만 있음). --gen14 로 그 파일 경로를 주면 돌리고, 없으면 「생성기 없음」으로 표시한다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
OUT = ROOT / "logs" / "collective_p2" / "insight"
PY = sys.executable
AS_OF_0308 = "2026-08-01"
REHEARSAL_RE = re.compile(r"^[a-z0-9_]+_p2r(_[a-z0-9]+)?$")
SIDES = {"before": {"collective": "collective_stats", "rent": "rent_stats", "built": "built_stats"},
         "after": {"collective": "collective_stats_p2r", "rent": "rent_stats_p2r", "built": "built_stats_p2r"}}

# 하위 프로세스에서 돌릴 코드(출력 경로를 logs 로 바꾸고 기간을 고정)
RUNNERS = {
    "03": """
import sys; sys.argv = ["x", "--as-of", "{as_of}", "--out", r"{out}/insight03.json"]
from app.rowhouse_lab import floor_elevator_screen as m
m.main()
""",
    "08": """
import datetime, json
from pathlib import Path
from app.apt_floor_lab import fit as m
d = Path(r"{out}")
m.OUT_JSON, m.OUT_CSV, m.OUT_PHASE5 = d / "insight08.json", d / "insight08_buildings.csv", d / "insight08_phase5.json"
m.latest_as_of_month = lambda conn: datetime.date.fromisoformat("{as_of}")
# 생성기의 키 필터는 TEMP 표(CREATE/DROP)라 읽기 전용 세션에서 막힌다 → 같은 조건을 expanding IN(나눠 읽기)으로.
# 기본 키 집합과의 JOIN = IN 필터라 결과 행이 같다(키 중복 제거).
import pandas as pd
from sqlalchemy import bindparam, text
_SQL = '''SELECT t.building_key, t.floor, t.exclusive_area, t.unit_price, t.contract_year, t.contract_month,
       t.building_year FROM collective_transactions t
WHERE t.building_key IN :keys AND t.asset_type = 'apartment' AND t.is_valid = TRUE
  AND t.contract_date >= :p_start AND t.contract_date <= :p_end
  AND t.unit_price > 0 AND t.exclusive_area > 0 AND t.floor >= 1'''
def _fetch(conn, keys, p_start, p_end):
    ks = sorted(set(keys))
    q = text(_SQL).bindparams(bindparam("keys", expanding=True))
    parts = [pd.read_sql(q, conn, params={{"keys": ks[i:i + 2000], "p_start": p_start, "p_end": p_end}})
             for i in range(0, len(ks), 2000)]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
m.fetch_transactions = _fetch
m.run_phase1()
""",
    "12": """
import json
from pathlib import Path
from app.sangkwon_apt_yield import build as m
p = m.build()
Path(r"{out}/insight12.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
""",
}


def env_for(side: str) -> dict:
    sys.path.insert(0, str(ROOT / "pipeline"))
    from sqlalchemy.engine import make_url

    from collective.migrate_p2_keys import server_url_from_env

    base = make_url(server_url_from_env())
    dbs = SIDES[side]
    if side == "after":
        assert all(REHEARSAL_RE.match(v) for v in dbs.values())
    env = {**os.environ, "PYTHONUTF8": "1", "PGOPTIONS": "-c default_transaction_read_only=on"}
    for k, name in (("COLLECTIVE_DATABASE_URL", dbs["collective"]), ("RENT_DATABASE_URL", dbs["rent"]),
                    ("BUILT_DATABASE_URL", dbs["built"])):
        env[k] = base.set(database=name).render_as_string(hide_password=False)
    return env


def run(side: str, only: list[str], gen14: Path | None) -> None:
    d = OUT / side
    d.mkdir(parents=True, exist_ok=True)
    env = env_for(side)
    runners = dict(RUNNERS)
    if gen14:
        runners["14"] = f"""
import importlib.util, sys
spec = importlib.util.spec_from_file_location("g14", r"{gen14}")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
sys.argv = ["x", "--out", r"{{out}}/insight14.json"]
m.main()
"""
    for q, code in runners.items():
        if only and q not in only:
            continue
        r = subprocess.run([PY, "-c", code.format(out=d, as_of=AS_OF_0308)], cwd=BACKEND, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        (d / f"insight{q}.log").write_text(r.stdout[-5000:] + "\n" + r.stderr[-5000:], encoding="utf-8")
        print(f"{side} insight{q}: rc={r.returncode}")


# --- 비교 ---------------------------------------------------------------

def ts_snapshot(q: str) -> dict:
    """insightNN.ts 의 *_SNAP 객체에서 숫자 칸(최상위)만 뽑는다."""
    p = ROOT / "frontend-insight" / "src" / "copy" / f"insight{q}.ts"
    s = p.read_text(encoding="utf-8")
    m = re.search(r"export const INSIGHT_\d+_SNAP = \{(.*?)\n\} as const;|export const INSIGHT_\d+_SNAP = \{(.*?)\n\};", s, re.S)
    body = (m.group(1) or m.group(2)) if m else ""
    top = {}
    depth = 0
    for ln in body.splitlines():
        if depth == 0:
            mm = re.match(r"\s*(\w+):\s*(-?[\d.]+),?\s*$", ln)
            if mm:
                top[mm.group(1)] = float(mm.group(2)) if "." in mm.group(2) else int(mm.group(2))
        depth += ln.count("{") + ln.count("[") - ln.count("}") - ln.count("]")
    return top


def headline(q: str, d: dict) -> dict:
    """재계산 JSON → 공개 스냅샷과 같은 이름의 머리 숫자."""
    if q == "03":
        s, p3 = d.get("summary", {}), d.get("phase3", {})
        return {"scanned": s.get("n_buildings_scanned"), "eligible": s.get("n_eligible"),
                "known": p3.get("n_known"), "nYes": p3.get("n_yes"), "nNo": p3.get("n_no")}
    if q == "08":
        out = {"eligible": d.get("buildings_fit")}
        for row in d.get("distribution", {}).get("by_tier", []):
            for b in ("low", "mid", "high", "top"):
                v = row.get("bins", {}).get(b, {}).get("p50")
                out[f"{row.get('key')}.{b}.p50"] = None if v is None else round(float(v), 1)
        return out
    if q == "12":
        return {"rows": len(d.get("rows", []))}
    if q == "14":
        return {k: d.get(k) for k in ("nHeadline", "nStrict", "nRegression", "nIntervalBelow")}
    return {}


def compare() -> str:
    lines = ["# Insight 재계산 비교 (공개 스냅샷 · before = 로컬 원본 · after = 리허설)", ""]
    for q in ("14", "08", "03", "12"):
        snap = ts_snapshot(q)
        got = {}
        for side in ("before", "after"):
            f = OUT / side / f"insight{q}.json"
            got[side] = headline(q, json.loads(f.read_text(encoding="utf-8"))) if f.is_file() else None
        lines += [f"## Insight {q}", ""]
        if got["before"] is None and got["after"] is None:
            lines += ["재계산 결과 없음" + (" — 생성기가 main 에 없음(--gen14)" if q == "14" else ""), ""]
            continue
        keys = list((got["after"] or got["before"]).keys())
        lines += ["| 지표 | 공개 스냅샷 | before | after | after−before |", "|---|---|---|---|---|"]
        for k in keys:
            b = (got["before"] or {}).get(k)
            a = (got["after"] or {}).get(k)
            dlt = (a - b) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else "—"
            lines.append(f"| {k} | {snap.get(k, '—')} | {b} | {a} | {dlt} |")
        lines.append("")
    md = "\n".join(lines)
    (OUT / "compare.md").write_text(md, encoding="utf-8")
    return md


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--side", choices=list(SIDES), required=True)
    r.add_argument("--only", default="", help="쉼표 목록(예: 03,08)")
    r.add_argument("--gen14", type=Path, default=None)
    sub.add_parser("compare")
    a = p.parse_args(argv)
    if a.cmd == "run":
        run(a.side, [x for x in a.only.split(",") if x], a.gen14)
    else:
        print(compare())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
