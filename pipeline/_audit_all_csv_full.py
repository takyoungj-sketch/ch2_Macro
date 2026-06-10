# -*- coding: utf-8 -*-
"""
Full audit: all historical land CSV files (2010~2020 × 17 sidos).

Checks per file:
  1) metadata 시도 vs filename region
  2) metadata 실거래구분 contains 토지 (not 아파트/오피스텔/…)
  3) metadata 계약일자 year span vs filename year
  4) header columns: land (지목·용도지역) vs apt (단지명·전용면적·층)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "raw" / "토지_2010_2020"

REGION_ALIASES: dict[str, tuple[str, ...]] = {
    "서울특별시": ("서울특별시", "서울"),
    "부산광역시": ("부산광역시", "부산"),
    "대구광역시": ("대구광역시", "대구"),
    "인천광역시": ("인천광역시", "인천"),
    "광주광역시": ("광주광역시", "광주"),
    "대전광역시": ("대전광역시", "대전"),
    "울산광역시": ("울산광역시", "울산"),
    "세종특별자치시": ("세종특별자치시", "세종"),
    "경기도": ("경기도", "경기"),
    "강원특별자치도": ("강원특별자치도", "강원도", "강원"),
    "충청북도": ("충청북도", "충북"),
    "충청남도": ("충청남도", "충남"),
    "전북특별자치도": ("전북특별자치도", "전라북도", "전북"),
    "전라남도": ("전라남도", "전남"),
    "경상북도": ("경상북도", "경북"),
    "경상남도": ("경상남도", "경남"),
    "제주특별자치도": ("제주특별자치도", "제주"),
}


@dataclass
class FileReport:
    path: Path
    expected_region: str
    file_year: int
    meta_sido: str | None = None
    meta_deal_type: str | None = None
    meta_date_range: str | None = None
    issues: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def decode(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("cp949", "utf-8-sig", "utf-8", "euc-kr"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp949", errors="replace")


def parse_meta(text: str) -> tuple[str | None, str | None, str | None, str | None]:
    sido = deal = dates = None
    header = None
    for ln in text.splitlines()[:30]:
        if "시도 :" in ln:
            m = re.search(r"시도\s*:\s*([^\"]+)", ln)
            if m:
                sido = m.group(1).strip().strip('"')
        if "실거래구분" in ln:
            m = re.search(r"실거래구분\s*:\s*([^\"]+)", ln)
            if m:
                deal = m.group(1).strip().strip('"')
        if "계약일자" in ln:
            m = re.search(r"계약일자\s*:\s*([^\"]+)", ln)
            if m:
                dates = m.group(1).strip().strip('"')
        if header is None and "시군구" in ln and ("NO" in ln or ln.startswith('"NO"')):
            header = ln
    return sido, deal, dates, header


def sido_ok(expected: str, actual: str | None) -> bool:
    if not actual:
        return False
    aliases = REGION_ALIASES.get(expected, (expected,))
    return any(a in actual or actual.startswith(a) for a in aliases)


def year_ok(file_year: int, date_range: str | None) -> bool:
    if not date_range:
        return False
    years = [int(y) for y in re.findall(r"(20\d{2})", date_range)]
    if not years:
        return False
    lo, hi = min(years), max(years)
    return lo <= file_year <= hi


def header_kind(header: str | None) -> str:
    if not header:
        return "unknown"
    land = sum(1 for k in ("지목", "용도지역", "계약면적") if k in header)
    apt = sum(1 for k in ("단지명", "전용면적", "건축년도", "층") if k in header)
    if land >= 2 and apt == 0:
        return "land"
    if apt >= 2 and land == 0:
        return "apt"
    if land >= 1 and apt >= 1:
        return "mixed"
    return "unknown"


def audit_file(path: Path) -> FileReport:
    m = re.match(r"^(.+?)_토지_매매_(\d{4})\.csv$", path.name)
    if not m:
        return FileReport(path, "?", 0, issues=["bad_filename"])
    expected, year = m.group(1), int(m.group(2))
    rep = FileReport(path, expected, year)
    text = decode(path)
    rep.meta_sido, rep.meta_deal_type, rep.meta_date_range, hdr = parse_meta(text)
    hk = header_kind(hdr)

    if not rep.meta_sido:
        rep.issues.append("no_meta_sido")
    elif not sido_ok(expected, rep.meta_sido):
        rep.issues.append(f"wrong_sido:meta={rep.meta_sido}")

    if not rep.meta_deal_type:
        rep.issues.append("no_meta_deal_type")
    elif "토지" not in rep.meta_deal_type:
        rep.issues.append(f"wrong_type:{rep.meta_deal_type}")

    if not rep.meta_date_range:
        rep.issues.append("no_meta_dates")
    elif not year_ok(year, rep.meta_date_range):
        rep.issues.append(f"wrong_year:meta={rep.meta_date_range}")

    if hk == "apt":
        rep.issues.append("apt_header")
    elif hk == "mixed":
        rep.issues.append("mixed_header")
    elif hk == "unknown":
        rep.issues.append("unknown_header")

    return rep


def main() -> None:
    files = sorted(RAW.glob("*_토지_매매_*.csv"))
    reports = [audit_file(p) for p in files]
    bad = [r for r in reports if not r.ok]
    ok_n = len(reports) - len(bad)

    print(f"검사 파일: {len(files)} (17시도 × 11년 = 187 예상)")
    print(f"정상: {ok_n}  /  문제: {len(bad)}")
    print()

    if bad:
        print("=== 문제 파일 전체 목록 ===")
        for r in sorted(bad, key=lambda x: (x.expected_region, x.file_year)):
            issue_str = "; ".join(r.issues)
            print(f"  {r.path.name}")
            print(f"    시도={r.meta_sido!r}  유형={r.meta_deal_type!r}  기간={r.meta_date_range!r}")
            print(f"    → {issue_str}")
        print()
        by_issue: dict[str, int] = {}
        for r in bad:
            for i in r.issues:
                key = i.split(":")[0]
                by_issue[key] = by_issue.get(key, 0) + 1
        print("=== 이슈 유형별 건수 ===")
        for k, n in sorted(by_issue.items(), key=lambda x: -x[1]):
            print(f"  {k}: {n}")

    missing = 17 * 11 - len(files)
    if missing:
        print(f"\n⚠ 누락 파일: {missing}개 (187 - {len(files)})")


if __name__ == "__main__":
    main()
