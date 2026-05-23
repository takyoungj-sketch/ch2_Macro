#!/usr/bin/env python3
"""
국토교통부 실거래가 엑셀 수집 (토지 매매 전용).

`참고/0.수집.ipynb` 와 같은 Selenium 흐름:
  rt.molit.go.kr → 탭 선택 → 계약일 · 시도 선택 → EXCEL 다운 ...

기본 출력: `<repo>/raw/토지/<cycle_id>/토지_매매/<시도명>/<파일>.xlsx`
`flatten_raw_xlsx.py` 로 같은 cycle 폴더 아래 평탄화 후 파이프라인에 넣으면 된다.

예)
  py scripts/monthly/download_molit_land_xlsx.py --cycle-id 202605 --limit-regions 1
  py scripts/monthly/download_molit_land_xlsx.py --cycle-id 202605
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# repo 루트 (scripts/monthly/ 기준 두 단계 상위)
REPO_ROOT = Path(__file__).resolve().parents[2]

MOLIT_XLS_URL = "https://rt.molit.go.kr/pt/xls/xls.do?mobileAt="

# 노트북과 동일: 토지는 xlsTab7
LAND_PROPERTY_TYPE = 7
LAND_TYPE_LABEL_KO = "토지"

# 공개 사이트 시도 선택 옵션 텍스트와 정확히 일치해야 함 (공백 제거 후 비교).
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


def get_date_ranges(start: str, end: str) -> list[tuple[int, str, str]]:
    """달력연도 단위로 (year, from_date, to_date) 목록 생성 (참고 노트북과 동일)."""
    result: list[tuple[int, str, str]] = []
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    for year in range(start_dt.year, end_dt.year + 1):
        from_dt = max(start_dt, datetime(year, 1, 1))
        to_dt = min(end_dt, datetime(year, 12, 31))
        result.append((year, from_dt.strftime("%Y-%m-%d"), to_dt.strftime("%Y-%m-%d")))
    return result


def resolve_regions(args: argparse.Namespace) -> list[str]:
    if args.regions.strip():
        return [r.strip() for r in args.regions.split(",") if r.strip()]
    out = list(DEFAULT_SIDO_LIST)
    if args.limit_regions and args.limit_regions > 0:
        out = out[: args.limit_regions]
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Molit 실거래 토지(매매) 엑셀 일괄 다운로드")
    p.add_argument(
        "--cycle-id",
        metavar="YYYYMM",
        default="202605",
        help="저장 디렉터리 raw/토지/<cycle-id> 에 사용 (기본 202605 = 2026년 5월 초 갱신 가정)",
    )
    p.add_argument(
        "--output-dir",
        type=str,
        default="",
        help="토지_매매 상위 디렉터리. 미지정 시 <repo>/raw/토지/<cycle-id>",
    )
    p.add_argument("--start-date", default="2025-05-01", help="계약일 시작")
    p.add_argument("--end-date", default="2026-04-30", help="계약일 종료")
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
        help="Chrome headless=new (환경에 따라 다운 실패 가능 — 기본은 창 표시)",
    )
    return p


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
    property_type = LAND_PROPERTY_TYPE
    deal_type_name = "매매"
    regions = resolve_regions(args)
    if not regions:
        print("선택된 시도가 없습니다.")
        sys.exit(1)

    if args.output_dir.strip():
        base_parent = Path(args.output_dir.strip()).expanduser().resolve()
    else:
        base_parent = (REPO_ROOT / "raw" / "토지" / args.cycle_id).resolve()
    os.makedirs(base_parent, exist_ok=True)

    download_dir = base_parent / f"{LAND_TYPE_LABEL_KO}_{deal_type_name}"
    download_dir.mkdir(parents=True, exist_ok=True)

    options = Options()
    if args.headless:
        options.add_argument("--headless=new")
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )

    date_ranges = get_date_ranges(args.start_date, args.end_date)
    print(
        "다운로드 설정:",
        f"시도={len(regions)}개",
        f"기간={args.start_date}~{args.end_date}",
        f"연도 슬라이스={len(date_ranges)}건/시도",
        f"저장={download_dir}",
        sep="\n  ",
        flush=True,
    )

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 60)

    try:
        driver.get(MOLIT_XLS_URL)
        for region in regions:
            region_folder = download_dir / region
            region_folder.mkdir(parents=True, exist_ok=True)
            for year, from_date, to_date in date_ranges:
                file_name = f"{region}_{LAND_TYPE_LABEL_KO}_{deal_type_name}_{year}.xlsx"
                file_path = region_folder / file_name
                if file_path.exists():
                    print(region, year, "이미 존재 → 스킵", flush=True)
                    continue

                try:
                    wait.until(
                        EC.element_to_be_clickable((By.ID, f"xlsTab{property_type}"))
                    ).click()

                    driver.find_element(By.ID, "srhFromDt").clear()
                    driver.find_element(By.ID, "srhFromDt").send_keys(from_date)
                    driver.find_element(By.ID, "srhToDt").clear()
                    driver.find_element(By.ID, "srhToDt").send_keys(to_date)

                    sido_select = wait.until(
                        EC.presence_of_element_located((By.ID, "srhSidoCd"))
                    )
                    for option in sido_select.find_elements(By.TAG_NAME, "option"):
                        if option.text.strip() == region.strip():
                            option.click()
                            break
                    else:
                        print(region, year, "시도 옵션을 찾지 못함 → 스킵", flush=True)
                        continue

                    btn = wait.until(
                        EC.presence_of_element_located(
                            (By.XPATH, "//button[contains(text(),'EXCEL 다운')]")
                        )
                    )
                    driver.execute_script("arguments[0].click();", btn)
                    print(region, year, "다운로드 시작", flush=True)
                    time.sleep(2)
                    handle_processing_popup(driver)
                    wait_for_downloads(str(download_dir))

                    candidates = [
                        os.path.join(download_dir, f)
                        for f in os.listdir(download_dir)
                        if os.path.isfile(os.path.join(download_dir, f))
                        and (f.endswith(".xlsx") or f.endswith(".XLSX"))
                        and Path(os.path.join(download_dir, f)) != Path(file_path)
                    ]
                    if not candidates:
                        print(region, year, ".xlsx 없음 → 실패 처리", flush=True)
                        continue

                    newest = max(candidates, key=os.path.getctime)
                    Path(newest).replace(file_path)
                    print(region, year, "저장 완료 →", file_path, flush=True)
                except Exception:
                    print(region, year, "오류", flush=True)
                    traceback.print_exc()

                time.sleep(2)
    finally:
        driver.quit()
        print("수집 종료", flush=True)


if __name__ == "__main__":
    main()
