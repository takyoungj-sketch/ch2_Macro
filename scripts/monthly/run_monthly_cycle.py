"""
월간 로컬 사이클(반자동):
  평탄화 → pipeline/run_pipeline.py(excel+V2, --v2-as-of 명시) → 시도별 건수 스냅샷 JSON

사전 조건은 docs/MONTHLY_UPDATE_SOP.md 참고.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# 같은 폴더 유틸
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from cycle_utils import stats_as_of_iso_from_cycle_id  # noqa: E402

log = logging.getLogger(__name__)


def _run_subprocess_timed(
    phase: str,
    cmd: list[str],
    *,
    cwd: Path | None = None,
) -> None:
    """subprocess 실행과 wall-clock 시간을 로그로 남긴다."""
    log.info("[%s]: %s", phase, " ".join(cmd))
    t0 = time.perf_counter()
    kwargs: dict[str, object] = {}
    if cwd is not None:
        kwargs["cwd"] = str(cwd.resolve())
    subprocess.run(cmd, check=True, **kwargs)
    sec = time.perf_counter() - t0
    log.info("[%s timing] %s 소요=%.1fs (%.2f분)", "monthly_cycle", phase, sec, sec / 60.0)


def _write_manifest(repo: Path, cycle_id: str) -> Path:
    raw = repo / "raw" / "토지" / cycle_id
    out_dir = repo / "clean_snapshots" / cycle_id
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(raw.rglob("*.xlsx"), key=lambda p: str(p).lower())
    rel_list: list[str] = []
    for p in files:
        try:
            rel_list.append(str(p.relative_to(raw)))
        except ValueError:
            rel_list.append(str(p))
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cycle_id": cycle_id,
        "raw_root": str(raw),
        "xlsx_count": len(files),
        "xlsx_files": rel_list,
    }

    man_path = out_dir / "raw_manifest.json"
    man_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return man_path


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="월간 토지 로컬 파이프라인 (반자동)")
    p.add_argument("--cycle-id", required=True, help="작업 번들 ID (YYYYMM, 예: 202605)")
    p.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="저장소 루트 (기본: ch2_Macro)",
    )
    p.add_argument("--skip-flatten", action="store_true", help="이미 flat_in 만 쓸 때")
    p.add_argument(
        "--v2-as-of",
        help="build_stats_v2 --as-of (YYYY-MM-DD). 미지정 시 cycle_id 기본 매핑(SOP 참고)",
    )
    p.add_argument("--with-upper-v2", action="store_true")
    p.add_argument("--excel-format", default="auto", choices=["auto", "raw", "merged"])
    p.add_argument("--manifest-only", action="store_true", help="수집 목록 JSON 만 쓰고 종료")
    args = p.parse_args()

    repo: Path = args.repo_root.expanduser().resolve()
    cycle = args.cycle_id.strip()
    raw_dir = repo / "raw" / "토지" / cycle
    if not raw_dir.is_dir():
        raise SystemExit(f"raw 폴더가 없습니다: {raw_dir}")

    man = _write_manifest(repo, cycle)
    log.info("manifest: %s", man)
    if args.manifest_only:
        return

    flat_dir = repo / "clean_snapshots" / cycle / "flat_in"
    py = sys.executable
    cycle_t0 = time.perf_counter()
    if not args.skip_flatten:
        flat_dir.mkdir(parents=True, exist_ok=True)
        flatten_script = _SCRIPT_DIR / "flatten_raw_xlsx.py"
        _run_subprocess_timed(
            "flatten_raw_xlsx",
            [py, str(flatten_script), "--source", str(raw_dir), "--dest", str(flat_dir)],
        )
    else:
        flat_dir = raw_dir
        log.info("skip-flatten: excel-dir=%s", flat_dir)

    v2_as = (args.v2_as_of or "").strip() or stats_as_of_iso_from_cycle_id(cycle)
    log.info("v2-as-of=%s (build_stats_v2)", v2_as)

    runp = repo / "pipeline" / "run_pipeline.py"
    cmd = [
        py,
        str(runp),
        "--excel-dir",
        str(flat_dir),
        "--excel-format",
        str(args.excel_format),
        "--with-v2",
        "--v2-windows",
        "3,5",
        "--v2-as-of",
        v2_as,
    ]
    if args.with_upper_v2:
        cmd.append("--with-upper-v2")

    _run_subprocess_timed("run_pipeline(full)", cmd, cwd=repo / "pipeline")

    snap_script = _SCRIPT_DIR / "snapshot_land_tx_counts.py"
    snap_out = repo / "clean_snapshots" / cycle / "land_tx_counts_after.json"
    _run_subprocess_timed(
        "snapshot_land_tx_counts",
        [py, str(snap_script), "--output", str(snap_out)],
    )
    log.info("스냅샷: %s", snap_out)

    v2_snap = _SCRIPT_DIR / "snapshot_v2_stats.py"
    v2_out_dir = repo / "stats_snapshots" / cycle
    v2_out_dir.mkdir(parents=True, exist_ok=True)
    v2_out = v2_out_dir / "land_basic_stats_v2_summary.json"
    _run_subprocess_timed(
        "snapshot_v2_stats",
        [py, str(v2_snap), "--as-of", v2_as, "--output", str(v2_out)],
    )
    log.info("V2 통계 요약 스냅샷: %s", v2_out)
    total_sec = time.perf_counter() - cycle_t0
    log.info(
        "[%s timing] monthly_cycle_total 소요=%.1fs (%.2f분)",
        "monthly_cycle",
        total_sec,
        total_sec / 60.0,
    )
    log.info("다음: SOP 검증(rehearse / verify_v2 / compare_count_snapshots) 후 promote")


if __name__ == "__main__":
    main()
