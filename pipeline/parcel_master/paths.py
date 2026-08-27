from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RAW_ADD = REPO / "raw" / "raw addition"
CACHE = Path(__file__).resolve().parent / "_cache"

SNAPSHOTS = {
    "2024-09": "2024년+09월",
    "2025-07": "2025년+07월",
    "2026-07": "2026년+07월",
}
PILOT_SIDO = ("30", "43")
ALL_SIDO = (
    "11",
    "12",
    "26",
    "27",
    "28",
    "30",
    "31",
    "36",
    "41",
    "43",
    "44",
    "47",
    "48",
    "50",
    "51",
    "52",
)
EXPAND_SIDO = tuple(s for s in ALL_SIDO if s not in PILOT_SIDO)
ISOLATED_SIDO = frozenset({"99", "38", "00", "46", "0"})

TITLE_COLS = {
    "pk": 0,
    "ledger_kind": 2,
    "building_name": 7,
    "sigungu_code": 8,
    "bjd_code": 9,
    "plat_gb": 10,
    "bun": 11,
    "ji": 12,
    "dong_name": 22,
    "title_land": 25,
    "arch_area": 26,
    "gross_area": 28,
    "plat_area": 29,
    "struct_name": 32,
    "main_purpose": 35,
    "purpose_detail": 36,
    "households": 40,
    "floors_above": 43,
    "floors_below": 44,
    "approve_date": 60,
    # 대수만. 면적 열 [51][53][55][57] 은 적재하지 않는다.
    "park_mech_in": 50,
    "park_mech_out": 52,
    "park_self_in": 54,
    "park_self_out": 56,
    "ho_cnt": 66,
}


def _dir_named(parent: Path, token: str) -> Path:
    for p in parent.iterdir():
        if p.is_dir() and token in p.name:
            return p
    raise FileNotFoundError(f"{parent} 안에 '{token}' 폴더 없음")


def bldrgst_dir() -> Path:
    return _dir_named(RAW_ADD, "건축물대장")


def land_ledger_dir() -> Path:
    return _dir_named(RAW_ADD, "토지대장csv")


def zone_dir() -> Path:
    return _dir_named(RAW_ADD, "토지이용계획csv")


def land_price_dir() -> Path:
    return _dir_named(RAW_ADD, "개별공시지가")


def kapt_dir() -> Path:
    return _dir_named(RAW_ADD, "K-apt")


def title_path(snapshot: str) -> Path:
    tag = SNAPSHOTS[snapshot]
    return bldrgst_dir() / f"국토교통부_건축물대장_표제부+({tag})" / "mart_djy_03.txt"


def kapt_pnu_xlsx() -> Path:
    matches = sorted(
        p
        for p in kapt_dir().iterdir()
        if p.suffix.lower() == ".xlsx" and "필지" in p.name and not p.name.startswith("~")
    )
    if not matches:
        raise FileNotFoundError("K-apt 단지_필지고유번호 xlsx 없음")
    return matches[-1]


def kapt_info_xlsx() -> Path:
    matches = sorted(
        p
        for p in kapt_dir().iterdir()
        if p.suffix.lower() == ".xlsx" and "기본정보" in p.name and not p.name.startswith("~")
    )
    if not matches:
        raise FileNotFoundError("K-apt 단지_기본정보 xlsx 없음")
    return matches[-1]


def land_ledger_csv(sido: str) -> Path | None:
    root = land_ledger_dir()
    dirs = sorted(root.glob(f"AL_D003_{sido}_*"))
    if not dirs:
        return None
    csvs = list(dirs[-1].glob("*.csv"))
    return csvs[-1] if csvs else None


def zone_csv(sido: str) -> Path | None:
    root = zone_dir()
    dirs = sorted(root.glob(f"AL_D155_{sido}_*"))
    if not dirs:
        return None
    csvs = [
        p
        for p in dirs[-1].glob("*.csv")
        if "head" not in p.name.lower()
    ]
    return csvs[-1] if csvs else None


def zone_snapshot(sido: str) -> str:
    root = zone_dir()
    dirs = sorted(root.glob(f"AL_D155_{sido}_*"))
    if not dirs:
        return ""
    parts = dirs[-1].name.split("_")
    return parts[3] if len(parts) >= 4 else dirs[-1].name


def land_price_csv(sido: str) -> Path | None:
    root = land_price_dir()
    dirs = sorted(root.glob(f"AL_D151_{sido}_*"))
    if not dirs:
        return None
    csvs = list(dirs[-1].glob("*.csv"))
    return csvs[-1] if csvs else None


def land_price_snapshot(sido: str) -> str:
    root = land_price_dir()
    dirs = sorted(root.glob(f"AL_D151_{sido}_*"))
    if not dirs:
        return ""
    parts = dirs[-1].name.split("_")
    return parts[3] if len(parts) >= 4 else dirs[-1].name


def land_price_sidos() -> tuple[str, ...]:
    root = land_price_dir()
    out: list[str] = []
    for d in sorted(root.glob("AL_D151_*")):
        parts = d.name.split("_")
        if len(parts) >= 3 and parts[2].isdigit():
            out.append(parts[2])
    return tuple(out)
