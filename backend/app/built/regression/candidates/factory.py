"""복합부동산 Candidate Factory — 생성과 검증만 담당."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.built.asset_scope import apply_asset_type_filter
from app.built.regression.candidates.base import (
    CandidateContext,
    CandidateProvider,
    CandidateSpec,
    CandidateValidation,
    validate_candidate,
)
from app.built.time_scope import apply_contract_date_window, parse_as_of_month


@dataclass(frozen=True)
class CandidateFactoryResult:
    accepted: tuple[CandidateSpec, ...]
    validations: tuple[CandidateValidation, ...]


_ADMIN_LEVEL_COLUMN: dict[str, str] = {
    "sigungu": "sigungu_code",
    "gu": "sigungu_code",
    "eupmyeondong": "eupmyeondong_code",
    "beopjungri": "beopjungri_code",
}


def _region_where_clauses(
    *,
    admin_level: str,
    region_codes: tuple[str, ...],
    asset_type: str | None,
    contract_year_from: int | None,
    contract_year_to: int | None,
    as_of_month: str | None,
    window_years: int | None,
) -> tuple[str | None, list[str], dict[str, object]]:
    """anchor 표본과 무관하게 후보 지역 자체를 조회하기 위한 WHERE 절.

    region_counts_from_db·fetch_candidate_rows가 공유한다 — 둘 다 anchor
    조회 범위 밖의 Twin 지역 데이터가 필요하다는 동일한 이유에서 나왔다.
    """
    column = _ADMIN_LEVEL_COLUMN.get(admin_level)
    if not column or not region_codes:
        return None, [], {}
    clauses = ["is_valid = true", f"{column} = ANY(:codes)"]
    params: dict[str, object] = {"codes": list(region_codes)}
    apply_asset_type_filter(clauses, params, asset_type)
    if contract_year_from is not None:
        clauses.append("contract_year >= :cy_from")
        params["cy_from"] = contract_year_from
    if contract_year_to is not None:
        clauses.append("contract_year <= :cy_to")
        params["cy_to"] = contract_year_to
    if as_of_month and window_years:
        apply_contract_date_window(
            clauses,
            params,
            as_of_month=parse_as_of_month(as_of_month),
            window_years=window_years,
        )
    return column, clauses, params


def region_counts_from_frame(
    df: pd.DataFrame,
    *,
    admin_level: str,
) -> dict[str, int]:
    """built 원장의 canonical 지역코드별 거래건수를 계산한다."""

    column = {
        "sigungu": "sigungu_code",
        "eupmyeondong": "eupmyeondong_code",
        "beopjungri": "beopjungri_code",
    }.get(admin_level)
    if not column or column not in df.columns:
        return {}
    values = df[column].astype("string").str.strip()
    return {
        str(code): int(count)
        for code, count in values.dropna().value_counts().items()
        if str(code)
    }


def region_counts_from_db(
    conn,
    *,
    admin_level: str,
    region_codes: tuple[str, ...],
    asset_type: str | None,
    contract_year_from: int | None = None,
    contract_year_to: int | None = None,
    as_of_month: str | None = None,
    window_years: int | None = None,
) -> dict[str, int]:
    """anchor 표본과 무관하게 built 원장에서 지역코드별 거래건수를 조회한다.

    Twin/Region Group 후보 지역은 anchor 조회 범위(complete-case 표본)에는
    존재하지 않으므로, region_counts_from_frame(ctx.df)만으로는 항상 0건으로
    잡혀 모든 후보가 region_coverage에서 탈락한다. 후보 검증은 반드시 원장
    전체에서 후보 지역 자체의 거래량을 별도 조회해야 한다.
    """
    column, clauses, params = _region_where_clauses(
        admin_level=admin_level,
        region_codes=region_codes,
        asset_type=asset_type,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        as_of_month=as_of_month,
        window_years=window_years,
    )
    if not column:
        return {}

    from sqlalchemy import text

    where = " AND ".join(clauses)
    sql = f"""
        SELECT {column} AS code, COUNT(*) AS n
        FROM built_transactions
        WHERE {where}
        GROUP BY {column}
    """
    rows = conn.execute(text(sql), params).mappings().all()
    return {
        str(row["code"]).strip(): int(row["n"])
        for row in rows
        if row["code"] is not None and str(row["code"]).strip()
    }


def region_price_levels_from_db(
    conn,
    *,
    admin_level: str,
    region_codes: tuple[str, ...],
    asset_type: str | None,
    contract_year_from: int | None = None,
    contract_year_to: int | None = None,
    as_of_month: str | None = None,
    window_years: int | None = None,
    min_n: int = 3,
) -> dict[str, float]:
    """지역별 ㎡당 가격 median(price/gross_area) — Twin Pooling 가격수준 hard gate.

    Twin 유사도(v21)는 시장 구성 *비중*만 보고 상가 가격 *수준* 자체는 반영하지
    않는다(§E3 백로그, docs/CANDIDATE_EVALUATION_DESIGN.md). Pooling 단계에서
    anchor와 극단적으로 다른 가격대의 Twin이 pool에 섞이는 것을 막기 위해
    별도로 검증한다. 표본이 min_n 미만인 지역은 결과에서 제외한다(gate 생략
    신호 — 데이터 부족을 가격 불일치로 오판하지 않도록).
    """
    column, clauses, params = _region_where_clauses(
        admin_level=admin_level,
        region_codes=region_codes,
        asset_type=asset_type,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        as_of_month=as_of_month,
        window_years=window_years,
    )
    if not column:
        return {}

    from sqlalchemy import text

    clauses = [*clauses, "gross_area IS NOT NULL", "gross_area > 0", "price IS NOT NULL"]
    where = " AND ".join(clauses)
    sql = f"""
        SELECT {column} AS code,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY price / gross_area) AS median_psqm,
               COUNT(*) AS n
        FROM built_transactions
        WHERE {where}
        GROUP BY {column}
        HAVING COUNT(*) >= :min_n
    """
    rows = conn.execute(text(sql), {**params, "min_n": min_n}).mappings().all()
    return {
        str(row["code"]).strip(): float(row["median_psqm"])
        for row in rows
        if row["code"] is not None and str(row["code"]).strip() and row["median_psqm"] is not None
    }


def fetch_candidate_rows(
    conn,
    *,
    admin_level: str,
    region_codes: tuple[str, ...],
    asset_type: str | None,
    contract_year_from: int | None = None,
    contract_year_to: int | None = None,
    as_of_month: str | None = None,
    window_years: int | None = None,
) -> pd.DataFrame:
    """anchor 표본과 무관하게 후보 지역 자체의 built 원장 원행을 조회한다.

    Twin Pooling 후보를 실제로 적합(fit)하려면 anchor 조회 범위 밖에 있는
    Twin 지역의 원행이 필요하다 — region_counts_from_db와 동일한 이유다.
    반환 컬럼은 built.regression.engine._fetch_df와 동일하게 맞춰
    기존 fit_best_scale·with_complete_case를 그대로 재사용할 수 있게 한다.
    """
    column, clauses, params = _region_where_clauses(
        admin_level=admin_level,
        region_codes=region_codes,
        asset_type=asset_type,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        as_of_month=as_of_month,
        window_years=window_years,
    )
    if not column:
        return pd.DataFrame()

    from sqlalchemy import text

    where = " AND ".join(clauses)
    sql = f"""
        SELECT price, gross_area, land_area, building_age, road_code, road_width_label,
               zone_type, building_use, asset_type, contract_year,
               addr1, addr2, addr3, addr4, addr5,
               sigungu_code, eupmyeondong_code, beopjungri_code
        FROM built_transactions
        WHERE {where}
    """
    rows = conn.execute(text(sql), params).mappings().all()
    return pd.DataFrame(rows)


def generate_candidates(
    providers: list[CandidateProvider],
    *,
    context: CandidateContext,
    region_counts: dict[str, int],
    min_region_n: int = 5,
) -> CandidateFactoryResult:
    """Provider 후보를 생성하고 검증 결과를 함께 반환한다.

    `accepted` 후보는 이후 Evaluation Engine에 전달할 수 있지만,
    이 함수 자체는 표본을 합치거나 회귀를 적합하지 않는다.
    """

    accepted: list[CandidateSpec] = []
    validations: list[CandidateValidation] = []
    seen_ids: set[str] = set()
    for provider in providers:
        for candidate in provider.generate(context):
            if candidate.candidate_id in seen_ids:
                continue
            seen_ids.add(candidate.candidate_id)
            validation = validate_candidate(
                candidate,
                context=context,
                region_counts=region_counts,
                min_region_n=min_region_n,
            )
            validations.append(validation)
            if validation.accepted:
                accepted.append(candidate)
    return CandidateFactoryResult(
        accepted=tuple(accepted),
        validations=tuple(validations),
    )
