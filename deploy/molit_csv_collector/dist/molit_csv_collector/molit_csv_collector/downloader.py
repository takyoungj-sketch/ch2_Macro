"""국토부 실거래 CSV Selenium 다운로더 (검증·안정 대기 포함)."""

from __future__ import annotations

import json
import shutil
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .config import (
    DEFAULT_MAX_NEW_DOWNLOADS,
    DEFAULT_SIDO_LIST,
    MOLIT_XLS_URL,
    PropertyType,
    download_timeout_sec,
    processing_timeout_sec,
)
from .csv_validate import parse_metadata, read_csv_text, validate_csv_file
from .manifest import write_manifest

LogFn = Callable[[str], None]
LogLevelFn = Callable[[str, str], None]

POST_CLICK_WAIT_SEC = 4
INTER_REQUEST_SLEEP_SEC = 8
SIDO_SELECT_WAIT_SEC = 3
FILE_STABLE_SEC = 4
MIN_CSV_BYTES = 500
HEARTBEAT_SEC = 30
FILE_MOVE_RETRIES = 12
FILE_MOVE_RETRY_DELAY_SEC = 1.0
STALL_ABORT_SEC = 180
FOLDER_BUSY_TIMEOUT_SEC = 60

CHROME_DOWNLOAD_SUBDIR = ".downloads"
FAILED_SUBDIR = "failed"
FAILURE_LOG_NAME = ".download_failures.jsonl"


@dataclass
class DownloadJob:
    property_type: PropertyType
    start_year: int
    end_year: int
    output_dir: Path
    regions: list[str] = field(default_factory=lambda: list(DEFAULT_SIDO_LIST))
    max_new_downloads: int = DEFAULT_MAX_NEW_DOWNLOADS
    headless: bool = False
    revalidate_existing: bool = True


@dataclass
class DownloadResult:
    done: int = 0
    skipped: int = 0
    failed: int = 0
    revalidated_bad: int = 0
    stopped_reason: str | None = None
    manifest_path: Path | None = None
    failures: list[dict] = field(default_factory=list)


def _emit(log, log_level, level: str, message: str) -> None:
    if log_level:
        log_level(level, message)
    elif log:
        log(message)


def _log_info(log, log_level, msg: str) -> None:
    _emit(log, log_level, "info", msg)


def _log_fail(log, log_level, msg: str) -> None:
    _emit(log, log_level, "fail", msg)


def _file_meta(path: Path) -> tuple[int, float]:
    st = path.stat()
    return st.st_size, st.st_mtime


def snapshot_meta(folder: Path) -> dict[Path, tuple[int, float]]:
    if not folder.is_dir():
        return {}
    out: dict[Path, tuple[int, float]] = {}
    for p in folder.iterdir():
        if p.is_file() and not p.name.endswith(".crdownload"):
            try:
                out[p.resolve()] = _file_meta(p)
            except OSError:
                pass
    return out


def quarantine_csv(
    src: Path,
    output_dir: Path,
    *,
    expected_region: str,
    year: int,
    property_type: PropertyType,
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
        f"{expected_region}_{property_type.label_ko}_{property_type.deal_type}"
        f"_{year}_실제_{safe_actual}.csv"
    )
    dest = failed_dir / base
    if dest.exists():
        dest = failed_dir / f"{dest.stem}_{int(time.time())}.csv"
    move_csv_to_final(src, dest, label=f"quarantine {base}")
    return dest


def move_csv_to_final(
    src: Path,
    dest: Path,
    *,
    log=None,
    log_level=None,
    label: str = "",
) -> None:
    """Windows 파일 잠금(WinError 32) 대비 — rename 재시도 후 copy fallback."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        try:
            dest.unlink()
        except OSError:
            pass
    tag = label or dest.name
    last_err: OSError | None = None
    for attempt in range(1, FILE_MOVE_RETRIES + 1):
        try:
            src.replace(dest)
            return
        except OSError as exc:
            last_err = exc
            if attempt < FILE_MOVE_RETRIES:
                _log_info(
                    log,
                    log_level,
                    f"{tag} 저장 재시도 {attempt}/{FILE_MOVE_RETRIES} ({exc})",
                )
                time.sleep(FILE_MOVE_RETRY_DELAY_SEC)
    for attempt in range(1, FILE_MOVE_RETRIES + 1):
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
    """Select 드롭다운으로 시도 선택 + UI 반영 확인."""
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


def chrome_download_dir(output_dir: Path) -> Path:
    d = output_dir / CHROME_DOWNLOAD_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def cleanup_orphan_temp_csv(folder: Path, property_type: PropertyType) -> int:
    """국토부 기본 파일명 등 최종명 규격이 아닌 csv 잔여물 제거."""
    tag = f"_{property_type.label_ko}_{property_type.deal_type}_"
    removed = 0
    for p in folder.glob("*.csv"):
        if tag in p.name:
            continue
        try:
            p.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def wait_folder_quiescent(
    folder: Path,
    *,
    stable_sec: float = 2.0,
    timeout: int = 180,
    log=None,
    log_level=None,
    label: str = "",
) -> bool:
    deadline = time.time() + timeout
    last_sig: tuple[tuple[str, int], ...] | None = None
    stable_since: float | None = None
    last_heartbeat = time.time()

    while time.time() < deadline:
        try:
            files = list(folder.iterdir())
        except OSError:
            time.sleep(0.5)
            continue
        if any(p.name.endswith(".crdownload") for p in files if p.is_file()):
            if time.time() - last_heartbeat >= HEARTBEAT_SEC:
                cr = [p.name for p in files if p.name.endswith(".crdownload")]
                _log_info(log, log_level, f"{label} 이전 다운로드 진행 중… ({', '.join(cr)})")
                last_heartbeat = time.time()
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


def _iter_download_candidates(
    folder: Path,
    before_meta: dict[Path, tuple[int, float]],
    click_ts: float,
) -> list[Path]:
    candidates: list[Path] = []
    for p in folder.iterdir():
        if not p.is_file():
            continue
        if p.name.endswith(".crdownload"):
            continue
        if p.suffix.lower() not in {".csv", ".xlsx"}:
            continue
        try:
            resolved = p.resolve()
            size, mtime = _file_meta(p)
        except OSError:
            continue
        if size < MIN_CSV_BYTES:
            continue
        if mtime < click_ts - 3:
            continue
        old = before_meta.get(resolved)
        if old is None or size != old[0] or mtime > old[1] + 0.5:
            candidates.append(resolved)
    return candidates


def wait_for_new_csv(
    folder: Path,
    before_meta: dict[Path, tuple[int, float]],
    click_ts: float,
    *,
    timeout: int,
    log=None,
    log_level=None,
    label: str = "",
    should_stop: Callable[[], bool] | None = None,
    stall_abort_sec: int = STALL_ABORT_SEC,
) -> Path | None:
    """신규 또는 동일 경로 덮어쓰기 csv 가 안정될 때까지 대기."""
    deadline = time.time() + timeout
    candidate: Path | None = None
    last_size = -1
    stable_since: float | None = None
    last_heartbeat = time.time()
    last_progress = time.time()
    start = time.time()

    while time.time() < deadline:
        if should_stop and should_stop():
            return None

        crdownloads = [
            p.name for p in folder.iterdir()
            if p.is_file() and p.name.endswith(".crdownload")
        ]
        if crdownloads:
            last_progress = time.time()
            if time.time() - last_heartbeat >= HEARTBEAT_SEC:
                elapsed = int(time.time() - start)
                _log_info(
                    log,
                    log_level,
                    f"{label} Chrome 다운로드 중… {elapsed}s ({', '.join(crdownloads)})",
                )
                last_heartbeat = time.time()
            candidate = None
            last_size = -1
            stable_since = None
            time.sleep(0.5)
            continue

        picks = _iter_download_candidates(folder, before_meta, click_ts)
        if not picks:
            if time.time() - last_progress >= stall_abort_sec:
                elapsed = int(time.time() - start)
                _log_info(
                    log,
                    log_level,
                    f"{label} 진행 없음 {stall_abort_sec}s → 조기 중단 (경과 {elapsed}s)",
                )
                return None
            if time.time() - last_heartbeat >= HEARTBEAT_SEC:
                elapsed = int(time.time() - start)
                _log_info(
                    log,
                    log_level,
                    f"{label} 서버 CSV 생성 대기… {elapsed}s / 최대 {timeout}s",
                )
                last_heartbeat = time.time()
            time.sleep(0.5)
            continue

        last_progress = time.time()

        pick = max(picks, key=lambda p: p.stat().st_mtime)
        size = pick.stat().st_size
        if pick == candidate and size == last_size:
            if stable_since and time.time() - stable_since >= FILE_STABLE_SEC:
                return pick
        else:
            last_progress = time.time()
            candidate = pick
            last_size = size
            stable_since = time.time()
            if time.time() - last_heartbeat >= HEARTBEAT_SEC:
                elapsed = int(time.time() - start)
                _log_info(
                    log,
                    log_level,
                    f"{label} 파일 수신 중… {elapsed}s ({pick.name}, {size:,} bytes)",
                )
                last_heartbeat = time.time()
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


def wait_processing_popup(
    driver,
    *,
    timeout: int,
    log=None,
    log_level=None,
    label: str = "",
) -> None:
    """국토부 '처리중입니다' 팝업이 사라질 때까지 대기 (대용량 시도는 수 분)."""
    from selenium.webdriver.common.by import By

    deadline = time.time() + timeout
    last_heartbeat = time.time()
    start = time.time()

    while time.time() < deadline:
        try:
            popups = driver.find_elements(By.CSS_SELECTOR, ".layerPop")
            busy = False
            for popup in popups:
                if popup.is_displayed() and "처리중입니다" in popup.text:
                    busy = True
                    try:
                        popup.find_element(
                            By.XPATH, ".//button[contains(text(),'확인')]"
                        ).click()
                    except Exception:
                        pass
                    break
            if not busy:
                return
            if time.time() - last_heartbeat >= HEARTBEAT_SEC:
                elapsed = int(time.time() - start)
                _log_info(log, log_level, f"{label} 국토부 처리중… {elapsed}s / 최대 {timeout}s")
                last_heartbeat = time.time()
        except Exception:
            return
        time.sleep(2)


def append_failure_log(output_dir: Path, record: dict) -> None:
    path = output_dir / FAILURE_LOG_NAME
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _record_failure(
    result: DownloadResult,
    output_dir: Path,
    *,
    region: str,
    year: int,
    reason: str,
    property_type: PropertyType,
) -> None:
    rec = {
        "at": datetime.now(timezone.utc).isoformat(),
        "region": region,
        "year": year,
        "property_type": property_type.key,
        "reason": reason,
    }
    result.failures.append(rec)
    append_failure_log(output_dir, rec)


def _download_one_task(
    *,
    driver,
    wait,
    job: DownloadJob,
    region: str,
    year: int,
    from_date: str,
    to_date: str,
    download_dir: Path,
    chrome_dir: Path,
    result: DownloadResult,
    log,
    log_level,
    should_stop,
) -> str:
    """단일 (시도, 연도) 다운로드. 반환: done | failed | deferred."""
    from selenium.common.exceptions import UnexpectedAlertPresentException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC

    tag = f"{region} {year}"
    dl_timeout = download_timeout_sec(region)
    proc_timeout = processing_timeout_sec(region)
    file_path = download_dir / job.property_type.csv_filename(region, year)

    try:
        n_orphan = cleanup_orphan_temp_csv(chrome_dir, job.property_type)
        if n_orphan:
            _log_info(log, log_level, f"{tag} Chrome 임시 csv {n_orphan}개 정리")

        if not wait_folder_quiescent(
            chrome_dir,
            timeout=FOLDER_BUSY_TIMEOUT_SEC,
            log=log,
            log_level=log_level,
            label=tag,
        ):
            _log_info(log, log_level, f"{tag} 폴더 busy → 보류 (다른 작업 우선)")
            return "deferred"

        dismiss_alerts(driver)
        tab = wait.until(
            EC.element_to_be_clickable((By.ID, f"xlsTab{job.property_type.tab_id}"))
        )
        driver.execute_script("arguments[0].click();", tab)

        driver.find_element(By.ID, "srhFromDt").clear()
        driver.find_element(By.ID, "srhFromDt").send_keys(from_date)
        driver.find_element(By.ID, "srhToDt").clear()
        driver.find_element(By.ID, "srhToDt").send_keys(to_date)

        wait.until(EC.presence_of_element_located((By.ID, "srhSidoCd")))
        ok_sido, sido_reason = select_sido_region(driver, wait, region)
        if not ok_sido:
            _log_fail(log, log_level, f"{tag} {sido_reason}")
            _record_failure(
                result, download_dir,
                region=region, year=year, reason=sido_reason,
                property_type=job.property_type,
            )
            result.failed += 1
            return "failed"

        before_meta = snapshot_meta(chrome_dir)
        btn = wait.until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(text(),'CSV')]"))
        )
        click_ts = time.time()
        driver.execute_script("arguments[0].click();", btn)
        _log_info(
            log,
            log_level,
            f"{tag} 다운로드 시작… (최대 {dl_timeout}s, 진행 없으면 {STALL_ABORT_SEC}s 후 중단)",
        )
        time.sleep(POST_CLICK_WAIT_SEC)
        wait_processing_popup(
            driver,
            timeout=proc_timeout,
            log=log,
            log_level=log_level,
            label=tag,
        )

        alert_text = dismiss_alerts(driver)
        if alert_text:
            _log_fail(log, log_level, f"{tag} 알림: {alert_text}")
            if "실패" in alert_text:
                _record_failure(
                    result, download_dir,
                    region=region, year=year, reason=alert_text,
                    property_type=job.property_type,
                )
                result.failed += 1
                return "failed"

        temp_path = wait_for_new_csv(
            chrome_dir,
            before_meta,
            click_ts,
            timeout=dl_timeout,
            log=log,
            log_level=log_level,
            label=tag,
            should_stop=should_stop,
        )
        if temp_path is None:
            _log_info(
                log,
                log_level,
                f"{tag} 다운로드 미완료 → 보류 (다른 시도·연도 우선)",
            )
            return "deferred"

        ok, vreason = validate_csv_file(
            temp_path,
            region=region,
            year=year,
            property_type=job.property_type,
        )
        if not ok:
            moved = quarantine_csv(
                temp_path,
                download_dir,
                expected_region=region,
                year=year,
                property_type=job.property_type,
                reason=vreason,
            )
            _log_fail(
                log,
                log_level,
                f"{tag} 검증 실패 — {FAILED_SUBDIR}/ 보관 ({vreason}) → {moved.name}",
            )
            _record_failure(
                result, download_dir,
                region=region, year=year, reason=vreason,
                property_type=job.property_type,
            )
            result.failed += 1
            return "failed"

        try:
            move_csv_to_final(
                temp_path,
                file_path,
                log=log,
                log_level=log_level,
                label=tag,
            )
        except OSError as exc:
            _log_info(
                log,
                log_level,
                f"{tag} 저장 실패({exc}) → 보류 (다른 작업 우선)",
            )
            return "deferred"

        _log_info(log, log_level, f"{tag} 저장 완료 → {file_path.name}")
        result.done += 1
        return "done"

    except UnexpectedAlertPresentException:
        alert_text = dismiss_alerts(driver) or "알 수 없는 알림"
        _log_fail(log, log_level, f"{tag} 알림 오류: {alert_text}")
        _record_failure(
            result, download_dir,
            region=region, year=year, reason=alert_text,
            property_type=job.property_type,
        )
        result.failed += 1
        return "failed"
    except Exception:
        err = traceback.format_exc()
        _log_fail(log, log_level, f"{tag} 오류\n{err}")
        _log_info(log, log_level, f"{tag} → 보류 (다른 작업 우선)")
        return "deferred"


def run_download(
    job: DownloadJob,
    *,
    log: LogFn | None = None,
    log_level: LogLevelFn | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> DownloadResult:
    try:
        from selenium import webdriver
        from selenium.common.exceptions import UnexpectedAlertPresentException
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError as exc:
        raise RuntimeError("selenium 패키지가 필요합니다: py -m pip install selenium>=4.15") from exc

    years = list(range(job.start_year, job.end_year + 1))
    if not years:
        raise ValueError("연도 범위가 비어 있습니다.")
    if not job.regions:
        raise ValueError("선택된 시도가 없습니다.")

    download_dir = job.output_dir.expanduser().resolve()
    download_dir.mkdir(parents=True, exist_ok=True)
    chrome_dir = chrome_download_dir(download_dir)

    options = Options()
    if job.headless:
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

    year_ranges = [(y, f"{y}-01-01", f"{y}-12-31") for y in years]
    total = len(job.regions) * len(year_ranges)
    _log_info(
        log,
        log_level,
        "\n".join(
            [
                "다운로드 설정:",
                f"  유형={job.property_type.label_ko} {job.property_type.deal_type}",
                f"  시도={len(job.regions)}개",
                f"  연도={years[0]}~{years[-1]} ({len(years)}년)",
                f"  예상 파일={total}개",
                f"  신규 상한={job.max_new_downloads}",
                f"  저장={download_dir}",
                f"  Chrome 다운로드={chrome_dir}",
                f"  검증 실패 → {FAILED_SUBDIR}/ 보관 (삭제 안 함)",
                f"  작업 순서=연도별 시도 교차 (실패·보류 시 다른 시도 우선)",
                f"  진행 없음 조기중단={STALL_ABORT_SEC}s",
            ]
        ),
    )

    # 연도 → 시도 순: 경기 2019 실패 시 같은 연도 다른 시도부터 진행
    tasks: list[tuple[str, int, str, str]] = [
        (region, year, from_d, to_d)
        for year, from_d, to_d in year_ranges
        for region in job.regions
    ]

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 90)
    result = DownloadResult()
    max_new = max(0, int(job.max_new_downloads or 0))
    deferred: list[tuple[str, int, str, str]] = []

    def _should_abort() -> bool:
        return bool(
            result.stopped_reason
            or (should_stop and should_stop())
            or (max_new and result.done >= max_new)
        )

    def _process_tasks(
        queue: list[tuple[str, int, str, str]],
        *,
        pass_name: str,
        allow_defer: bool,
    ) -> list[tuple[str, int, str, str]]:
        next_deferred: list[tuple[str, int, str, str]] = []
        for region, year, from_date, to_date in queue:
            tag = f"{region} {year}"
            if should_stop and should_stop():
                result.stopped_reason = "user_stop"
                _log_info(log, log_level, "사용자 중지 요청")
                break
            if max_new and result.done >= max_new:
                result.stopped_reason = f"max_new_downloads={max_new}"
                _log_info(log, log_level, f"신규 다운로드 {max_new}건 도달 → 중단")
                break

            file_path = download_dir / job.property_type.csv_filename(region, year)
            if file_path.exists() and file_path.stat().st_size > 0:
                if job.revalidate_existing:
                    ok, reason = validate_csv_file(
                        file_path,
                        region=region,
                        year=year,
                        property_type=job.property_type,
                    )
                    if ok:
                        _log_info(log, log_level, f"{tag} 검증 OK → 스킵")
                        result.skipped += 1
                        continue
                    _log_fail(log, log_level, f"{tag} 기존 파일 검증 실패 → 재수집 ({reason})")
                    moved = quarantine_csv(
                        file_path,
                        download_dir,
                        expected_region=region,
                        year=year,
                        property_type=job.property_type,
                        reason=reason,
                    )
                    _log_info(log, log_level, f"{tag} 오염 파일 이동 → {moved.name}")
                    result.revalidated_bad += 1
                else:
                    _log_info(log, log_level, f"{tag} 이미 존재 → 스킵")
                    result.skipped += 1
                    continue

            if pass_name != "1차":
                _log_info(log, log_level, f"{tag} {pass_name} 재시도")

            outcome = _download_one_task(
                driver=driver,
                wait=wait,
                job=job,
                region=region,
                year=year,
                from_date=from_date,
                to_date=to_date,
                download_dir=download_dir,
                chrome_dir=chrome_dir,
                result=result,
                log=log,
                log_level=log_level,
                should_stop=should_stop,
            )
            if outcome == "deferred":
                if allow_defer:
                    next_deferred.append((region, year, from_date, to_date))
                else:
                    reason = "재시도 후에도 실패(다운로드·저장)"
                    _log_fail(log, log_level, f"{tag} {reason}")
                    _record_failure(
                        result, download_dir,
                        region=region, year=year, reason=reason,
                        property_type=job.property_type,
                    )
                    result.failed += 1

            time.sleep(INTER_REQUEST_SLEEP_SEC)
        return next_deferred

    try:
        driver.get(MOLIT_XLS_URL)
        deferred = _process_tasks(tasks, pass_name="1차", allow_defer=True)
        if deferred and not _should_abort():
            _log_info(
                log,
                log_level,
                f"보류 {len(deferred)}건 → 마지막 일괄 재시도 (다른 작업 완료 후)",
            )
            _process_tasks(deferred, pass_name="재시도", allow_defer=False)
    finally:
        driver.quit()
        result.manifest_path = write_manifest(
            download_dir,
            property_type=job.property_type,
            regions=job.regions,
            years=years,
            stats={
                "done": result.done,
                "skipped": result.skipped,
                "failed": result.failed,
                "revalidated_bad": result.revalidated_bad,
            },
            stopped_reason=result.stopped_reason,
        )
        _log_info(
            log,
            log_level,
            f"수집 종료: 완료 {result.done}, 스킵 {result.skipped}, "
            f"실패 {result.failed}, 오염재수집 {result.revalidated_bad}",
        )
        if result.failures:
            _log_fail(log, log_level, "실패 목록 (해당 시도만 선택 후 재실행):")
            for f in result.failures:
                _log_fail(log, log_level, f"  · {f['region']} {f['year']}: {f['reason']}")
        if result.stopped_reason:
            _log_info(log, log_level, f"중단 사유: {result.stopped_reason}")
        _log_info(log, log_level, f"manifest: {result.manifest_path}")

    return result
