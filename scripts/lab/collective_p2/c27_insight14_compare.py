"""집합 2단계 P5 — Insight 14(동일 지번 아파트·오피스텔) 리허설 재계산 ↔ 공개값 비교. (리허설 승인 뒤 실행)

생성기 `backend/app/collective/apt_officetel_same_building_lab.py` 는 wip/ai-revision-20261109 에만 있다.
main 으로 가져오지 않는다. 그 브랜치를 **분리된(detached) worktree 로 꺼내 읽기 전용으로** 돌린다.

  python c27_insight14_compare.py prepare            # worktree 만들기(커밋 고정, logs/collective_p2/insight14/worktree.json)
  python c27_insight14_compare.py run --side after   # 리허설 DB(*_p2r)로 재계산 → logs/collective_p2/insight14/after.json
  python c27_insight14_compare.py compare            # 공개값(main insight14.ts SNAP + wip 커밋의 JSON) ↔ after
  python c27_insight14_compare.py cleanup            # worktree 지우기

안전장치
- 하위 프로세스에 `PGOPTIONS=-c default_transaction_read_only=on` — 어느 DB 에도 쓰지 못한다. after 는 DB 이름이 *_p2r 인지 확인.
- 생성기의 고정 출력 경로(docs/lab/…json)는 하위 프로세스 안에서 logs/ 로 바꾼다. 바이트코드도 쓰지 않는다(PYTHONDONTWRITEBYTECODE).
- 실행 전후로 worktree 가 고정 커밋 그대로이고 바뀐 파일이 없는지 확인한다(있으면 멈춤).
- 기간은 공개값과 같게 as_of 2026-10-01(2021-11~2026-10)로 고정한다(리허설 mart 의 최신 월이 달라도).
- 접속 정보는 출력하지 않는다. 결과에는 집계 숫자만 있다(키·지번 없음).
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
OUT = ROOT / "logs" / "collective_p2" / "insight14"
WT = ROOT.parent / f"{ROOT.name}-wip14-ro"
BRANCH = "wip/ai-revision-20261109"
GEN = "backend/app/collective/apt_officetel_same_building_lab.py"
PUBLISHED_JSON = "docs/lab/apt_officetel_same_building.json"
AS_OF = "2026-10-01"
REHEARSAL_RE = re.compile(r"^[a-z0-9_]+_p2r(_[a-z0-9]+)?$")
SIDES = {"after": {"collective": "collective_stats_p2r", "parcel": "parcel_master_p2r"},
         "before": {"collective": "collective_stats", "parcel": "parcel_master"}}
PY = sys.executable


class StopRun(RuntimeError):
    pass


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


# --- worktree -------------------------------------------------------------

def prepare(*, git_=git) -> dict:
    commit = git_("rev-parse", f"{BRANCH}^{{commit}}")
    if not WT.exists():
        git_("worktree", "add", "--detach", str(WT), commit)
    info = {"branch": BRANCH, "commit": commit, "path": str(WT)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "worktree.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    check_worktree(info, git_=git_)
    return info


def load_worktree_info() -> dict:
    f = OUT / "worktree.json"
    if not f.is_file():
        raise StopRun("worktree 정보 없음 — 먼저 prepare")
    return json.loads(f.read_text(encoding="utf-8"))


def check_worktree(info: dict, *, git_=git) -> None:
    """고정 커밋 그대로이고 바뀐·새 파일이 없어야 한다(읽기 전용 실행 확인)."""
    wt = Path(info["path"])
    if not (wt / GEN).is_file():
        raise StopRun("worktree 에 생성기 파일이 없음")
    head = git_("rev-parse", "HEAD", cwd=wt)
    if head != info["commit"]:
        raise StopRun(f"worktree HEAD 가 고정 커밋과 다름({head[:8]} ≠ {info['commit'][:8]})")
    dirty = git_("status", "--porcelain", "--untracked-files=all", cwd=wt)
    if dirty:
        raise StopRun(f"worktree 에 바뀐 파일 {len(dirty.splitlines())}개 — 읽기 전용 실행이 아님")


def cleanup(*, git_=git) -> None:
    if WT.exists():
        git_("worktree", "remove", str(WT))


# --- 실행 -----------------------------------------------------------------

RUNNER = """
import datetime, sys
from pathlib import Path
sys.path.insert(0, r"{backend}")
import app.collective.apt_officetel_same_building_lab as m
assert Path(m.__file__).resolve().is_relative_to(Path(r"{backend}").resolve()), "생성기가 worktree 밖에서 읽힘"
m.OUT = Path(r"{out}")
_as_of = datetime.date.fromisoformat("{as_of}")
m.latest_mart_snapshot = lambda conn: (_as_of, None)
m.main()
"""


def env_for(side: str, base_url: str) -> dict:
    from sqlalchemy.engine import make_url

    dbs = SIDES[side]
    if side == "after" and not all(REHEARSAL_RE.match(v) for v in dbs.values()):
        raise StopRun("after 쪽 DB 이름이 리허설 이름이 아님")
    base = make_url(base_url)
    env = {k: v for k, v in os.environ.items() if not k.endswith("_DATABASE_URL")}
    env.update({"PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
                "PGOPTIONS": "-c default_transaction_read_only=on"})
    env["COLLECTIVE_DATABASE_URL"] = base.set(database=dbs["collective"]).render_as_string(hide_password=False)
    env["PARCEL_MASTER_DATABASE_URL"] = base.set(database=dbs["parcel"]).render_as_string(hide_password=False)
    return env


def runner_code(info: dict, out: Path) -> str:
    return RUNNER.format(backend=Path(info["path"]) / "backend", out=out, as_of=AS_OF)


def run(side: str, *, git_=git, runner=subprocess.run) -> int:
    sys.path.insert(0, str(ROOT / "pipeline"))
    from collective.migrate_p2_keys import server_url_from_env

    info = load_worktree_info()
    check_worktree(info, git_=git_)
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{side}.json"
    r = runner([PY, "-c", runner_code(info, out)], cwd=OUT, env=env_for(side, server_url_from_env()),
               capture_output=True, text=True, encoding="utf-8", errors="replace")
    (OUT / f"{side}.log").write_text((r.stdout or "")[-8000:] + "\n" + (r.stderr or "")[-8000:], encoding="utf-8")
    check_worktree(info, git_=git_)          # 실행 뒤에도 worktree 그대로
    print(f"insight14 {side}: rc={r.returncode} → {out.relative_to(ROOT)}")
    return int(r.returncode)


# --- 비교 -----------------------------------------------------------------

def ts_snapshot() -> dict:
    """main 의 frontend-insight/src/copy/insight14.ts 의 INSIGHT_14_SNAP(공개 화면 값)."""
    s = (ROOT / "frontend-insight" / "src" / "copy" / "insight14.ts").read_text(encoding="utf-8")
    m = re.search(r"export const INSIGHT_14_SNAP = \{(.*?)\n\}", s, re.S)
    out: dict = {}
    for k, v in re.findall(r"(\w+):\s*(\"[^\"]*\"|-?[\d.]+)", m.group(1) if m else ""):
        out[k] = v.strip('"') if v.startswith('"') else (float(v) if "." in v else int(v))
    return out


def _get(d: dict, path: str):
    for p in path.split("."):
        if not isinstance(d, dict) or p not in d:
            return None
        d = d[p]
    return d


def _pct(v):
    return None if v is None else round(float(v) * 100, 1)


def headline(d: dict) -> dict:
    """생성기 JSON → 공개 화면에 쓰인 숫자(같은 이름)."""
    sb = "same_building"
    n = _get(d, f"{sb}.direct.distribution.n")
    below = _get(d, f"{sb}.direct.distribution.share_below")
    return {
        "periodStart": d.get("period_start"), "periodEnd": d.get("period_end"), "asOfMonth": d.get("as_of"),
        "status": d.get("status"),
        "candidates": _get(d, "stage1.same_building_n"),
        "nHeadline": _get(d, f"{sb}.direct.pass_n"),
        "medianPct": _pct(_get(d, f"{sb}.direct.distribution.median")),
        "p25Pct": _pct(_get(d, f"{sb}.direct.distribution.p25")),
        "p75Pct": _pct(_get(d, f"{sb}.direct.distribution.p75")),
        "nBelow": None if n is None or below is None else round(float(below) * int(n)),
        "nStrict": _get(d, f"{sb}.followup.strict_90_92d.pass_n"),
        "strictMedianPct": _pct(_get(d, f"{sb}.followup.strict_90_92d.distribution.median")),
        "nRegression": _get(d, f"{sb}.regression.n_fit"),
        "nIntervalBelow": _get(d, f"{sb}.regression.intervals.entirely_below_0"),
        "pooledPercent": _get(d, f"{sb}.regression.pooled.percent"),
    }


def published_json(info: dict | None, *, git_=git) -> dict | None:
    """공개값의 원본: 고정 커밋의 docs/lab JSON(git show — worktree 파일을 열지 않아도 된다)."""
    commit = (info or {}).get("commit") or BRANCH
    try:
        return json.loads(git_("show", f"{commit}:{PUBLISHED_JSON}"))
    except (subprocess.CalledProcessError, ValueError):
        return None


def compare_table(snap: dict, pub: dict | None, after: dict | None) -> tuple[str, list[str]]:
    """(표, 차이 지표 이름들). 차이 = 공개 JSON 과 after 가 다른 지표."""
    pubh = headline(pub) if pub else {}
    afth = headline(after) if after else {}
    keys = list(dict.fromkeys([*pubh, *afth]))
    lines = ["| 지표 | 공개 화면(SNAP) | 공개 원본(wip JSON) | 리허설 after | after − 공개 |", "|---|---|---|---|---|"]
    diffs = []
    for k in keys:
        p, a = pubh.get(k), afth.get(k)
        if isinstance(p, (int, float)) and isinstance(a, (int, float)):
            dlt = round(a - p, 4)
            if dlt:
                diffs.append(k)
        elif after is None:
            dlt = "—"
        else:
            dlt = "—" if p == a else "다름"
            if p != a and after is not None:
                diffs.append(k)
        lines.append(f"| {k} | {snap.get(k, '—')} | {p if p is not None else '—'} | {a if a is not None else '—'} | {dlt} |")
    mism = [k for k in snap if k in pubh and pubh[k] is not None and snap[k] != pubh[k]]
    if mism:
        lines.append(f"\n- 주의: 공개 화면 값과 wip JSON 이 다른 지표 {mism} — 화면 값이 다른 실행에서 왔을 수 있다")
    return "\n".join(lines), diffs


def compare(*, git_=git) -> int:
    info = None
    try:
        info = load_worktree_info()
    except StopRun:
        pass
    f = OUT / "after.json"
    after = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
    tab, diffs = compare_table(ts_snapshot(), published_json(info, git_=git_), after)
    md = "\n".join(["# Insight 14 — 리허설 재계산 ↔ 공개값", "",
                    f"- 생성기: {BRANCH} @ {(info or {}).get('commit', '?')[:10]} (worktree 읽기 전용 실행)",
                    f"- 기간 고정: as_of {AS_OF}", "", tab, "",
                    ("- 리허설 결과 없음 — run --side after 먼저" if after is None else
                     f"- 차이 지표: {', '.join(diffs) if diffs else '없음'}")])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "compare.md").write_text(md, encoding="utf-8")
    print(md)
    return 0 if after is not None and not diffs else (2 if after is None else 1)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare")
    r = sub.add_parser("run")
    r.add_argument("--side", choices=list(SIDES), default="after")
    sub.add_parser("compare")
    sub.add_parser("cleanup")
    a = p.parse_args(argv)
    try:
        if a.cmd == "prepare":
            print(json.dumps(prepare(), ensure_ascii=False))
            return 0
        if a.cmd == "run":
            return run(a.side)
        if a.cmd == "compare":
            return compare()
        cleanup()
        return 0
    except StopRun as ex:
        print(f"중단: {ex}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
