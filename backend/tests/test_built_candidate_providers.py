from app.built.regression.candidates import (
    CandidateContext,
    CandidateSpec,
    LocalCandidateProvider,
    ProfileTwinCandidateProvider,
    generate_candidates,
    normalize_profile_twin_neighbors,
    region_counts_from_db,
    region_counts_from_frame,
    validate_candidate,
)


def test_local_provider_generates_baseline_without_profile_dependency():
    context = CandidateContext(
        admin_level="beopjungri",
        anchor_region_codes=("4311132026",),
    )
    candidates = LocalCandidateProvider(["gross_area", "region_leaf"]).generate(context)
    assert len(candidates) == 1
    assert candidates[0].candidate_id == "local"
    assert candidates[0].metadata["pooling"] is False


def test_profile_candidate_requires_native_snapshot():
    context = CandidateContext(
        admin_level="eupmyeondong",
        anchor_region_codes=("43111320",),
        profile_version="v2.1-national",
        profile_window_years=3,
    )
    candidate = CandidateSpec(
        candidate_id="twin-1",
        provider_id="profile_twin",
        region_codes=("43111320", "43111321"),
        variables=("gross_area",),
        metadata={
            "admin_level": "eupmyeondong",
            "algorithm_version": 21,
            "profile_version": "v2.1-national",
            "profile_window_years": 3,
        },
    )
    result = validate_candidate(
        candidate,
        context=context,
        region_counts={"43111320": 20, "43111321": 18},
    )
    assert result.accepted is True


def test_profile_candidate_rejects_old_twin_algorithm():
    context = CandidateContext(
        admin_level="eupmyeondong",
        anchor_region_codes=("43111320",),
        profile_version="v2.1-national",
    )
    candidate = CandidateSpec(
        candidate_id="old-twin",
        provider_id="profile_twin",
        region_codes=("43111320", "43111321"),
        variables=("gross_area",),
        metadata={"algorithm_version": 8},
    )
    result = validate_candidate(
        candidate,
        context=context,
        region_counts={"43111320": 20, "43111321": 18},
    )
    assert result.accepted is False
    assert "v21" in " ".join(result.reasons)


def test_profile_twin_provider_builds_candidates_without_pooling():
    context = CandidateContext(
        admin_level="beopjungri",
        anchor_region_codes=("4311132026",),
        profile_version="v2.1-national",
        profile_as_of_month="2026-06-01",
        profile_window_years=3,
    )
    provider = ProfileTwinCandidateProvider(
        [
            {"twin_region_code": "4311132033", "similarity_score": 92.0},
            {"twin_region_code": "4311132044", "similarity_score": 88.0},
        ],
        ["gross_area"],
    )
    candidates = provider.generate(context)
    assert [c.region_codes for c in candidates] == [
        ("4311132026", "4311132033"),
        ("4311132026", "4311132033", "4311132044"),
    ]
    assert all(c.metadata["pooling"] is False for c in candidates)
    assert all(c.metadata["validated"] is False for c in candidates)


def test_candidate_factory_keeps_rejected_candidates_out_of_accepted_list():
    context = CandidateContext(
        admin_level="eupmyeondong",
        anchor_region_codes=("43111320",),
        profile_version="v2.1-national",
    )
    result = generate_candidates(
        [
            LocalCandidateProvider(["gross_area"]),
            ProfileTwinCandidateProvider(
                [{"twin_region_code": "43111321"}],
                ["gross_area"],
                algorithm_version=8,
            ),
        ],
        context=context,
        region_counts={"43111320": 20, "43111321": 20},
    )
    assert [candidate.provider_id for candidate in result.accepted] == ["local"]
    assert len(result.validations) == 2
    assert result.validations[1].accepted is False


def test_profile_adapter_accepts_only_profile_native_v21():
    payload = {
        "algorithm_version": 21,
        "profile_version": "v2.1-national",
        "as_of_month": "2026-06-01",
        "window_years": 3,
        "neighbors": [
            {
                "twin_beopjungri_code": "4311132033",
                "similarity_score": 92.0,
            }
        ],
    }
    rows = normalize_profile_twin_neighbors(payload, admin_level="beopjungri")
    assert rows[0]["region_code"] == "4311132033"
    assert normalize_profile_twin_neighbors(
        {**payload, "algorithm_version": 8},
        admin_level="beopjungri",
    ) == []


def test_region_counts_use_built_canonical_column():
    import pandas as pd

    df = pd.DataFrame(
        {
            "eupmyeondong_code": ["43111320", "43111320", "43111321", None],
            "price": [1, 2, 3, 4],
        }
    )
    assert region_counts_from_frame(df, admin_level="eupmyeondong") == {
        "43111320": 2,
        "43111321": 1,
    }


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeConn:
    """region_counts_from_db가 anchor 표본이 아니라 후보 지역 자체를 조회하는지 확인."""

    def __init__(self, rows):
        self._rows = rows
        self.last_params: dict[str, object] | None = None

    def execute(self, _stmt, params):
        self.last_params = params
        return _FakeResult(self._rows)


def test_region_counts_from_db_queries_candidate_codes_not_anchor_sample():
    # anchor(43111320)는 selection 표본에 있지만 twin(43111321)은 anchor 조회 범위 밖 —
    # region_counts_from_frame(ctx.df)로는 twin이 항상 0건으로 잡히는 결함을 재현/회귀 방지.
    conn = _FakeConn(
        rows=[{"code": "43111320", "n": 12}, {"code": "43111321", "n": 7}]
    )
    counts = region_counts_from_db(
        conn,
        admin_level="eupmyeondong",
        region_codes=("43111320", "43111321"),
        asset_type="commercial",
    )
    assert counts == {"43111320": 12, "43111321": 7}
    assert conn.last_params is not None
    assert set(conn.last_params["codes"]) == {"43111320", "43111321"}


def test_region_counts_from_db_returns_empty_without_codes():
    conn = _FakeConn(rows=[])
    assert region_counts_from_db(
        conn, admin_level="eupmyeondong", region_codes=(), asset_type="commercial"
    ) == {}


def test_candidate_with_missing_built_region_is_rejected():
    context = CandidateContext(
        admin_level="eupmyeondong",
        anchor_region_codes=("43111320",),
        profile_version="v2.1-national",
    )
    candidate = CandidateSpec(
        candidate_id="twin-missing",
        provider_id="profile_twin",
        region_codes=("43111320", "43111399"),
        variables=("gross_area",),
        metadata={
            "admin_level": "eupmyeondong",
            "algorithm_version": 21,
            "profile_version": "v2.1-national",
        },
    )
    result = validate_candidate(
        candidate,
        context=context,
        region_counts={"43111320": 20, "43111399": 0},
    )
    assert result.accepted is False
    assert "원장" in " ".join(result.reasons)
