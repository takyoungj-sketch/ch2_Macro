"""
법정동 코드 파일(CSV/탭, 행정안전부·국토교통부 등)을 읽어 region_codes 테이블에 시드 적재한다.

법정동 코드 파일 다운로드:
    - 행정안전부 등: 법정동코드_전체자료.txt (탭 구분, EUC-KR/UTF-8)
    - 국토교통부 등: 국토교통부_법정동코드_YYYYMMDD.csv (쉼표 구분, UTF-8)
    예: https://www.data.go.kr/data/15077663/fileData.do

필수 컬럼: 법정동코드, 법정동명칭, 폐지여부 (다른 이름은 스크립트 후보 목록 참고)

사용법:
    python seed_region_codes.py --file 법정동코드.csv --sido 충청북도
    python seed_region_codes.py --file 법정동코드.txt          # 전국 적재
    python seed_region_codes.py --file 법정동코드.csv --dry-run
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from tqdm import tqdm

from db_utils import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# 시도 이름 → 2자리 코드 매핑 (법정동 코드 첫 2자리)
SIDO_CODE_MAP = {
    "서울특별시": "11",
    "부산광역시": "26",
    "대구광역시": "27",
    "인천광역시": "28",
    "광주광역시": "29",
    "대전광역시": "30",
    "울산광역시": "31",
    "세종특별자치시": "36",
    "경기도": "41",
    "강원특별자치도": "51",
    "충청북도": "43",
    "충청남도": "44",
    "전북특별자치도": "52",
    "전라남도": "46",
    "경상북도": "47",
    "경상남도": "48",
    "제주특별자치도": "50",
}


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _has_beopjungdong_columns(df: pd.DataFrame) -> bool:
    """법정동 마스터용 필수 컬럼이 구분자에 맞게 분리되어 있는지 확인한다."""
    code = _find_col(df, ["법정동코드", "법정동 코드", "code"])
    name = _find_col(df, ["법정동명칭", "법정동 명칭", "name"])
    status = _find_col(df, ["폐지여부", "상태", "status"])
    return bool(code and name and status)


def load_beopjungdong_file(file_path: str) -> pd.DataFrame:
    """
    법정동 코드 파일을 읽어 DataFrame으로 반환한다.
    구분자: 쉼표(CSV)·탭(TSV) 자동 시도.
    인코딩: UTF-8 BOM / EUC-KR / UTF-8 순으로 시도한다.
    """
    path = Path(file_path)
    encodings = ("utf-8-sig", "euc-kr", "utf-8")
    # CSV(국토부 등)를 먼저 시도한 뒤 기존 탭 텍스트 호환
    separators = (",", "\t")

    last_error: Exception | None = None
    for encoding in encodings:
        for sep in separators:
            try:
                df = pd.read_csv(
                    path,
                    sep=sep,
                    header=0,
                    dtype=str,
                    encoding=encoding,
                    on_bad_lines="skip",
                )
            except UnicodeDecodeError:
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                continue

            df.columns = [str(c).strip() for c in df.columns]
            if len(df.columns) < 3 or not _has_beopjungdong_columns(df):
                continue

            sep_label = "comma" if sep == "," else "tab"
            log.info(
                "파일 로드 성공 (encoding=%s, sep=%s): %d행",
                encoding,
                sep_label,
                len(df),
            )
            return df

    hint = f" ({last_error})" if last_error else ""
    raise RuntimeError(
        f"법정동 코드 파일을 읽을 수 없습니다 (CSV/탭·인코딩 조합 실패): {file_path}{hint}"
    )


def parse_beopjungdong(df: pd.DataFrame, sido_filter: str | None) -> list[dict]:
    """
    법정동 코드 DataFrame을 파싱해 region_codes 삽입용 레코드 목록을 반환한다.

    법정동 코드 10자리 구조:
        SS GGG EEE LL
        ├─ SS  : 시도코드 (2자리)
        ├─ GGG : 시군구코드 (3자리 → 총 5자리)
        ├─ EEE : 읍면동코드 (3자리 → 총 8자리)
        └─ LL  : 리코드 (2자리 → 총 10자리, 동 단위는 00)

    삽입 대상:
        - LL != "00" : 법정리 단위 → beopjungri_code = 10자리 코드
        - LL == "00" AND EEE != "000" AND 해당 읍면동에 리 자식이 없는 경우
          → 법정동(동) 단위 → beopjungri_code = 8자리 + "00"
    """
    col_code = _find_col(df, ["법정동코드", "법정동 코드", "code"])
    col_name = _find_col(df, ["법정동명칭", "법정동 명칭", "name"])
    col_status = _find_col(df, ["폐지여부", "상태", "status"])

    if not all([col_code, col_name, col_status]):
        raise RuntimeError(
            f"필수 컬럼을 찾을 수 없습니다. 실제 컬럼: {list(df.columns)}"
        )

    df = df[[col_code, col_name, col_status]].copy()
    df.columns = ["code", "name", "status"]
    df["code"] = df["code"].astype(str).str.strip().str.zfill(10)
    df["name"] = df["name"].astype(str).str.strip()

    # 존재하는 코드만
    df = df[df["status"].str.strip() == "존재"].copy()

    # 시도 필터
    if sido_filter:
        sido_code = SIDO_CODE_MAP.get(sido_filter)
        if not sido_code:
            raise ValueError(
                f"알 수 없는 시도 이름: {sido_filter}. 사용 가능: {list(SIDO_CODE_MAP.keys())}"
            )
        df = df[df["code"].str.startswith(sido_code)].copy()
        log.info("시도 필터(%s, %s) 적용 후: %d행", sido_filter, sido_code, len(df))

    # 계층 빌드용 lookup: code → full_name
    code_to_name: dict[str, str] = dict(zip(df["code"], df["name"]))

    # 읍면동 코드(8자리+00)에 리 자식이 있는지 여부 집합
    eupmyeondong_with_ri: set[str] = set()
    for code in df["code"]:
        if code[8:] != "00":  # 리 레벨
            eupmyeondong_with_ri.add(code[:8] + "00")

    records = []
    seen_beopjungri: set[str] = set()

    for _, row in df.iterrows():
        code: str = row["code"]
        full_name: str = row["name"]

        sido_code_2 = code[:2]
        sigungu_code_5 = code[:5]
        eupmyeondong_code_8 = code[:8]
        li_suffix = code[8:]

        # 시도 레벨: 처리 건너뜀
        if code[2:] == "00000000":
            continue
        # 시군구 레벨: 처리 건너뜀
        if code[5:] == "00000":
            continue

        is_ri_level = (li_suffix != "00")
        is_dong_leaf = (li_suffix == "00" and eupmyeondong_code_8 + "00" not in eupmyeondong_with_ri)

        if not (is_ri_level or is_dong_leaf):
            continue

        beopjungri_code = code  # 리 단위는 10자리 그대로, 동 단위도 '00' 포함 10자리

        if beopjungri_code in seen_beopjungri:
            continue
        seen_beopjungri.add(beopjungri_code)

        # 이름 분리: "충청북도 청주시 청원구 오창읍 가곡리" 형태
        name_parts = full_name.split()

        sido_name = name_parts[0] if len(name_parts) >= 1 else ""

        # 시군구 이름: 두 번째 토큰 (도 → 시/군, 광역시 → 구/군)
        # 세 번째가 '구'/'군'으로 끝나면 시+구 합산 (예: 청주시 청원구)
        if len(name_parts) >= 3 and (name_parts[2].endswith("구") or (name_parts[2].endswith("군") and not name_parts[2].endswith("면"))):
            sigungu_name = f"{name_parts[1]} {name_parts[2]}"
            rest = name_parts[3:]
        elif len(name_parts) >= 2:
            sigungu_name = name_parts[1]
            rest = name_parts[2:]
        else:
            sigungu_name = ""
            rest = []

        eupmyeondong_name = rest[0] if len(rest) >= 1 else ""
        beopjungri_name = rest[1] if len(rest) >= 2 else eupmyeondong_name

        # 부모 시군구 이름 보완 (직접 코드로 조회)
        sigungu_full = code_to_name.get(sigungu_code_5 + "00000", "")
        if sigungu_full:
            sg_parts = sigungu_full.split()
            if len(sg_parts) >= 3 and (sg_parts[2].endswith("구") or (sg_parts[2].endswith("군") and not sg_parts[2].endswith("면"))):
                sigungu_name = f"{sg_parts[1]} {sg_parts[2]}"
            elif len(sg_parts) >= 2:
                sigungu_name = sg_parts[1]

        records.append({
            "sido_code": sido_code_2,
            "sido_name": sido_name,
            "sigungu_code": sigungu_code_5,
            "sigungu_name": sigungu_name,
            "eupmyeondong_code": eupmyeondong_code_8,
            "eupmyeondong_name": eupmyeondong_name,
            "beopjungri_code": beopjungri_code,
            "beopjungri_name": beopjungri_name,
        })

    log.info("파싱 완료: %d개 법정동/리 레코드", len(records))
    return records


def upsert_region_codes(records: list[dict], dry_run: bool = False) -> int:
    """region_codes 테이블에 UPSERT 방식으로 적재한다."""
    if dry_run:
        log.info("[DRY RUN] 적재 대상 %d건 (실제 DB 반영 없음)", len(records))
        for r in records[:5]:
            log.info("  예시: %s", r)
        return 0

    engine = get_engine()
    inserted = 0

    with engine.begin() as conn:
        for rec in tqdm(records, desc="region_codes UPSERT"):
            conn.execute(
                text("""
                    INSERT INTO region_codes (
                        sido_code, sido_name,
                        sigungu_code, sigungu_name,
                        eupmyeondong_code, eupmyeondong_name,
                        beopjungri_code, beopjungri_name,
                        is_active, updated_at
                    ) VALUES (
                        :sido_code, :sido_name,
                        :sigungu_code, :sigungu_name,
                        :eupmyeondong_code, :eupmyeondong_name,
                        :beopjungri_code, :beopjungri_name,
                        TRUE, NOW()
                    )
                    ON CONFLICT (beopjungri_code) DO UPDATE SET
                        sido_name        = EXCLUDED.sido_name,
                        sigungu_name     = EXCLUDED.sigungu_name,
                        eupmyeondong_name = EXCLUDED.eupmyeondong_name,
                        beopjungri_name  = EXCLUDED.beopjungri_name,
                        is_active        = TRUE,
                        updated_at       = NOW()
                """),
                rec,
            )
            inserted += 1

    log.info("region_codes 적재 완료: %d건", inserted)
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="법정동 코드 시드 적재")
    parser.add_argument(
        "--file",
        required=True,
        help="법정동코드 파일 경로 (.csv 쉼표 / .txt 탭 구분 자동 인식)",
    )
    parser.add_argument(
        "--sido",
        default=None,
        help="시도 이름 (예: 충청북도). 미지정 시 전국 적재.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB에 실제로 반영하지 않고 결과만 미리 확인",
    )
    args = parser.parse_args()

    df = load_beopjungdong_file(args.file)
    records = parse_beopjungdong(df, sido_filter=args.sido)

    if not records:
        log.warning("적재할 레코드가 없습니다.")
        return

    upsert_region_codes(records, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
