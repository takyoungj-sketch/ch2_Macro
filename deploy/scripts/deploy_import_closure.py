"""배포 범위 점검 — scope가 올리는 backend 코드의 import 대상 중 범위 밖 파일을 찾는다.

복합(built) 배포는 backend/app 전체가 아니라 일부 패키지만 서버로 보낸다. 이때 그
패키지가 import하는 공통 모듈(예: app.region_sido)이 범위 밖이면, 서버의 구버전 파일과
섞여 import 오류가 날 수 있다 (2026-11-11 코덱스 검수 P1).

사용:
  python deploy/scripts/deploy_import_closure.py --covered <scope가 올리는 경로...> --start <따라갈 시작 경로...>
출력: 범위 밖 의존 파일의 repo 상대 경로를 한 줄에 하나씩 (없으면 빈 출력).

정적 분석이다 — 함수 안 import도 포함한다. ``app.*`` 모듈과, backend가 sys.path로
끌어오는 ``pipeline/<name>.py`` 모듈(예: region_canonical)을 따라간다.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
PIPELINE = REPO / "pipeline"


def _module_file(module: str) -> Path | None:
    parts = module.split(".")
    if parts[0] == "app":
        base = BACKEND.joinpath(*parts)
        for cand in (base.with_suffix(".py"), base / "__init__.py"):
            if cand.is_file():
                return cand
        return None
    cand = PIPELINE.joinpath(*parts).with_suffix(".py")
    return cand if cand.is_file() else None


def _package_of(path: Path) -> list[str]:
    rel = path.relative_to(BACKEND if BACKEND in path.parents else PIPELINE).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        return parts[:-1]
    return parts[:-1]


def _imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    out: set[str] = set()
    pkg = _package_of(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg[: len(pkg) - (node.level - 1)] if node.level > 1 else pkg
                mod = ".".join([*base, node.module] if node.module else base)
            else:
                mod = node.module or ""
            if not mod:
                continue
            out.add(mod)
            # from app.x import y — y가 하위 모듈일 수 있다
            out.update(f"{mod}.{alias.name}" for alias in node.names)
    return out


def _resolve(module: str) -> Path | None:
    # 'app.a.b.c' → 가장 긴 접두로 파일을 찾고, 지나는 패키지 __init__ 도 포함
    parts = module.split(".")
    for end in range(len(parts), 0, -1):
        f = _module_file(".".join(parts[:end]))
        if f is not None:
            return f
    return None


def _parent_inits(path: Path) -> list[Path]:
    out = []
    if BACKEND not in path.parents:
        return out
    cur = path.parent
    while cur != BACKEND and BACKEND in cur.parents:
        init = cur / "__init__.py"
        if init.is_file():
            out.append(init)
        cur = cur.parent
    return out


def closure(covered: list[str], start_from: list[str] | None = None) -> list[str]:
    """``start_from`` 패키지가 따라가는 import 중 ``covered`` 밖 파일.

    ``main.py`` 처럼 모든 라우터를 끌어오는 진입점은 시작점에서 빼고(그건 서버 import
    점검이 맡는다) scope 고유 패키지만 시작점으로 둔다.
    """
    covered_paths = [(REPO / c).resolve() for c in covered]

    def is_covered(p: Path) -> bool:
        return any(p == c or c in p.parents for c in covered_paths)

    start: list[Path] = []
    for c in [(REPO / x).resolve() for x in (start_from or covered)]:
        if c.is_file() and c.suffix == ".py":
            start.append(c)
        elif c.is_dir():
            start.extend(sorted(c.rglob("*.py")))
    seen: set[Path] = set()
    stack = list(start)
    while stack:
        f = stack.pop()
        if f in seen:
            continue
        seen.add(f)
        for dep in [*_parent_inits(f), *filter(None, (_resolve(m) for m in _imports(f)))]:
            if dep not in seen:
                stack.append(dep)
    missing = sorted(p for p in seen if not is_covered(p))
    return [p.relative_to(REPO).as_posix() for p in missing]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--covered", nargs="+", required=True, help="scope가 올리는 repo 상대 경로")
    ap.add_argument("--start", nargs="+", default=None, help="import를 따라갈 시작 경로 (기본: --covered)")
    args = ap.parse_args()
    for rel in closure(args.covered, args.start):
        print(rel)


if __name__ == "__main__":
    main()
