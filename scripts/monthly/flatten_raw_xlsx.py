"""
raw 토지 폴더 아래(하위 폴더 포함)의 모든 .xlsx 를 한 디렉터리로 복사(평탄화).

`collect.py --directory` 는 **바로 아래 층**의 .xlsx 만 읽으므로
`raw/토지/202605/서울/서울.xlsx` 처럼 깊게 두었다면 이 스크립트로 `flat_in/` 등에 모은 뒤
`run_pipeline.py --excel-dir` 에 넘긴다.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(description="하위 폴더 포함 .xlsx 를 한 폴더로 평탄화(복사)")
    p.add_argument("--source", required=True, help="재귀 탐색 루트 (예: raw/토지/202605)")
    p.add_argument("--dest", required=True, help="복사 대상 폴더 (없으면 생성)")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="복사하지 않고 계획만 stdout",
    )
    args = p.parse_args()

    src = Path(args.source).expanduser().resolve()
    dst = Path(args.dest).expanduser().resolve()
    if not src.is_dir():
        raise SystemExit(f"소스 폴더가 없습니다: {src}")

    files = sorted(src.rglob("*.xlsx"), key=lambda x: str(x).lower())
    if not files:
        raise SystemExit(f".xlsx 가 없습니다: {src}")

    used: dict[str, int] = {}
    plan: list[tuple[Path, Path]] = []
    for f in files:
        name = f.name
        key = name.lower()
        n = used.get(key, 0)
        used[key] = n + 1
        if n > 0:
            stem = f.stem
            name = f"{stem}__dup{n}{f.suffix}"
        plan.append((f, dst / name))

    print(f"평탄화: {len(plan)}개 파일 → {dst}")
    for src_f, out_f in plan:
        print(f"  {src_f.relative_to(src)} -> {out_f.name}")

    if args.dry_run:
        return

    dst.mkdir(parents=True, exist_ok=True)
    for src_f, out_f in plan:
        shutil.copy2(src_f, out_f)
    print("완료.")


if __name__ == "__main__":
    main()
