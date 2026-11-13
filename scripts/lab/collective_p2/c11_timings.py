"""Phase C-11 — 단계·창·지역별 소요(빌더 tqdm 로그) 표.

tqdm 줄 `desc: k/N [경과<남은...]` 의 경과(누적)를 이어 지역별 소요를 구한다. 지역 순서 = _distinct_addr1(가나다).
사용: python c11_timings.py <log> [<log> ...]   출력: 표준출력(markdown)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ADDR1 = ["강원", "경기", "경남", "경북", "대구", "대전", "부산", "서울", "세종", "울산", "인천", "전남광주", "전북", "제주", "충남", "충북"]
PAT = re.compile(r"^(?P<desc>[^:\r\n]+):\s+\d+%\|[^|]*\|\s*(?P<k>\d+)/(?P<n>\d+)\s+\[(?P<el>[\d:]+)<")


def secs(s: str) -> int:
    p = [int(x) for x in s.split(":")]
    while len(p) < 3:
        p.insert(0, 0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def parse(path: Path) -> dict[str, dict[int, int]]:
    raw = path.read_text(encoding="utf-8", errors="replace").replace("\r", "\n")
    out: dict[str, dict[int, int]] = {}
    for line in raw.splitlines():
        m = PAT.match(line.strip())
        if m:
            out.setdefault(m["desc"].strip(), {})[int(m["k"])] = secs(m["el"])
    return out


def fmt(s: int) -> str:
    return f"{s // 60}분 {s % 60:02d}초" if s >= 60 else f"{s}초"


def main():
    for p in map(Path, sys.argv[1:]):
        data = parse(p)
        print(f"\n### {p.name}\n")
        descs = list(data)
        print("| 지역 | " + " | ".join(descs) + " |")
        print("|---|" + "---|" * len(descs))
        n = max(max(v) for v in data.values()) if data else 0
        for i in range(1, n + 1):
            cells = []
            for d in descs:
                v = data[d]
                cells.append(fmt(v[i] - v.get(i - 1, 0)) if i in v and (i - 1 in v or i == 1) else "")
            name = ADDR1[i - 1] if n == len(ADDR1) else str(i)
            print(f"| {name} | " + " | ".join(cells) + " |")
        print("| **합** | " + " | ".join(fmt(max(data[d].values())) for d in descs) + " |")


if __name__ == "__main__":
    main()
