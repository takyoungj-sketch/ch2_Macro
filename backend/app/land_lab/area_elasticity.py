"""토지 면적 탄성(광평수) — 유형·게이트·1차 할당.

제품 `land_regression.py` 기본 체크를 바꾸지 않는다.
선정은 거래량·면적 분포만 쓴다 (단가·β 금지).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Literal

LAND_CATEGORIES = ("대", "전", "답", "임야")
PRIMARY_CATEGORIES = ("대", "전", "답")
REGION_TYPES = ("metro_gu", "cap_city", "prov_city", "urban_rural", "gun")
RegionType = Literal["metro_gu", "cap_city", "prov_city", "urban_rural", "gun"]

# 비현실 면적 상한 (단일 거래). 면적 IQR은 쓰지 않는다.
AREA_MAX_SQM = 10_000_000.0
WINDOW_YEARS = 5
PHASE1_PER_TYPE = 5

# 지방 도농복합시. 수도권 시는 cap_city가 우선이라 여기 있어도 수도권에서는 안 탄다.
URBAN_RURAL_CITIES = frozenset(
    {
        "평택시",
        "파주시",
        "남양주시",
        "용인시",
        "이천시",
        "안성시",
        "김포시",
        "화성시",
        "광주시",
        "양주시",
        "포천시",
        "여주시",
        "춘천시",
        "원주시",
        "강릉시",
        "삼척시",
        "청주시",
        "충주시",
        "제천시",
        "천안시",
        "공주시",
        "보령시",
        "아산시",
        "서산시",
        "논산시",
        "계룡시",
        "당진시",
        "전주시",
        "군산시",
        "익산시",
        "정읍시",
        "남원시",
        "김제시",
        "여수시",
        "순천시",
        "나주시",
        "광양시",
        "포항시",
        "경주시",
        "김천시",
        "안동시",
        "구미시",
        "영주시",
        "영천시",
        "상주시",
        "문경시",
        "경산시",
        "창원시",
        "진주시",
        "통영시",
        "사천시",
        "김해시",
        "밀양시",
        "거제시",
        "양산시",
        "제주시",
        "서귀포시",
    }
)
CAPITAL_SIDO = frozenset({"경기도"})
SEJONG_SIDO = frozenset({"세종특별자치시"})


@dataclass(frozen=True)
class GateSpec:
    n_min: int
    p90_p50_min: float | None = None
    n_ge_300_min: int | None = None
    p90_min: float | None = None
    n_ge_500_min: int | None = None
    n_ge_1000_min: int | None = None
    metro_width: bool = False  # P90≥300 또는 300㎡+ ≥30


def gate_spec(region_type: str, land_category: str) -> GateSpec | None:
    """유형×지목 게이트. 없으면 적격 아님 (임야·대도시 전답 등)."""
    cat = (land_category or "").strip()
    rt = (region_type or "").strip()
    if rt == "metro_gu" and cat == "대":
        return GateSpec(n_min=150, p90_p50_min=2.0, metro_width=True)
    if rt in {"cap_city", "prov_city", "urban_rural"} and cat == "대":
        return GateSpec(n_min=100, p90_p50_min=2.5, n_ge_500_min=20)
    if rt in {"cap_city", "prov_city", "urban_rural"} and cat in {"전", "답"}:
        return GateSpec(n_min=100, p90_p50_min=3.0, n_ge_1000_min=20)
    if rt == "gun" and cat in {"전", "답"}:
        return GateSpec(n_min=80, p90_p50_min=3.0, n_ge_1000_min=20)
    if rt == "gun" and cat == "대":
        return GateSpec(n_min=80, n_ge_500_min=15)
    return None


def city_stem(sigungu_name: str) -> str:
    """'청주시 흥덕구' → '청주시', '화성시'/'강남구' → 그대로."""
    parts = [p for p in (sigungu_name or "").split() if p]
    if len(parts) >= 2 and parts[0].endswith("시") and parts[-1].endswith("구"):
        return parts[0]
    return (sigungu_name or "").strip()


def classify_region_type(sido_name: str, sigungu_name: str) -> RegionType:
    sido = (sido_name or "").strip()
    name = (sigungu_name or "").strip()
    stem = city_stem(name)
    leaf = name.split()[-1] if name else ""

    if leaf.endswith("군") or (stem.endswith("군") and " " not in name):
        return "gun"
    if sido in SEJONG_SIDO:
        return "urban_rural"
    if leaf.endswith("구") and not stem.endswith("시"):
        return "metro_gu"
    if sido in CAPITAL_SIDO:
        return "cap_city"
    if stem in URBAN_RURAL_CITIES or name in URBAN_RURAL_CITIES:
        return "urban_rural"
    return "prov_city"


def n_tier(n: int) -> str:
    if n < 50:
        return "exclude"
    if n < 80:
        return "note"
    if n < 150:
        return "ok"
    if n < 300:
        return "good"
    return "better"


def b_preview_ok(n_dongs: int | None, dong_n_median: float | None) -> bool:
    if n_dongs is None or dong_n_median is None:
        return False
    return int(n_dongs) >= 5 and float(dong_n_median) >= 8.0


def _ratio(p90: float | None, p50: float | None) -> float | None:
    if p90 is None or p50 is None or p50 <= 0:
        return None
    return float(p90) / float(p50)


def evaluate_gate(
    *,
    region_type: str,
    land_category: str,
    n: int,
    area_p50: float | None,
    area_p90: float | None,
    n_ge_300: int = 0,
    n_ge_500: int = 0,
    n_ge_1000: int = 0,
) -> tuple[bool, list[str], float | None]:
    reasons: list[str] = []
    spec = gate_spec(region_type, land_category)
    p90_p50 = _ratio(area_p90, area_p50)
    if spec is None:
        if land_category == "임야":
            reasons.append("optional_imya")
        else:
            reasons.append("no_gate_for_type_jimok")
        return False, reasons, p90_p50

    if n < spec.n_min:
        reasons.append(f"n<{spec.n_min}")
    if spec.p90_p50_min is not None:
        if p90_p50 is None:
            reasons.append("p90_p50_missing")
        elif p90_p50 < spec.p90_p50_min:
            reasons.append(f"p90_p50<{spec.p90_p50_min}")
    if spec.metro_width:
        p90_ok = area_p90 is not None and area_p90 >= 300
        tail_ok = n_ge_300 >= 30
        if not (p90_ok or tail_ok):
            reasons.append("metro_width")
    if spec.n_ge_500_min is not None and n_ge_500 < spec.n_ge_500_min:
        reasons.append(f"n_ge_500<{spec.n_ge_500_min}")
    if spec.n_ge_1000_min is not None and n_ge_1000 < spec.n_ge_1000_min:
        reasons.append(f"n_ge_1000<{spec.n_ge_1000_min}")
    return (len(reasons) == 0), reasons, p90_p50


@dataclass
class CellRow:
    sido_code: str
    sido_name: str
    sigungu_code: str
    sigungu_name: str
    land_category: str
    region_type: str
    n: int
    area_p10: float | None
    area_p50: float | None
    area_p75: float | None
    area_p90: float | None
    p90_p50: float | None
    n_ge_300: int
    n_ge_500: int
    n_ge_1000: int
    n_ge_3000: int
    n_ge_5000: int
    n_dongs: int
    dong_n_median: float | None
    eligible: bool
    gate_reasons: list[str] = field(default_factory=list)
    n_tier: str = ""
    b_preview: str = "B_skip"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("area_p10", "area_p50", "area_p75", "area_p90", "p90_p50", "dong_n_median"):
            if d[k] is not None:
                d[k] = round(float(d[k]), 4)
        return d


def cell_from_agg(row: dict[str, Any]) -> CellRow:
    sido_name = str(row.get("sido_name") or "").strip()
    sigungu_name = str(row.get("sigungu_name") or "").strip()
    cat = str(row.get("land_category") or "").strip()
    rt = classify_region_type(sido_name, sigungu_name)
    n = int(row.get("n") or 0)
    p50 = _f(row.get("area_p50"))
    p90 = _f(row.get("area_p90"))
    n300 = int(row.get("n_ge_300") or 0)
    n500 = int(row.get("n_ge_500") or 0)
    n1000 = int(row.get("n_ge_1000") or 0)
    ok, reasons, ratio = evaluate_gate(
        region_type=rt,
        land_category=cat,
        n=n,
        area_p50=p50,
        area_p90=p90,
        n_ge_300=n300,
        n_ge_500=n500,
        n_ge_1000=n1000,
    )
    n_dongs = int(row.get("n_dongs") or 0)
    dong_med = _f(row.get("dong_n_median"))
    return CellRow(
        sido_code=str(row.get("sido_code") or "").strip(),
        sido_name=sido_name,
        sigungu_code=str(row.get("sigungu_code") or "").strip(),
        sigungu_name=sigungu_name,
        land_category=cat,
        region_type=rt,
        n=n,
        area_p10=_f(row.get("area_p10")),
        area_p50=p50,
        area_p75=_f(row.get("area_p75")),
        area_p90=p90,
        p90_p50=ratio,
        n_ge_300=n300,
        n_ge_500=n500,
        n_ge_1000=n1000,
        n_ge_3000=int(row.get("n_ge_3000") or 0),
        n_ge_5000=int(row.get("n_ge_5000") or 0),
        n_dongs=n_dongs,
        dong_n_median=dong_med,
        eligible=ok,
        gate_reasons=reasons,
        n_tier=n_tier(n),
        b_preview="B_ok" if b_preview_ok(n_dongs, dong_med) else "B_skip",
    )


def spectrum_key(cell: CellRow) -> tuple[float, int, int]:
    """유형 안 우선순위: P90/P50 · 꼬리 건수 · n. 단가 없음."""
    ratio = float(cell.p90_p50 or 0.0)
    if cell.land_category == "대":
        tail = cell.n_ge_500 if cell.n_ge_500 else cell.n_ge_300
    else:
        tail = cell.n_ge_1000
    return (ratio, int(tail), int(cell.n))


def select_phase1(
    cells: Iterable[CellRow],
    *,
    per_type: int = PHASE1_PER_TYPE,
) -> list[CellRow]:
    eligible = [c for c in cells if c.eligible]
    by_type: dict[str, list[CellRow]] = {t: [] for t in REGION_TYPES}
    for c in eligible:
        by_type.setdefault(c.region_type, []).append(c)

    out: list[CellRow] = []
    out.extend(_pick_unique_sigungu(by_type["metro_gu"], per_type, cats=("대",)))
    out.extend(_pick_mixed(by_type["cap_city"], per_type, dae_n=3))
    out.extend(_pick_mixed(by_type["prov_city"], per_type, dae_n=3))
    out.extend(_pick_urban_rural(by_type["urban_rural"], per_type))
    out.extend(_pick_unique_sigungu(by_type["gun"], per_type, cats=("전", "답", "대")))
    return out


def _pick_unique_sigungu(
    cells: list[CellRow],
    k: int,
    *,
    cats: tuple[str, ...],
) -> list[CellRow]:
    ranked = sorted(
        [c for c in cells if c.land_category in cats],
        key=spectrum_key,
        reverse=True,
    )
    seen: set[str] = set()
    out: list[CellRow] = []
    for c in ranked:
        if c.sigungu_code in seen:
            continue
        seen.add(c.sigungu_code)
        out.append(c)
        if len(out) >= k:
            break
    return out


def _pick_mixed(cells: list[CellRow], k: int, *, dae_n: int) -> list[CellRow]:
    dae = _pick_unique_sigungu(cells, dae_n, cats=("대",))
    farm_k = max(0, k - len(dae))
    used = {c.sigungu_code for c in dae}
    farm = []
    for c in _pick_unique_sigungu(cells, k + farm_k, cats=("전", "답")):
        if c.sigungu_code in used:
            continue
        farm.append(c)
        used.add(c.sigungu_code)
        if len(farm) >= farm_k:
            break
    return (dae + farm)[:k]


def _pick_urban_rural(cells: list[CellRow], k: int) -> list[CellRow]:
    by_sgg: dict[str, list[CellRow]] = {}
    for c in cells:
        by_sgg.setdefault(c.sigungu_code, []).append(c)
    pairs: list[tuple[tuple[float, int, int], list[CellRow]]] = []
    for group in by_sgg.values():
        dae = max((c for c in group if c.land_category == "대"), key=spectrum_key, default=None)
        farm = max(
            (c for c in group if c.land_category in {"전", "답"}),
            key=spectrum_key,
            default=None,
        )
        if dae and farm:
            pairs.append((spectrum_key(dae), [dae, farm]))
    pairs.sort(key=lambda x: x[0], reverse=True)
    out: list[CellRow] = []
    used: set[str] = set()
    for _, pair in pairs:
        if len(out) >= k:
            break
        if len(out) + 2 <= k:
            out.extend(pair)
            used.add(pair[0].sigungu_code)
        elif len(out) + 1 <= k:
            out.append(pair[0])
            used.add(pair[0].sigungu_code)
    if len(out) < k:
        rest = [c for c in cells if c.sigungu_code not in used]
        for c in _pick_unique_sigungu(rest, k - len(out), cats=PRIMARY_CATEGORIES):
            out.append(c)
            if len(out) >= k:
                break
    return out[:k]


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:  # NaN
        return None
    return x
