"""Regional Profile Twin API 응답을 Candidate Provider 입력으로 변환."""

from __future__ import annotations

from collections.abc import Mapping


def normalize_profile_twin_neighbors(
    payload: Mapping[str, object],
    *,
    admin_level: str,
) -> list[dict[str, object]]:
    """Profile-native Twin 응답에서 지역코드·유사도만 정규화한다.

    이 함수는 과거 `/api/twin-v8` 응답을 자동 fallback하지 않는다.
    Profile API의 algorithm_version이 21이 아니면 빈 결과를 반환한다.
    """

    if int(payload.get("algorithm_version") or 0) != 21:
        return []
    neighbors = payload.get("neighbors")
    if not isinstance(neighbors, list):
        return []

    code_key = {
        "sigungu": "twin_sigungu_code",
        "eupmyeondong": "twin_eupmyeondong_code",
        "beopjungri": "twin_beopjungri_code",
    }.get(admin_level)
    if not code_key:
        return []

    normalized: list[dict[str, object]] = []
    for row in neighbors:
        if not isinstance(row, Mapping):
            continue
        code = str(row.get(code_key) or "").strip()
        if not code:
            continue
        normalized.append(
            {
                "region_code": code,
                "similarity_score": row.get("similarity_score"),
                "profile_version": payload.get("profile_version"),
                "profile_as_of_month": payload.get("as_of_month"),
                "profile_window_years": payload.get("window_years"),
                "algorithm_version": payload.get("algorithm_version"),
            }
        )
    return normalized
