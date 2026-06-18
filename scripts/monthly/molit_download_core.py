"""MOLIT CSV 다운로드 대기·검증 (수집기·monthly 스크립트 공용)."""

from __future__ import annotations

import re
import time
from pathlib import Path

# 이전 다운로드가 끝나기 전 다음 요청 → 잘못된 파일명 붙임 (race). 여유 필요.
DEFAULT_POST_CLICK_DELAY_SEC = 3.0
DEFAULT_BETWEEN_JOBS_DELAY_SEC = 5.0
DEFAULT_DOWNLOAD_TIMEOUT_SEC = 300
DEFAULT_STABLE_CHECKS = 3
DEFAULT_STABLE_INTERVAL_SEC = 1.0


def wait_folder_idle(folder: Path, idle_sec: float = 2.0) -> None:
    """폴더에 .crdownload 가 없고 idle_sec 동안 유지될 때까지 대기."""
    if not folder.is_dir():
        return
    stable = 0
    while stable < idle_sec:
        try:
            busy = any(
                p.name.endswith(".crdownload")
                for p in folder.iterdir()
                if p.is_file()
            )
        except OSError:
            busy = True
        if busy:
            stable = 0
        else:
            stable += 1
        time.sleep(1)


def wait_for_file_stable(path: Path, *, checks: int = DEFAULT_STABLE_CHECKS) -> bool:
    """파일 크기가 checks 회 연속 동일할 때까지 대기."""
    if not path.is_file():
        return False
    last_size = -1
    stable = 0
    for _ in range(60):
        try:
            size = path.stat().st_size
        except OSError:
            return False
        if size > 0 and size == last_size:
            stable += 1
            if stable >= checks:
                return True
        else:
            stable = 0
            last_size = size
        time.sleep(DEFAULT_STABLE_INTERVAL_SEC)
    return False


def snapshot_files(folder: Path) -> set[Path]:
    if not folder.is_dir():
        return set()
    return {
        p.resolve()
        for p in folder.iterdir()
        if p.is_file() and not p.name.endswith(".crdownload")
    }


def wait_for_new_download(
    folder: Path,
    before: set[Path],
    *,
    click_ts: float,
    timeout: int = DEFAULT_DOWNLOAD_TIMEOUT_SEC,
) -> Path | None:
    """
    클릭 이후 생긴 CSV/XLSX 1개를 기다린다.
    - .crdownload 완료
    - mtime >= click_ts
    - 크기 안정
    """
    deadline = time.time() + timeout
    seen_crdownload = False

    while time.time() < deadline:
        try:
            entries = list(folder.iterdir())
        except OSError:
            time.sleep(1)
            continue

        crdownloads = [
            p for p in entries if p.is_file() and p.name.endswith(".crdownload")
        ]
        if crdownloads:
            seen_crdownload = True

        after = snapshot_files(folder)
        candidates = [
            p
            for p in (after - before)
            if p.suffix.lower() in {".csv", ".xlsx"} and p.stat().st_mtime >= click_ts - 0.5
        ]

        if candidates and not crdownloads:
            if not seen_crdownload and time.time() - click_ts < 5:
                # 서버가 느리면 .crdownload 없이 바로 파일이 생길 수 있음
                pass
            newest = max(candidates, key=lambda p: p.stat().st_mtime)
            if wait_for_file_stable(newest):
                return newest

        time.sleep(1)

    return None


def decode_csv_text(path: Path, *, max_bytes: int = 65536) -> str:
    raw = path.read_bytes()[:max_bytes]
    for enc in ("utf-8-sig", "cp949", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp949", errors="replace")


def parse_csv_metadata(path: Path) -> dict[str, str]:
    text = decode_csv_text(path)
    meta: dict[str, str] = {}
    for line in text.splitlines()[:20]:
        line = line.strip().strip('"')
        if line.startswith("계약일자"):
            meta["date_range"] = line.split(":", 1)[-1].strip()
        elif line.startswith("시도"):
            meta["region"] = line.split(":", 1)[-1].strip()
        elif line.startswith("실거래구분"):
            meta["deal_type"] = line.split(":", 1)[-1].strip()
    return meta


def validate_csv_metadata(
    path: Path,
    *,
    region: str,
    year: int,
    type_label_ko: str,
) -> tuple[bool, str]:
    """CSV 헤더 메타데이터가 요청(시도·연도·유형)과 일치하는지 확인."""
    if not path.is_file() or path.stat().st_size < 100:
        return False, "파일이 비어 있거나 너무 작음"

    meta = parse_csv_metadata(path)
    if not meta.get("region"):
        return False, "CSV 메타데이터(시도) 없음"
    if not meta.get("date_range"):
        return False, "CSV 메타데이터(계약일자) 없음"

    if meta["region"].strip() != region.strip():
        return False, f"시도 불일치: 파일={meta['region']!r} 기대={region!r}"

    m = re.search(r"(\d{4})-01-01\s*~\s*(\d{4})-12-31", meta["date_range"])
    if not m:
        return False, f"계약일자 형식 이상: {meta['date_range']!r}"
    start_y, end_y = int(m.group(1)), int(m.group(2))
    if start_y != year or end_y != year:
        return False, f"연도 불일치: 파일={start_y}~{end_y} 기대={year}"

    deal = meta.get("deal_type", "")
    if type_label_ko not in deal:
        return False, f"유형 불일치: 파일={deal!r} 기대={type_label_ko!r}"

    return True, "ok"


def find_new_download_legacy(folder: Path, before: set[Path], exclude: Path) -> Path | None:
    """구버전 호환 — 신규 검증 없이 diff 만 (deprecated)."""
    exclude_resolved = exclude.resolve()
    after = snapshot_files(folder)
    new_files = {
        p
        for p in (after - before)
        if p != exclude_resolved and p.suffix.lower() in {".csv", ".xlsx"}
    }
    if not new_files:
        return None
    return max(new_files, key=lambda p: p.stat().st_ctime)
