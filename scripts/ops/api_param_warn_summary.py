"""미지원 파라미터 경고 JSONL 요약 (집합 1단계 C-05).

입력: backend 미들웨어가 쓴 JSONL (기본 logs/api_param_warn.jsonl, 설정 API_PARAM_WARN_PATH).
출력: API·화면·파라미터별 빈도표(표준 출력). 파라미터 값은 원래 기록되지 않는다.

사용:
  python scripts/ops/api_param_warn_summary.py [JSONL 경로 ...] [--since 2026-11-01] [--by api|screen|param|all] [--top 50]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(paths: list[Path], since: str | None):
    for p in paths:
        if not p.exists():
            print(f"(없음) {p}", file=sys.stderr)
            continue
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if since and str(row.get("window_end", "")) < since:
                    continue
                yield row


def table(counter: Counter, headers: list[str], top: int) -> str:
    rows = counter.most_common(top)
    widths = [len(h) for h in headers]
    body = []
    for key, n in rows:
        cells = [*(key if isinstance(key, tuple) else (key,)), f"{n:,}"]
        widths = [max(w, len(str(c))) for w, c in zip(widths, cells)]
        body.append(cells)
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    out = [fmt.format(*headers), fmt.format(*["-" * w for w in widths])]
    out += [fmt.format(*map(str, c)) for c in body]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--since", default=None, help="window_end 가 이 값(ISO) 이상인 행만")
    ap.add_argument("--by", choices=["api", "screen", "param", "all"], default="all")
    ap.add_argument("--top", type=int, default=50)
    args = ap.parse_args(argv)
    paths = args.paths or [ROOT / "logs" / "api_param_warn.jsonl"]
    by_full: Counter = Counter()
    by_api: Counter = Counter()
    by_screen: Counter = Counter()
    by_param: Counter = Counter()
    for r in load(paths, args.since):
        n = int(r.get("count", 0) or 0)
        api = f"{r.get('method', '')} {r.get('route', '')}"
        screen = r.get("screen") or "(없음)"
        param = f"{r.get('location', '')}:{r.get('param', '')}"
        by_full[(api, screen, param)] += n
        by_api[api] += n
        by_screen[screen] += n
        by_param[(api, param)] += n
    if not by_full:
        print("기록 없음")
        return 0
    total = sum(by_full.values())
    print(f"합계 {total:,}건 · API {len(by_api)} · 화면 {len(by_screen)} · (API,파라미터) {len(by_param)}\n")
    if args.by in ("api", "all"):
        print(table(by_api, ["API", "빈도"], args.top), end="\n\n")
    if args.by in ("screen", "all"):
        print(table(by_screen, ["화면", "빈도"], args.top), end="\n\n")
    if args.by in ("param", "all"):
        print(table(by_param, ["API", "파라미터", "빈도"], args.top), end="\n\n")
    if args.by == "all":
        print(table(by_full, ["API", "화면", "파라미터", "빈도"], args.top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
