from app.qa_audit.built_enriched import (
    _qualify_pred,
    compare_enrichment,
    normalize_asset_type,
)


def test_normalize_built_asset_aliases():
    assert normalize_asset_type("상가") == "commercial"
    assert normalize_asset_type("단독다가구") == "detached"


def test_qualify_pred_prefixes_alias():
    raw = "(eupmyeondong_code = :eup_code OR LEFT(btrim(COALESCE(beopjungri_code::text, '')), 8) = :eup_code)"
    out = _qualify_pred(raw, "t")
    assert "t.eupmyeondong_code" in out
    assert "t.beopjungri_code" in out
    assert ":eup_code" in out


def _base(*, n_l1=10, n_l3=10, n_enr=7, n_mart=7, coarse=0, bad_tier=0, orphan=0):
    return compare_enrichment(
        {"n": n_l1},
        {
            "n_enriched": n_enr,
            "n_coarse_pollution": coarse,
            "n_invalid_tier": bad_tier,
            "n_orphan": orphan,
        },
        {"n": n_l3, "n_enriched": n_enr, "available": True},
        {"n": n_mart, "missing": False},
    )


def test_compare_pass_when_quality_clean():
    d = _base()
    assert d["verdict"] == "PASS"
    by_id = {c["id"]: c for c in d["checks"]}
    assert by_id["coarse_zone"]["grade"] == "PASS"
    assert by_id["coverage"]["grade"] == "PASS"


def test_compare_block_on_coarse_pollution():
    d = _base(coarse=1)
    assert d["verdict"] == "BLOCK"
    by_id = {c["id"]: c for c in d["checks"]}
    assert by_id["coarse_zone"]["grade"] == "ERROR"


def test_compare_review_when_no_enrichment():
    d = _base(n_enr=0, n_mart=0)
    assert d["verdict"] == "REVIEW"
    by_id = {c["id"]: c for c in d["checks"]}
    assert by_id["coverage"]["grade"] == "REVIEW"


def test_compare_skip_empty_region():
    d = _base(n_l1=0, n_l3=0, n_enr=0, n_mart=0)
    assert d["verdict"] == "SKIP"
