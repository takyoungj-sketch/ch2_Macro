#!/usr/bin/env python3
"""
국토교통부 실거래가 CSV 수집 (오피스텔 매매).

`참고/0.수집.ipynb` 와 같은 Selenium 흐름:
  rt.molit.go.kr → 오피스텔 탭 → 계약일 · 시도 선택 → CSV 다운 ...

기본 출력: `<repo>/원본/오피스텔/<시도>_오피스텔_매매_<연도>.csv` (연도별·시도별 flat)

예)
  py scripts/monthly/download_molit_officetel_csv.py --limit-regions 1 --years 2021
  py scripts/monthly/download_molit_officetel_csv.py --start-year 2021 --end-year 2025
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

MOLIT_XLS_URL = "https://rt.molit.go.kr/pt/xls/xls.do?mobileAt="

OFFICETEL_PROPERTY_TYPE = 4
TYPE_LABEL_KO = "오피스텔"
DEAL_TYPE_NAME = "매매"

DEFAULT_SIDO_LIST = [
    "서울특별시",
    "부산광역시",
    "대구광역시",
    "인천광역시",
    "광주광역시",
    "대전광역시",
    "울산광역시",
    "세종특별자치시",
    "경기도",
    "강원특별자치도",
    "충청북도",
    "충청남도",
    "전북특별자치도",
    "전라남도",
    "경상북도",
    "경상남도",
    "제주특별자치도",
]


def wait_for_downloads(folder: str, timeout: int = 180) -> None:
    folder_path = Path(folder)
    for _ in range(timeout):
        try:
            names = list(folder_path.iterdir())
        except OSError:
            time.sleep(1)
            continue
        if not any(p.name.endswith(".crdownload") for p in names if p.is_file()):
            return
        time.sleep(1)
    print("다운로드 대기 시간 초과 (아직 .crdownload 가 남았을 수 있음)")


def handle_processing_popup(driver) -> None:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    try:
        popup = WebDriverWait(driver, 3).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".layerPop"))
        )
        if "처리중입니다" in popup.text:
            popup.find_element(By.XPATH, ".//button[contains(text(),'확인')]").click()
            print("팝업 확인 클릭")
    except Exception:
        pass


def resolve_regions(args: argparse.Namespace) -> list[str]:
    if args.regions.strip():
        return [r.strip() for r in args.regions.split(",") if r.strip()]
    out = list(DEFAULT_SIDO_LIST)
    if args.limit_regions and args.limit_regions > 0:
        out = out[: args.limit_regions]
    return out


def resolve_years(args: argparse.Namespace) -> list[int]:
    if args.years.strip():
        return [int(y.strip()) for y in args.years.split(",") if y.strip()]
    return list(range(args.start_year, args.end_year + 1))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Molit 실거래 오피스텔(매매) CSV 일괄 다운로드")
    p.add_argument(
        "--output-dir",
        type=str,
        default="",
        help="저장 폴더. 미지정 시 <repo>/원본/오피스텔",
    )
    p.add_argument("--start-year", type=int, default=2021, help="시작 연도 (포함)")
    p.add_argument("--end-year", type=int, default=2025, help="종료 연도 (포함)")
    p.add_argument(
        "--years",
        type=str,
        default="",
        help="연도 쉼표 구분 (예: 2021,2022). 지정 시 start/end-year 무시",
    )
    p.add_argument(
        "--regions",
        type=str,
        default="",
        help="시도 이름 쉼표 구분 (비우면 전국 또는 --limit-regions 적용 목록 전체)",
    )
    p.add_argument(
        "--limit-regions",
        type=int,
        default=0,
        metavar="N",
        help="처음 N개 시도만 (검증용). --regions 가 있으면 무시된다.",
    )
    p.add_argument(
        "--headless",
        action="store_true",
        help="Chrome headless=new (환경에 따라 다운 실패 가능. 기본은 창 표시)",
    )
    return p


def newest_download_candidate(download_dir: Path, exclude: Path) -> Path | None:
    candidates: list[Path] = []
    for p in download_dir.iterdir():
        if not p.is_file():
            continue
        if p == exclude:
            continue
        lower = p.name.lower()
        if lower.endswith(".csv") or lower.endswith(".xlsx"):
            candidates.append(p)
    if not candidates:
        return None
    return max(candidates, key=lambda x: x.stat().st_ctime)


def main() -> None:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError:
        print("selenium 패키지가 필요합니다: py -m pip install selenium>=4", file=sys.stderr)
        sys.exit(1)

    args = build_parser().parse_args()
    regions = resolve_regions(args)
    years = resolve_years(args)
    if not regions:
        print("선택된 시도가 없습니다.")
        sys.exit(1)
    if not years:
        print("선택된 연도가 없습니다.")
        sys.exit(1)

    if args.output_dir.strip():
        download_dir = Path(args.output_dir.strip()).expanduser().resolve()
    else:
        download_dir = (REPO_ROOT / "원본" / "오피스텔").resolve()
    download_dir.mkdir(parents=True, exist_ok=True)

    options = Options()
    if args.headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )

    year_ranges = [(y, f"{y}-01-01", f"{y}-12-31") for y in years]
    total = len(regions) * len(year_ranges)
    print(
        "다운로드 설정:",
        f"유형={TYPE_LABEL_KO} {DEAL_TYPE_NAME}",
        f"시도={len(regions)}개",
        f"연도={years[0]}~{years[-1]} ({len(years)}년)",
        f"예상 파일={total}개",
        f"저장={download_dir}",
        sep="\n  ",
        flush=True,
    )

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 60)
    done = 0
    skipped = 0
    failed = 0

    try:
        driver.get(MOLIT_XLS_URL)
        for region in regions:
            for year, from_date, to_date in year_ranges:
                file_name = f"{region}_{TYPE_LABEL_KO}_{DEAL_TYPE_NAME}_{year}.csv"
                file_path = download_dir / file_name
                if file_path.exists() and file_path.stat().st_size > 0:
                    print(region, year, "이미 존재 → 스킵", flush=True)
                    skipped += 1
                    continue

                try:
                    tab = wait.until(
                        EC.element_to_be_clickable(
                            (By.ID, f"xlsTab{OFFICETEL_PROPERTY_TYPE}")
                        )
                    )
                    driver.execute_script("arguments[0].click();", tab)

                    driver.find_element(By.ID, "srhFromDt").clear()
                    driver.find_element(By.ID, "srhFromDt").send_keys(from_date)
                    driver.find_element(By.ID, "srhToDt").clear()
                    driver.find_element(By.ID, "srhToDt").send_keys(to_date)

                    sido_select = wait.until(
                        EC.presence_of_element_located((By.ID, "srhSidoCd"))
                    )
                    matched = False
                    for option in sido_select.find_elements(By.TAG_NAME, "option"):
                        if option.text.strip() == region.strip():
                            option.click()
                            matched = True
                            break
                    if not matched:
                        print(region, year, "시도 옵션을 찾지 못함 → 스킵", flush=True)
                        failed += 1
                        continue

                    btn = wait.until(
                        EC.presence_of_element_located(
                            (By.XPATH, "//button[contains(text(),'CSV')]")
                        )
                    )
                    driver.execute_script("arguments[0].click();", btn)
                    print(region, year, "다운로드 시작", flush=True)
                    time.sleep(2)
                    handle_processing_popup(driver)
                    wait_for_downloads(str(download_dir))

                    newest = newest_download_candidate(download_dir, file_path)
                    if newest is None:
                        print(region, year, "csv 없음 → 실패", flush=True)
                        failed += 1
                        continue

                    newest.replace(file_path)
                    print(region, year, "저장 완료 →", file_path.name, flush=True)
                    done += 1
                except Exception:
                    print(region, year, "오류", flush=True)
                    traceback.print_exc()
                    failed += 1

                time.sleep(2)
    finally:
        driver.quit()
        print(
            f"수집 종료: 완료 {done}, 스킵 {skipped}, 실패 {failed}",
            flush=True,
        )


if __name__ == "__main__":
    main()
