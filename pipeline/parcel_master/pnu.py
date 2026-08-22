"""PNU 19자리 — 법정동10 + 필지구분1 + 본번4 + 부번4.

표제부 대지구분 `[10]` 은 0=대지·1=산이고, PNU 필지구분은 1=토지·2=산이다.
K-apt 고유번호는 이미 PNU이므로 이 매핑을 다시 적용하지 않는다.
"""

from __future__ import annotations

import re

_LOT_RE = re.compile(r"^(산)?\s*(\d+)(?:-(\d+))?$")


def beopjungri_code(sigungu: str, bjd: str) -> str | None:
    sg = re.sub(r"\D", "", sigungu or "")
    bd = re.sub(r"\D", "", bjd or "")
    if len(bd) >= 10:
        code = bd[:10]
    elif len(sg) >= 5 and bd:
        code = (sg[:5] + bd.zfill(5))[:10]
    elif len(sg) >= 10:
        code = sg[:10]
    else:
        return None
    return code if len(code) == 10 else None


def gbn_from_title(plat_code: str | None) -> str:
    p = (plat_code or "0").strip()
    if p in {"1", "산"}:
        return "2"
    return "1"


def parse_lot(lot: str | None) -> tuple[str, str, str] | None:
    """지번 → (bun4, ji4, pnu_gbn). 산 지번은 gbn=2."""
    t = re.sub(r"\s+", "", str(lot or ""))
    if not t:
        return None
    m = _LOT_RE.match(t)
    if not m:
        return None
    gbn = "2" if m.group(1) else "1"
    bun = m.group(2).zfill(4)[-4:]
    ji = (m.group(3) or "0").zfill(4)[-4:]
    if not bun.isdigit() or not ji.isdigit():
        return None
    return bun, ji, gbn


def make_pnu(bjd10: str, gbn: str, bun4: str, ji4: str) -> str | None:
    if len(bjd10) != 10 or not bjd10.isdigit():
        return None
    if gbn not in {"1", "2"}:
        return None
    bun = bun4.zfill(4)[-4:]
    ji = ji4.zfill(4)[-4:]
    if not bun.isdigit() or not ji.isdigit():
        return None
    return bjd10 + gbn + bun + ji


def pnu_from_title_parts(
    sigungu: str,
    bjd: str,
    plat_code: str | None,
    bun: str,
    ji: str,
) -> str | None:
    code = beopjungri_code(sigungu, bjd)
    if not code:
        return None
    return make_pnu(code, gbn_from_title(plat_code), bun, ji)


def pnu_from_tx(beopjungri: str | None, lot_number: str | None) -> str | None:
    code = re.sub(r"\D", "", str(beopjungri or ""))
    if len(code) != 10:
        return None
    parsed = parse_lot(lot_number)
    if not parsed:
        return None
    bun, ji, gbn = parsed
    return make_pnu(code, gbn, bun, ji)


def split_pnu(pnu: str) -> dict[str, str] | None:
    p = (pnu or "").strip()
    if len(p) != 19 or not p.isdigit():
        return None
    return {
        "pnu": p,
        "beopjungri_code": p[:10],
        "gbn": p[10],
        "bun": p[11:15],
        "ji": p[15:19],
        "sido_code": p[:2],
        "sigungu_code": p[:5],
    }


def structure_group(name: str | None) -> str:
    t = re.sub(r"\s+", "", name or "")
    if not t:
        return "other"
    if "목" in t:
        return "wood"
    if any(k in t for k in ("벽돌", "블록", "조적", "연와", "석조")):
        return "masonry"
    if "철골" in t and "철근" not in t:
        return "steel"
    if "철근" in t or "콘크리트" in t:
        return "RC"
    return "other"
