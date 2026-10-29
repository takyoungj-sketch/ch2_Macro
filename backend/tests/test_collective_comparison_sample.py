import numpy as np
import pandas as pd

from app.collective.regression.recommend import search_block_models


def test_candidates_with_different_missing_rows_share_sample_and_split():
    rng = np.random.default_rng(32)
    frame = pd.DataFrame(dict(transaction_id=np.arange(80), price=rng.uniform(100, 300, 80),
        area=rng.uniform(10, 80, 80), age=rng.uniform(1, 20, 80)))
    frame.loc[:9, "area"] = np.nan
    frame.loc[70:, "age"] = np.nan
    def build(blocks):
        return frame.price, frame[blocks]
    result = search_block_models(["area", "age"], build, observations=frame)
    assert result and all(r["n"] == 60 for r in result)
    assert all(r["comparison"]["sample_n"] == 60 for r in result)
    cv = [r for r in result if r["cv_mape"] is not None]
    assert cv
    assert len({r["comparison"]["evaluation_signature"] for r in cv}) == 1
    assert all(r["comparison"]["evaluation_n"] == 60 for r in cv)


def test_no_ranking_when_candidate_union_has_no_common_rows():
    frame = pd.DataFrame(dict(price=np.arange(20)+100., a=np.r_[np.arange(10), [np.nan]*10],
        b=np.r_[[np.nan]*10, np.arange(10)]))
    assert search_block_models(["a", "b"], lambda blocks: (frame.price, frame[blocks])) == []
