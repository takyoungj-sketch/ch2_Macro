"""집합부동산 월간 cycle 유틸."""

from __future__ import annotations

from pathlib import Path

GUKTO = Path(r"C:\startcoding\GUKTO")

SUBDIR_ALIASES = {
    "apartment": ("apartment", "아파트", "apt"),
    "rowhouse": ("rowhouse", "연립", "연립다세대"),
    "officetel": ("officetel", "오피스텔"),
}


def collective_raw_root(repo: Path, cycle_id: str) -> Path:
    return repo / "raw" / "집합부동산" / cycle_id


def collection_yyyymm_range_from_cycle_id(cycle_id: str) -> tuple[str, str]:
    """cycle_id YYYYMM → 직전 12개월 YYYYMM from..to (land/built 동일 규칙)."""
    y = int(cycle_id[:4])
    m = int(cycle_id[4:6])
    end_y, end_m = y, m - 1
    if end_m == 0:
        end_y -= 1
        end_m = 12
    start_y, start_m = end_y, end_m - 11
    while start_m <= 0:
        start_m += 12
        start_y -= 1
    return f"{start_y}{start_m:02d}", f"{end_y}{end_m:02d}"


def resolve_collective_xlsx_paths(repo: Path, cycle_id: str, *, use_legacy: bool) -> dict[str, Path]:
    if use_legacy:
        apt_dir = GUKTO / "아파트_매매" / "아파트_매매_정제"
        apt_files = sorted(apt_dir.glob("*.xlsx"))
        if not apt_files:
            raise FileNotFoundError(f"no apartment xlsx in {apt_dir}")
        return {
            "apartment_dir": apt_dir,
            "rowhouse": GUKTO / "연립다세대_매매" / "연립다세대_매매_정제" / "연립다세대_매매_정제.xlsx",
            "officetel": GUKTO / "오피스텔_매매" / "오피스텔_매매_정제" / "오피스텔_전국정제_정제.xlsx",
        }
    root = collective_raw_root(repo, cycle_id)
    return {
        "apartment_dir": root / "apartment",
        "rowhouse": root / "rowhouse" / "rowhouse.xlsx",
        "officetel": root / "officetel" / "officetel.xlsx",
    }
