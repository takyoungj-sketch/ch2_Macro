# -*- coding: utf-8 -*-
"""Phase 1a — region code change classification (read-only).

Classifies master「존재」leaf missing from region_codes and related abolished
twins into: code_reissue | rename | merge | split | unresolved.

No DB writes. Report only.

Usage:
  cd backend
  .venv/Scripts/python.exe ../pipeline/classify_region_code_changes_1a.py
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "pipeline"))

MASTER = ROOT / "data" / "region_codes" / "법정동코드 전체자료(260701).txt"
OUT_DIR = ROOT / "docs" / "reports"
OUT_MD = OUT_DIR / "REGION_CODE_PHASE1A_CLASSIFICATION.md"
OUT_CSV = OUT_DIR / "REGION_CODE_PHASE1A_CLASSIFICATION.csv"

TYPES = ("code_reissue", "rename", "merge", "split", "unresolved")


@dataclass
class MasterRow:
    code: str
    name: str
    status: str
    sido: str
    sigungu: str
    eup: str
    leaf: str


@dataclass
class Classified:
    change_type: str
    historical_code: str
    historical_name: str
    historical_status: str
    canonical_code: str
    canonical_name: str
    canonical_candidates: str
    rationale: str
    in_region_codes: bool
    region_codes_active: bool | None
    region_codes_eup_name: str
    tx_count_historical: int
    tx_count_canonical: int
    stats_v2_historical: int
    stats_v2_canonical: int
    exemplar: str = ""
    notes: str = ""


def _emd_and_leaf(full_name: str) -> tuple[str, str]:
    """읍면동·리/동 leaf 추출. 분구(시→구)에서도 leaf·읍면 키가 안정되도록."""
    toks = full_name.split()
    if not toks:
        return "", ""
    leaf = toks[-1]
    if leaf.endswith("리") and len(toks) >= 2:
        return toks[-2], leaf
    # 동·가 leaf: 읍면동 단위가 곧 leaf (상위는 구/시)
    if leaf.endswith(("동", "가", "로")):
        return leaf, leaf
    if len(toks) >= 2:
        return toks[-2], leaf
    return "", leaf


def _parse_master(path: Path) -> dict[str, MasterRow]:
    text_ko = path.read_bytes().decode("cp949", errors="replace")
    out: dict[str, MasterRow] = {}
    for line in text_ko.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        code, name, status = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if len(code) != 10:
            continue
        toks = name.split()
        sido = toks[0] if toks else ""
        eup, leaf = _emd_and_leaf(name)
        sigungu = code[:5]
        out[code] = MasterRow(code, name, status, sido, sigungu, eup, leaf)
    return out


def _eup_stem(eup: str) -> str:
    s = (eup or "").strip()
    if s.endswith(("읍", "면", "동")) and len(s) >= 2:
        return s[:-1]
    return s


def _eup_myeon_pair(a: str, b: str) -> bool:
    """면↔읍 승격 표기 (동일 stem)."""
    if not a or not b:
        return False
    if a == b:
        return False
    return _eup_stem(a) == _eup_stem(b) and {
        a[-1] if a else "",
        b[-1] if b else "",
    } <= {"읍", "면"}


def _leaf_rows(
    master: dict[str, MasterRow], *, status: str
) -> list[MasterRow]:
    rows = []
    for r in master.values():
        if r.status != status:
            continue
        if r.code.endswith("00"):
            continue
        if r.code[2:] == "00000000" or r.code[5:] == "00000":
            continue
        rows.append(r)
    return rows


def _city_key(name: str, code: str) -> str:
    """시·군 키 (분구 전후 동일). 구는 제외."""
    for t in name.split():
        if t.endswith("시") or (t.endswith("군") and not t.endswith("구")):
            return t
    return code[:4]


def _find_twins(
    anchor: MasterRow,
    pool: list[MasterRow],
) -> tuple[list[MasterRow], str]:
    """Find counterpart codes for anchor. Prefer tighter keys.

    Returns (candidates, match_mode).
    """
    sido2 = anchor.code[:2]
    city = _city_key(anchor.name, anchor.code)

    same_sg = [r for r in pool if r.sigungu == anchor.sigungu and r.leaf == anchor.leaf]
    same_sg_eup = [r for r in same_sg if r.eup == anchor.eup]
    if same_sg_eup:
        return same_sg_eup, "same_sg_eup"
    same_sg_stem = [
        r for r in same_sg if _eup_myeon_pair(r.eup, anchor.eup) or r.eup == anchor.eup
    ]
    if same_sg_stem:
        return same_sg_stem, "same_sg_stem"

    # 분구: 동일 시·군 + 동일 읍면동·리. 시도 전체 leaf 매칭 금지(동명 충돌).
    cross = [
        r
        for r in pool
        if r.code[:2] == sido2
        and r.code != anchor.code
        and r.leaf == anchor.leaf
        and _city_key(r.name, r.code) == city
    ]
    cross_eup = [r for r in cross if r.eup == anchor.eup]
    if cross_eup:
        return cross_eup, "cross_sg_eup"
    cross_stem = [r for r in cross if _eup_myeon_pair(r.eup, anchor.eup)]
    if cross_stem:
        return cross_stem, "cross_sg_stem"
    if same_sg:
        return same_sg, "same_sg_leaf"
    return [], "none"


def _reissue_rationale(old: MasterRow, new: MasterRow, mode: str) -> str:
    if _eup_myeon_pair(old.eup, new.eup):
        return (
            f"면↔읍 승격 1:1 — '{old.eup}'→'{new.eup}', 리명 '{old.leaf}' 동일, "
            f"코드 {old.code}→{new.code}"
        )
    if old.sigungu != new.sigungu and old.eup == new.eup:
        return (
            f"분구·시군구코드 재부여 1:1 ({mode}) — 읍면동·리명 동일 "
            f"('{old.eup}' '{old.leaf}'), 시군구 {old.sigungu}→{new.sigungu}, "
            f"코드 {old.code}→{new.code}"
        )
    if old.eup != new.eup:
        return (
            f"읍면동·코드 재부여 1:1 ({mode}) — '{old.eup}'→'{new.eup}', "
            f"리 '{old.leaf}', {old.code}→{new.code}"
        )
    return (
        f"코드 재부여 1:1 ({mode}) — '{old.name}' → '{new.name}' ({old.code}→{new.code})"
    )


def classify(
    master: dict[str, MasterRow],
    db_info: dict[str, dict],
    tx_counts: dict[str, int],
    stats_counts: dict[str, int],
) -> list[Classified]:
    exist = _leaf_rows(master, status="존재")
    abolished = _leaf_rows(master, status="폐지")

    # missing 존재 = not in region_codes at all
    missing_exist = [r for r in exist if r.code not in db_info]
    # stale = master 폐지 AND in DB with is_active true
    stale_abol = [
        r
        for r in abolished
        if r.code in db_info and db_info[r.code].get("is_active")
    ]

    results: list[Classified] = []
    seen_pair: set[tuple[str, str]] = set()

    def add(c: Classified) -> None:
        key = (c.historical_code, c.canonical_code or "")
        if key in seen_pair and c.canonical_code:
            return
        seen_pair.add(key)
        results.append(c)

    # --- Primary: each stale abolished active row (historical side) ---
    for old in stale_abol:
        candidates, mode = _find_twins(old, exist)
        cand_str = "; ".join(f"{n.code}|{n.name}" for n in candidates)

        db = db_info.get(old.code, {})
        h_tx = tx_counts.get(old.code, 0)
        if len(candidates) == 1:
            new = candidates[0]
            reverse, _rmode = _find_twins(new, abolished)
            reverse = [o for o in reverse if o.code != new.code]
            if len(reverse) > 1:
                ctype = "merge"
                rationale = (
                    f"존재 1코드에 폐지 후보 {len(reverse)}개 (mode={mode}) → N:1 통합 가능성"
                )
            else:
                ctype = "code_reissue"
                rationale = _reissue_rationale(old, new, mode)
            add(
                Classified(
                    change_type=ctype,
                    historical_code=old.code,
                    historical_name=old.name,
                    historical_status=old.status,
                    canonical_code=new.code,
                    canonical_name=new.name,
                    canonical_candidates=cand_str,
                    rationale=rationale,
                    in_region_codes=True,
                    region_codes_active=bool(db.get("is_active")),
                    region_codes_eup_name=str(db.get("eupmyeondong_name") or ""),
                    tx_count_historical=h_tx,
                    tx_count_canonical=tx_counts.get(new.code, 0),
                    stats_v2_historical=stats_counts.get(old.code, 0),
                    stats_v2_canonical=stats_counts.get(new.code, 0),
                )
            )
        elif len(candidates) > 1:
            add(
                Classified(
                    change_type="split",
                    historical_code=old.code,
                    historical_name=old.name,
                    historical_status=old.status,
                    canonical_code="",
                    canonical_name="",
                    canonical_candidates=cand_str,
                    rationale=(
                        f"폐지 1코드에 존재 후보 {len(candidates)}개 (mode={mode}) "
                        f"→ 1:N 분할 가능. 자동 매핑 금지"
                    ),
                    in_region_codes=True,
                    region_codes_active=bool(db.get("is_active")),
                    region_codes_eup_name=str(db.get("eupmyeondong_name") or ""),
                    tx_count_historical=h_tx,
                    tx_count_canonical=0,
                    stats_v2_historical=stats_counts.get(old.code, 0),
                    stats_v2_canonical=0,
                )
            )
        else:
            add(
                Classified(
                    change_type="unresolved",
                    historical_code=old.code,
                    historical_name=old.name,
                    historical_status=old.status,
                    canonical_code="",
                    canonical_name="",
                    canonical_candidates="",
                    rationale=(
                        "마스터 폐지·DB 활성이나 동일 리(+읍면동) 존재 코드 없음. "
                        "흡수·개명·관할 이전 등 수동 검토 필요"
                    ),
                    in_region_codes=True,
                    region_codes_active=bool(db.get("is_active")),
                    region_codes_eup_name=str(db.get("eupmyeondong_name") or ""),
                    tx_count_historical=h_tx,
                    tx_count_canonical=0,
                    stats_v2_historical=stats_counts.get(old.code, 0),
                    stats_v2_canonical=0,
                )
            )

    # --- Missing 존재 without stale twin already covered ---
    covered_new = {c.canonical_code for c in results if c.canonical_code}
    covered_old = {c.historical_code for c in results}

    for new in missing_exist:
        if new.code in covered_new:
            continue
        candidates, mode = _find_twins(new, abolished)
        cand_str = "; ".join(f"{o.code}|{o.name}" for o in candidates)

        if len(candidates) == 1:
            old = candidates[0]
            if old.code in covered_old:
                continue
            ctype = "code_reissue"
            rationale = _reissue_rationale(old, new, mode)
            db = db_info.get(old.code, {})
            add(
                Classified(
                    change_type=ctype,
                    historical_code=old.code,
                    historical_name=old.name,
                    historical_status=old.status,
                    canonical_code=new.code,
                    canonical_name=new.name,
                    canonical_candidates=cand_str,
                    rationale=rationale,
                    in_region_codes=old.code in db_info,
                    region_codes_active=(
                        bool(db.get("is_active")) if old.code in db_info else None
                    ),
                    region_codes_eup_name=str(db.get("eupmyeondong_name") or ""),
                    tx_count_historical=tx_counts.get(old.code, 0),
                    tx_count_canonical=tx_counts.get(new.code, 0),
                    stats_v2_historical=stats_counts.get(old.code, 0),
                    stats_v2_canonical=stats_counts.get(new.code, 0),
                )
            )
        elif len(candidates) > 1:
            add(
                Classified(
                    change_type="merge",
                    historical_code=";".join(o.code for o in candidates),
                    historical_name="; ".join(o.name for o in candidates),
                    historical_status="폐지",
                    canonical_code=new.code,
                    canonical_name=new.name,
                    canonical_candidates=cand_str,
                    rationale=(
                        f"존재 1코드에 폐지 후보 {len(candidates)}개 (mode={mode}) → N:1 통합. "
                        f"건별 확인 후 매핑"
                    ),
                    in_region_codes=False,
                    region_codes_active=None,
                    region_codes_eup_name="",
                    tx_count_historical=sum(tx_counts.get(o.code, 0) for o in candidates),
                    tx_count_canonical=tx_counts.get(new.code, 0),
                    stats_v2_historical=sum(
                        stats_counts.get(o.code, 0) for o in candidates
                    ),
                    stats_v2_canonical=stats_counts.get(new.code, 0),
                )
            )
        else:
            add(
                Classified(
                    change_type="unresolved",
                    historical_code="",
                    historical_name="",
                    historical_status="",
                    canonical_code=new.code,
                    canonical_name=new.name,
                    canonical_candidates="",
                    rationale=(
                        "마스터 존재·region_codes 미적재, 동일 리(+읍면동) 폐지 쌍 없음. "
                        "신설·관할 이전·마스터만의 코드일 수 있음"
                    ),
                    in_region_codes=False,
                    region_codes_active=None,
                    region_codes_eup_name="",
                    tx_count_historical=0,
                    tx_count_canonical=tx_counts.get(new.code, 0),
                    stats_v2_historical=0,
                    stats_v2_canonical=stats_counts.get(new.code, 0),
                )
            )

    # Exemplar: 대소 수태리
    for c in results:
        if c.historical_code == "4377034026" or c.canonical_code == "4377025626":
            c.exemplar = "대소면→대소읍 수태리 (UI GIS/통계 충돌 사례)"
            if c.change_type == "code_reissue":
                c.notes = (
                    "GIS li_cd=4377025626(신), 통계/원장 매핑=4377034026(폐지·DB활성·이름 대소읍). "
                    "D-028 code_reissue 전형."
                )

    # Detect rename among DB active codes where master 존재 same code but eup name
    # in DB differs only by 면/읍 while code equals master exist — not in 192 set.
    # Optional pass: codes in DB where master status 존재 and DB eup != master eup
    for code, db in db_info.items():
        m = master.get(code)
        if not m or m.status != "존재":
            continue
        if not db.get("is_active"):
            continue
        db_eup = str(db.get("eupmyeondong_name") or "")
        if db_eup and m.eup and db_eup != m.eup and _eup_myeon_pair(db_eup, m.eup):
            # name drift on same code — true rename (code stable)
            key = (code, code)
            if key in seen_pair:
                continue
            add(
                Classified(
                    change_type="rename",
                    historical_code=code,
                    historical_name=f"(DB) … {db_eup} …",
                    historical_status="존재",
                    canonical_code=code,
                    canonical_name=m.name,
                    canonical_candidates=f"{code}|{m.name}",
                    rationale=(
                        f"동일 코드 유지, DB 읍면동명 '{db_eup}' ≠ 마스터 '{m.eup}' "
                        f"(면↔읍 표기만). grain 불변"
                    ),
                    in_region_codes=True,
                    region_codes_active=True,
                    region_codes_eup_name=db_eup,
                    tx_count_historical=tx_counts.get(code, 0),
                    tx_count_canonical=tx_counts.get(code, 0),
                    stats_v2_historical=stats_counts.get(code, 0),
                    stats_v2_canonical=stats_counts.get(code, 0),
                    notes="192 누락 집합 외 보조 스캔",
                )
            )

    return results


def _load_db():
    from app.config import settings

    eng = create_engine(settings.database_url)
    db_info: dict[str, dict] = {}
    tx_counts: dict[str, int] = {}
    stats_counts: dict[str, int] = {}
    with eng.connect() as conn:
        for row in conn.execute(
            text(
                """
                SELECT beopjungri_code, is_active, eupmyeondong_name, beopjungri_name,
                       sigungu_name
                FROM region_codes
                """
            )
        ).mappings():
            db_info[str(row["beopjungri_code"]).strip()] = dict(row)

        for row in conn.execute(
            text(
                """
                SELECT beopjungri_code, COUNT(*)::int AS n
                FROM land_transactions
                GROUP BY 1
                """
            )
        ):
            tx_counts[str(row[0]).strip()] = int(row[1])

        for row in conn.execute(
            text(
                """
                SELECT beopjungri_code, COUNT(*)::int AS n
                FROM land_basic_stats_v2
                GROUP BY 1
                """
            )
        ):
            stats_counts[str(row[0]).strip()] = int(row[1])
    return db_info, tx_counts, stats_counts


def _write_reports(
    results: list[Classified],
    *,
    missing_n: int,
    stale_n: int,
    stale_codes: set[str],
    missing_codes: set[str],
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    by_type: dict[str, list[Classified]] = {t: [] for t in TYPES}
    for r in results:
        by_type.setdefault(r.change_type, []).append(r)

    # 192 무결성 집합 관점: historical=stale 또는 canonical=missing
    integrity_rows = [
        r
        for r in results
        if (r.historical_code in stale_codes)
        or (r.canonical_code in missing_codes)
        or (
            ";" in (r.historical_code or "")
            and any(c in stale_codes for c in r.historical_code.split(";"))
        )
    ]
    integrity_by_type = Counter(r.change_type for r in integrity_rows)

    auto = [r for r in results if r.change_type == "code_reissue" and r.canonical_code]
    auto_with_tx = [r for r in auto if r.tx_count_historical > 0]
    real_problem = [
        r
        for r in results
        if r.change_type in ("code_reissue", "merge", "split", "unresolved")
        and (r.tx_count_historical > 0 or r.stats_v2_historical > 0)
    ]
    auto_real = [r for r in auto if r.tx_count_historical > 0 or r.stats_v2_historical > 0]

    # clusters for code_reissue
    def cluster_label(r: Classified) -> str:
        name = r.canonical_name or r.historical_name or ""
        if "대소" in name:
            return "음성 대소면→대소읍"
        if "양지" in name:
            return "용인 양지면→양지읍"
        if "화성" in name:
            return "화성시 분구(구 신설)"
        return "기타"

    cluster_c = Counter(cluster_label(r) for r in auto)

    exemplars = [r for r in results if r.exemplar]

    lines: list[str] = []
    lines.append("# Phase 1a — 지역코드 변경 분류 리포트")
    lines.append("")
    lines.append(f"- **일자:** {date.today().isoformat()}")
    lines.append("- **범위:** read-only (DB 변경·seed·remap 없음)")
    lines.append("- **마스터:** `data/region_codes/법정동코드 전체자료(260701).txt`")
    lines.append("- **원칙:** D-028 / [`REGION_CODE_LAYERS.md`](../REGION_CODE_LAYERS.md)")
    lines.append(
        "- **상세 CSV:** [`REGION_CODE_PHASE1A_CLASSIFICATION.csv`](./REGION_CODE_PHASE1A_CLASSIFICATION.csv)"
    )
    lines.append(
        "- **재실행:** `backend/.venv/Scripts/python.exe ../pipeline/classify_region_code_changes_1a.py`"
    )
    lines.append("")
    lines.append("## 1. 요약")
    lines.append("")
    lines.append("| 지표 | 건수 |")
    lines.append("|------|------|")
    lines.append(f"| 마스터 존재 leaf · region_codes 누락 | {missing_n} |")
    lines.append(f"| 마스터 폐지 · region_codes 활성 잔류 | {stale_n} |")
    lines.append(f"| 분류 행 합계 (쌍·보조 포함) | {len(results)} |")
    for t in TYPES:
        lines.append(f"| → `{t}` | {len(by_type.get(t, []))} |")
    lines.append("")
    lines.append("### 1.1 무결성 갭(192↔192)에 속한 분류")
    lines.append("")
    lines.append("| 유형 | 건수 |")
    lines.append("|------|------|")
    for t in TYPES:
        lines.append(f"| `{t}` | {integrity_by_type.get(t, 0)} |")
    lines.append("")
    lines.append("### 1.2 자동 매핑·실제 문제")
    lines.append("")
    lines.append("| 지표 | 건수 |")
    lines.append("|------|------|")
    lines.append(
        f"| **자동 canonical 매핑 후보** (`code_reissue` + canonical 확정) | **{len(auto)}** |"
    )
    lines.append(f"| 그중 historical 거래 > 0 | {len(auto_with_tx)} |")
    lines.append(
        f"| **실제 문제** (hist 거래 또는 stats_v2 > 0) | **{len(real_problem)}** |"
    )
    lines.append(
        f"| 실제 문제 중 자동 매핑 가능 (`code_reissue`) | **{len(auto_real)}** |"
    )
    lines.append(
        f"| 실제 문제 중 수동 (`merge`/`split`/`unresolved`) | {len(real_problem) - len(auto_real)} |"
    )
    lines.append("")
    lines.append("`code_reissue` 클러스터:")
    lines.append("")
    for k, v in cluster_c.most_common():
        lines.append(f"- **{k}:** {v}건")
    lines.append("")
    lines.append(
        "> `is_active` 일괄 복구는 하지 않음. "
        "Phase 1b 자동 대상은 `code_reissue`이며, `split`/`unresolved`/`merge`는 수동."
    )
    lines.append("")
    lines.append("## 2. 대소면 → 대소읍 수태리 (exemplar)")
    lines.append("")
    if exemplars:
        for e in exemplars:
            lines.append(f"- **유형:** `{e.change_type}`")
            lines.append(f"- **historical:** `{e.historical_code}` — {e.historical_name}")
            lines.append(f"- **canonical:** `{e.canonical_code}` — {e.canonical_name}")
            lines.append(f"- **근거:** {e.rationale}")
            if e.notes:
                lines.append(f"- **메모:** {e.notes}")
            lines.append(
                f"- **거래/통계:** hist tx={e.tx_count_historical}, "
                f"hist stats_v2={e.stats_v2_historical}, "
                f"canon tx={e.tx_count_canonical}, canon stats_v2={e.stats_v2_canonical}"
            )
            lines.append(
                f"- **DB:** active={e.region_codes_active}, "
                f"eupmyeondong_name(DB)='{e.region_codes_eup_name}'"
            )
            lines.append("")
    else:
        lines.append("_수태리 쌍이 결과에 없음 — 스크립트/DB 확인 필요._")
        lines.append("")

    lines.append("## 3. 유형별 정의")
    lines.append("")
    lines.append("| 유형 | 의미 | Phase 1b |")
    lines.append("|------|------|----------|")
    lines.append("| `code_reissue` | 구코드→신코드 1:1 (면→읍·분구 등) | 자동 매핑 OK |")
    lines.append("| `rename` | 코드 동일·명칭만 변경 | grain 불변, 이름 정합 |")
    lines.append("| `merge` | N:1 통합 | 건별 확인 후 매핑 |")
    lines.append("| `split` | 1:N 분할 | **자동 금지**, 별도 큐 |")
    lines.append("| `unresolved` | 자료만으로 확정 불가 | 수동 검토 |")
    lines.append("")

    def section(title: str, rows: list[Classified], limit: int = 40) -> None:
        lines.append(f"## {title}")
        lines.append("")
        if not rows:
            lines.append("_(없음)_")
            lines.append("")
            return
        lines.append(
            "| historical | historical name | canonical | canonical name | tx_h | stats_h | 근거 |"
        )
        lines.append(
            "|------------|-----------------|-----------|----------------|------|---------|------|"
        )
        for r in sorted(
            rows,
            key=lambda x: (-x.tx_count_historical, x.historical_code or x.canonical_code),
        )[:limit]:
            lines.append(
                f"| `{r.historical_code}` | {r.historical_name} | "
                f"`{r.canonical_code}` | {r.canonical_name} | "
                f"{r.tx_count_historical} | {r.stats_v2_historical} | {r.rationale} |"
            )
        if len(rows) > limit:
            lines.append("")
            lines.append(f"_… 외 {len(rows) - limit}건은 CSV 참고._")
        lines.append("")

    section("4. code_reissue (자동 매핑 후보)", by_type.get("code_reissue", []), limit=50)
    section("5. rename", by_type.get("rename", []))
    section("6. merge", by_type.get("merge", []))
    section("7. split (자동 금지)", by_type.get("split", []))
    section("8. unresolved (수동 검토)", by_type.get("unresolved", []), limit=40)

    lines.append("## 9. 실제 문제 후보 (historical에 거래 또는 stats_v2)")
    lines.append("")
    section("9.1 목록", real_problem, limit=60)

    lines.append("## 10. 다음 단계")
    lines.append("")
    lines.append("1. 본 리포트 검토 (특히 `merge` / `split` / `unresolved`)")
    lines.append("2. Phase 1b: 확정 `code_reissue`만 `region_code_history` 적재")
    lines.append("3. seed + abolished inactive → stats 재빌드 (canonical grain)")
    lines.append("4. GIS → canonical resolve")
    lines.append("")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    fieldnames = [
        "change_type",
        "historical_code",
        "historical_name",
        "historical_status",
        "canonical_code",
        "canonical_name",
        "canonical_candidates",
        "rationale",
        "in_region_codes",
        "region_codes_active",
        "region_codes_eup_name",
        "tx_count_historical",
        "tx_count_canonical",
        "stats_v2_historical",
        "stats_v2_canonical",
        "exemplar",
        "notes",
    ]
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in sorted(
            results,
            key=lambda x: (x.change_type, x.historical_code or "", x.canonical_code or ""),
        ):
            w.writerow({k: getattr(r, k) for k in fieldnames})


def main() -> int:
    if not MASTER.is_file():
        print(f"master missing: {MASTER}", file=sys.stderr)
        return 1
    master = _parse_master(MASTER)
    db_info, tx_counts, stats_counts = _load_db()

    exist = _leaf_rows(master, status="존재")
    abolished = _leaf_rows(master, status="폐지")
    missing_codes = {r.code for r in exist if r.code not in db_info}
    stale_codes = {
        r.code
        for r in abolished
        if r.code in db_info and db_info[r.code].get("is_active")
    }
    missing_n = len(missing_codes)
    stale_n = len(stale_codes)

    results = classify(master, db_info, tx_counts, stats_counts)
    _write_reports(
        results,
        missing_n=missing_n,
        stale_n=stale_n,
        stale_codes=stale_codes,
        missing_codes=missing_codes,
    )

    # console summary (ascii-safe counts)
    from collections import Counter

    c = Counter(r.change_type for r in results)
    print(f"missing_exist={missing_n} stale_active={stale_n} classified={len(results)}")
    print("by_type:", dict(c))
    auto = sum(1 for r in results if r.change_type == "code_reissue" and r.canonical_code)
    real = sum(
        1
        for r in results
        if r.change_type in ("code_reissue", "merge", "split", "unresolved")
        and (r.tx_count_historical > 0 or r.stats_v2_historical > 0)
    )
    print(f"auto_code_reissue={auto} real_problem={real}")
    print(f"wrote {OUT_MD}")
    print(f"wrote {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
