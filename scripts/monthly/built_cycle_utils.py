"""
복합부동산 월간 배치 유틸 — raw 경로 해석, cycle_id ↔ 수집 연월 범위.
"""

from __future__ import annotations

from pathlib import Path

from cycle_utils import last_data_yyyymm_from_cycle_id, _validate_cycle_id

ASSET_TYPES = ("commercial", "factory", "detached")

PREFERRED_XLSX: dict[str, list[str]] = {
    "commercial": ["일반상가_정제.xlsx", "일반상가.xlsx"],
    "factory": ["공장창고_매매_정제.xlsx", "공장창고.xlsx"],
    "detached": ["단독다가구_매매_정제.xlsx", "단독다가구.xlsx"],
}

SUBDIR_ALIASES: dict[str, tuple[str, ...]] = {
    "commercial": ("commercial", "상업", "일반상가"),
    "factory": ("factory", "공장", "공장창고"),
    "detached": ("detached", "단독", "단독다가구"),
}


def collection_yyyymm_range_from_cycle_id(cycle_id: str) -> tuple[str, str]:
    """직전 12개월 수집 가정. 반환 (from_yyyymm, to_yyyymm)."""
    _validate_cycle_id(cycle_id)
    to_yyyymm = last_data_yyyymm_from_cycle_id(cycle_id)
    ty, tm = int(to_yyyymm[:4]), int(to_yyyymm[4:6])
    # 11 months before to_yyyymm inclusive → 12 months total
    months: list[tuple[int, int]] = []
    y, m = ty, tm
    for _ in range(12):
        months.append((y, m))
        if m == 1:
            y, m = y - 1, 12
        else:
            m -= 1
    months.reverse()
    fy, fm = months[0]
    return f"{fy:04d}{fm:02d}", to_yyyymm


def built_raw_root(repo: Path, cycle_id: str) -> Path:
    return repo / "raw" / "복합부동산" / cycle_id


def _pick_xlsx(folder: Path, preferred_names: list[str], label: str) -> Path:
    if not folder.is_dir():
        raise FileNotFoundError(f"{label}: 폴더 없음 — {folder}")
    for name in preferred_names:
        p = folder / name
        if p.is_file():
            return p
    xs = sorted(folder.glob("*.xlsx"), key=lambda p: p.name.lower())
    if len(xs) == 1:
        return xs[0]
    if not xs:
        raise FileNotFoundError(f"{label}: xlsx 없음 — {folder}")
    names = ", ".join(p.name for p in xs[:5])
    raise SystemExit(
        f"{label}: xlsx가 여러 개입니다 ({folder}). "
        f"후보: {names}. preferred 파일명을 맞추거나 --*-path 로 지정하세요."
    )


def _find_subdir(root: Path, aliases: tuple[str, ...]) -> Path | None:
    for alias in aliases:
        p = root / alias
        if p.is_dir():
            return p
    lower_map = {c.name.lower(): c for c in root.iterdir() if c.is_dir()}
    for alias in aliases:
        for name, path in lower_map.items():
            if alias.lower() in name:
                return path
    return None


def resolve_built_xlsx_paths(
    repo: Path,
    cycle_id: str,
    *,
    overrides: dict[str, Path | None] | None = None,
) -> dict[str, Path]:
    """
    `raw/복합부동산/{cycle_id}/{commercial|factory|detached}/` 에서 정제 xlsx 를 찾는다.
    overrides 에 Path 가 있으면 해당 경로 우선.
    """
    root = built_raw_root(repo, cycle_id)
    if not root.is_dir():
        raise SystemExit(f"raw 폴더가 없습니다: {root}")

    out: dict[str, Path] = {}
    overrides = overrides or {}
    for asset in ASSET_TYPES:
        if overrides.get(asset) is not None:
            p = overrides[asset].expanduser().resolve()
            if not p.is_file():
                raise SystemExit(f"--{asset} path not found: {p}")
            out[asset] = p
            continue

        sub = _find_subdir(root, SUBDIR_ALIASES[asset])
        if sub is not None:
            out[asset] = _pick_xlsx(sub, PREFERRED_XLSX[asset], asset)
            continue

        # flat: root 에 preferred 파일명
        for name in PREFERRED_XLSX[asset]:
            flat = root / name
            if flat.is_file():
                out[asset] = flat
                break
        else:
            raise FileNotFoundError(
                f"{asset}: {root} 아래 서브폴더({SUBDIR_ALIASES[asset]}) 또는 "
                f"{PREFERRED_XLSX[asset][0]} 를 찾을 수 없습니다."
            )
    return out
