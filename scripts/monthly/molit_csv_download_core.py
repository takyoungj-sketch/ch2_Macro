"""
국토부 실거래 CSV Selenium 수집 코어 (월간·historical 스크립트 공용).

치명적 이슈: 요청 간격이 짧거나 이전 다운로드 완료 전 rename 하면
  시도/연도가 뒤바뀐 CSV 가 저장될 수 있음.
→ 폴더 quiescent 대기 + 파일 크기 안정 + CSV 메타데이터 검증 필수.

docs/MOLIT_CSV_COLLECTOR_WARNINGS.md 참고.
"""

from __future__ import annotations

import json
import shutil
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from molit_csv_validate import parse_metadata, read_csv_text, validate_csv_file

MOLIT_XLS_URL = "https://rt.molit.go.kr/pt/xls/xls.do?mobileAt="

DEFAULT_SIDO_LIST = [
    "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시",
    "대전광역시", "울산광역시", "세종특별자치시", "경기도", "강원특별자치도",
    "충청북도", "충청남도", "전북특별자치도", "전라남도", "경상북도", "경상남도",
    "제주특별자치도",
]

POST_CLICK_WAIT_SEC = 4
INTER_REQUEST_SLEEP_SEC = 8
SIDO_SELECT_WAIT_SEC = 3
DOWNLOAD_TIMEOUT_SEC = 360
FILE_STABLE_SEC = 3
MIN_CSV_BYTES = 500
FAILURE_LOG_NAME = ".download_failures.jsonl"
CHROME_DOWNLOAD_SUBDIR = ".downloads"
FAILED_SUBDIR = "failed"
FILE_MOVE_RETRIES = 12
FILE_MOVE_RETRY_DELAY_SEC = 1.0
STALL_ABORT_SEC = 180

LogFn = Callable[[str], None]


@dataclass
class CollectSpec:
    tab_id: int
    type_label_ko: str
    deal_type: str
    output_dir: Path
    start_year: int
    end_year: int
    regions: list[str] = field(default_factory=lambda: list(DEFAULT_SIDO_LIST))
    max_new_downloads: int = 100
    headless: bool = False
    revalidate_existing: bool = True

    def csv_filename(self, region: str, year: int) -> str:
        return f"{region}_{self.type_label_ko}_{self.deal_type}_{year}.csv"


@dataclass
class CollectResult:
    done: int = 0
    skipped: int = 0
    failed: int = 0
    revalidated_bad: int = 0
    stopped_reason: str | None = None
    failures: list[dict] = field(default_factory=list)


def wait_folder_quiescent(folder: Path, *, stable_sec: float = 2.0, timeout: int = 120) -> bool:
    deadline = time.time() + timeout
    last_sig: tuple[tuple[str, int], ...] | None = None
    stable_since: float | None = None
    while time.time() < deadline:
        try:
            files = list(folder.iterdir())
        except OSError:
            time.sleep(0.5)
            continue
        if any(p.name.endswith(".crdownload") for p in files if p.is_file()):
            last_sig = None
            stable_since = None
            time.sleep(0.5)
            continue
        sig = tuple(sorted((p.name, p.stat().st_size) for p in files if p.is_file()))
        if sig == last_sig:
            if stable_since and time.time() - stable_since >= stable_sec:
                return True
        else:
            last_sig = sig
            stable_since = time.time()
        time.sleep(0.5)
    return False


def snapshot_files(folder: Path) -> set[Path]:
    if not folder.is_dir():
        return set()
    return {
        p.resolve()
        for p in folder.iterdir()
        if p.is_file() and not p.name.endswith(".crdownload")
    }


def wait_for_new_csv(
    folder: Path, before: set[Path], click_ts: float, *, timeout: int = DOWNLOAD_TIMEOUT_SEC
) -> Path | None:
    deadline = time.time() + timeout
    candidate: Path | None = None
    last_size = -1
    stable_since: float | None = None
    last_progress = time.time()
    while time.time() < deadline:
        if any(p.name.endswith(".crdownload") for p in folder.iterdir() if p.is_file()):
            last_progress = time.time()
            candidate = None
            last_size = -1
            stable_since = None
            time.sleep(0.5)
            continue
        after = snapshot_files(folder)
        new_files = {
            p for p in (after - before)
            if p.suffix.lower() in {".csv", ".xlsx"} and p.stat().st_mtime >= click_ts - 2
        }
        if not new_files:
            if time.time() - last_progress >= STALL_ABORT_SEC:
                return None
            time.sleep(0.5)
            continue
        last_progress = time.time()
        pick = max(new_files, key=lambda p: p.stat().st_mtime)
        size = pick.stat().st_size
        if size < MIN_CSV_BYTES:
            time.sleep(0.5)
            continue
        if pick == candidate and size == last_size:
            if stable_since and time.time() - stable_since >= FILE_STABLE_SEC:
                return pick
        else:
            candidate = pick
            last_size = size
            stable_since = time.time()
        time.sleep(0.5)
    return None


def dismiss_alerts(driver) -> str | None:
    from selenium.common.exceptions import NoAlertPresentException
    try:
        alert = driver.switch_to.alert
        text = alert.text
        alert.accept()
        return text
    except NoAlertPresentException:
        return None


def handle_processing_popup(driver) -> None:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    try:
        popup = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".layerPop"))
        )
        if "처리중입니다" in popup.text:
            popup.find_element(By.XPATH, ".//button[contains(text(),'확인')]").click()
    except Exception:
        pass


def _append_failure(output_dir: Path, record: dict) -> None:
    with (output_dir / FAILURE_LOG_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def chrome_download_dir(output_dir: Path) -> Path:
    d = output_dir / CHROME_DOWNLOAD_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def quarantine_csv(
    src: Path,
    output_dir: Path,
    *,
    expected_region: str,
    year: int,
    spec: CollectSpec,
    reason: str,
) -> Path:
    """검증 실패 파일을 failed/ 로 이동 (삭제하지 않음)."""
    failed_dir = output_dir / FAILED_SUBDIR
    failed_dir.mkdir(parents=True, exist_ok=True)
    actual = "unknown"
    try:
        meta = parse_metadata(read_csv_text(src))
        actual = meta.get("시도", "") or actual
    except OSError:
        pass
    if "실제=" in reason:
        part = reason.split("실제=", 1)[1]
        actual = part.split(")")[0].split(",")[0].strip() or actual
    safe_actual = actual.replace("/", "_").replace("\\", "_")
    base = (
        f"{expected_region}_{spec.type_label_ko}_{spec.deal_type}"
        f"_{year}_실제_{safe_actual}.csv"
    )
    dest = failed_dir / base
    if dest.exists():
        dest = failed_dir / f"{dest.stem}_{int(time.time())}.csv"
    move_csv_to_final(src, dest)
    return dest


def move_csv_to_final(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        try:
            dest.unlink()
        except OSError:
            pass
    last_err: OSError | None = None
    for _ in range(FILE_MOVE_RETRIES):
        try:
            src.replace(dest)
            return
        except OSError as exc:
            last_err = exc
            time.sleep(FILE_MOVE_RETRY_DELAY_SEC)
    for _ in range(FILE_MOVE_RETRIES):
        try:
            shutil.copy2(src, dest)
            src.unlink(missing_ok=True)
            return
        except OSError as exc:
            last_err = exc
            time.sleep(FILE_MOVE_RETRY_DELAY_SEC)
    assert last_err is not None
    raise last_err


def select_sido_region(driver, wait, region: str) -> tuple[bool, str]:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import Select

    sido_el = wait.until(EC.presence_of_element_located((By.ID, "srhSidoCd")))
    select = Select(sido_el)
    select.select_by_visible_text(region.strip())
    time.sleep(SIDO_SELECT_WAIT_SEC)
    selected = select.first_selected_option.text.strip()
    if selected != region.strip():
        return False, f"시도 선택 미반영: 기대={region}, UI={selected}"
    return True, ""


def run_molit_csv_collect(spec: CollectSpec, *, log: LogFn | None = print) -> CollectResult:
    from selenium import webdriver
    from selenium.common.exceptions import UnexpectedAlertPresentException
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    years = list(range(spec.start_year, spec.end_year + 1))
    download_dir = spec.output_dir.expanduser().resolve()
    download_dir.mkdir(parents=True, exist_ok=True)
    chrome_dir = chrome_download_dir(download_dir)
    year_ranges = [(y, f"{y}-01-01", f"{y}-12-31") for y in years]

    options = Options()
    if spec.headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(chrome_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 90)
    result = CollectResult()
    max_new = max(0, spec.max_new_downloads)

    def _log(msg: str) -> None:
        if log:
            log(msg)

    try:
        driver.get(MOLIT_XLS_URL)
        for region in spec.regions:
            for year, from_date, to_date in year_ranges:
                if max_new and result.done >= max_new:
                    result.stopped_reason = f"max_new_downloads={max_new}"
                    _log(f"신규 {max_new}건 도달 → 중단")
                    break

                file_path = download_dir / spec.csv_filename(region, year)
                if file_path.exists() and file_path.stat().st_size > 0:
                    if spec.revalidate_existing:
                        ok, reason = validate_csv_file(
                            file_path, region=region, year=year,
                            type_label_ko=spec.type_label_ko, deal_type=spec.deal_type,
                        )
                        if ok:
                            _log(f"{region} {year} 검증 OK → 스킵")
                            result.skipped += 1
                            continue
                        _log(f"[FAIL] {region} {year} 기존 파일 오염 → 재수집 ({reason})")
                        moved = quarantine_csv(
                            file_path, download_dir,
                            expected_region=region, year=year, spec=spec, reason=reason,
                        )
                        _log(f"{region} {year} 오염 파일 이동 → {moved.name}")
                        result.revalidated_bad += 1
                    else:
                        _log(f"{region} {year} 이미 존재 → 스킵")
                        result.skipped += 1
                        continue

                try:
                    if not wait_folder_quiescent(chrome_dir):
                        reason = "이전 다운로드 미완료"
                        _log(f"[FAIL] {region} {year} {reason}")
                        _append_failure(download_dir, {"region": region, "year": year, "reason": reason})
                        result.failures.append({"region": region, "year": year, "reason": reason})
                        result.failed += 1
                        continue

                    dismiss_alerts(driver)
                    tab = wait.until(EC.element_to_be_clickable((By.ID, f"xlsTab{spec.tab_id}")))
                    driver.execute_script("arguments[0].click();", tab)
                    driver.find_element(By.ID, "srhFromDt").clear()
                    driver.find_element(By.ID, "srhFromDt").send_keys(from_date)
                    driver.find_element(By.ID, "srhToDt").clear()
                    driver.find_element(By.ID, "srhToDt").send_keys(to_date)

                    ok_sido, sido_reason = select_sido_region(driver, wait, region)
                    if not ok_sido:
                        _log(f"[FAIL] {region} {year} {sido_reason}")
                        result.failed += 1
                        continue

                    before = snapshot_files(chrome_dir)
                    btn = wait.until(
                        EC.presence_of_element_located((By.XPATH, "//button[contains(text(),'CSV')]"))
                    )
                    click_ts = time.time()
                    driver.execute_script("arguments[0].click();", btn)
                    _log(f"{region} {year} 다운로드 시작…")
                    time.sleep(POST_CLICK_WAIT_SEC)
                    handle_processing_popup(driver)
                    alert_text = dismiss_alerts(driver)
                    if alert_text and "실패" in alert_text:
                        _log(f"[FAIL] {region} {year} {alert_text}")
                        result.failed += 1
                        time.sleep(INTER_REQUEST_SLEEP_SEC)
                        continue

                    temp_path = wait_for_new_csv(chrome_dir, before, click_ts)
                    if temp_path is None:
                        reason = "타임아웃/신규파일 없음"
                        _log(f"[FAIL] {region} {year} {reason}")
                        result.failed += 1
                        time.sleep(INTER_REQUEST_SLEEP_SEC)
                        continue

                    ok, vreason = validate_csv_file(
                        temp_path, region=region, year=year,
                        type_label_ko=spec.type_label_ko, deal_type=spec.deal_type,
                    )
                    if not ok:
                        moved = quarantine_csv(
                            temp_path, download_dir,
                            expected_region=region, year=year, spec=spec, reason=vreason,
                        )
                        _log(f"[FAIL] {region} {year} 검증 실패 — {FAILED_SUBDIR}/ 보관 ({vreason}) → {moved.name}")
                        _append_failure(download_dir, {"region": region, "year": year, "reason": vreason})
                        result.failures.append({"region": region, "year": year, "reason": vreason})
                        result.failed += 1
                        time.sleep(INTER_REQUEST_SLEEP_SEC)
                        continue

                    move_csv_to_final(temp_path, file_path)
                    _log(f"{region} {year} 저장 → {file_path.name}")
                    result.done += 1
                except UnexpectedAlertPresentException:
                    alert_text = dismiss_alerts(driver) or "알림"
                    _log(f"[FAIL] {region} {year} {alert_text}")
                    result.failed += 1
                except Exception:
                    _log(f"[FAIL] {region} {year}\n{traceback.format_exc()}")
                    result.failed += 1

                time.sleep(INTER_REQUEST_SLEEP_SEC)
            if result.stopped_reason:
                break
    finally:
        driver.quit()
        _log(
            f"종료: 완료 {result.done}, 스킵 {result.skipped}, "
            f"실패 {result.failed}, 오염재수집 {result.revalidated_bad}"
        )
    return result
