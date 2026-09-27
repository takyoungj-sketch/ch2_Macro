"""토지 쌍둥이 선정. DB 없음."""

import numpy as np

from app.land_lab.land_twin import (
    _assign_blend,
    basket_amounts,
    basket_price_distance,
    basket_share,
    basket_structure_distance,
    js_divergence_base2,
    price_shape,
    rank_basket_twins,
    rank_land_twins,
    share_vector,
)


def test_js_is_zero_for_the_same_shares():
    p = np.array([0.5, 0.3, 0.2])
    assert js_divergence_base2(p, p) == 0.0


def test_same_shares_match_even_when_counts_differ():
    vocab = ["대", "전", "답"]
    a = share_vector({"대": 1000, "전": 600, "답": 400}, vocab)
    b = share_vector({"대": 200, "전": 120, "답": 80}, vocab)
    assert js_divergence_base2(a, b) < 1e-12


def test_doubled_prices_have_zero_shape_distance():
    anchor = {"대": (40, 50.0), "전": (40, 30.0), "답": (40, 20.0), "임": (40, 10.0), "도": (40, 8.0)}
    other = {"대": (40, 100.0), "전": (40, 60.0), "답": (40, 40.0), "임": (40, 20.0), "도": (40, 16.0)}
    shaped = price_shape(anchor, other)
    assert shaped is not None
    distance, level_gap, names = shaped
    assert distance < 1e-9
    assert abs(level_gap - np.log(2)) < 1e-9
    assert len(names) == 5


def test_thin_jimok_stays_in_shares_and_out_of_price():
    anchor = {
        "대": (100, 50.0),
        "전": (80, 30.0),
        "답": (40, 20.0),
        "임": (20, 10.0),
        "도": (20, 8.0),
        "장": (3, 99.0),
    }
    other = {
        "대": (50, 55.0),
        "전": (40, 28.0),
        "답": (20, 22.0),
        "임": (16, 11.0),
        "도": (16, 9.0),
        "장": (2, 1.0),
    }
    shaped = price_shape(anchor, other)
    assert shaped is not None
    assert "장" not in shaped[2]
    vocab = ["대", "전", "답", "임", "도", "장"]
    share = share_vector({k: v[0] for k, v in anchor.items()}, vocab)
    assert share[vocab.index("장")] > 0


def test_price_rank_is_inside_structure_top_and_skips_thin_overlap():
    vocab = ["대", "전", "답", "임", "도"]
    anchor = {name: (30, 10.0 * (i + 1)) for i, name in enumerate(vocab)}
    profiles = {"A": anchor}
    # 구성은 같고 가격 형태만 다른 후보 6곳. 마지막은 공통 지목이 4개라 가격 순위에서 빠진다.
    for i, code in enumerate(["B", "C", "D", "E", "F"]):
        profiles[code] = {name: (30, 10.0 * (i + 1) * (j + 1)) for j, name in enumerate(vocab)}
    thin = {name: (30, 10.0) for name in vocab[:4]}
    thin["도"] = (3, 10.0)
    profiles["G"] = thin
    # G의 비중을 앵커와 가깝게 두되 가격 비교 지목은 4개.
    rows = rank_land_twins("A", profiles, vocab)
    assert [row["region_code"] for row in rows if row["structure_rank"] <= 20]
    assert all(row["region_code"] != "A" for row in rows)
    priced = [row for row in rows if row["price_rank"] is not None]
    assert len(priced) == 5
    assert "G" not in {row["region_code"] for row in priced}
    by_price = sorted(priced, key=lambda row: row["price_rank"])
    assert [row["price_rank"] for row in by_price] == [1, 2, 3, 4, 5]
    distances = [row["price_distance"] for row in by_price]
    assert distances == sorted(distances)


def test_b_and_c_keep_structure_when_price_alone_would_promote_a_mismatch():
    rows = [
        {
            "region_code": "NEAR",
            "js": 0.01,
            "price_distance": 0.20,
            "zone_js": 0.02,
            "structure_rank": 1,
        },
        {
            "region_code": "MID",
            "js": 0.02,
            "price_distance": 0.05,
            "zone_js": 0.05,
            "structure_rank": 2,
        },
        {
            "region_code": "CHEAP",
            "js": 0.05,
            "price_distance": 0.02,
            "zone_js": 0.40,
            "structure_rank": 3,
        },
    ]
    _assign_blend(rows, ["js", "price_distance"], "rank_b", "score_b")
    _assign_blend(rows, ["js", "zone_js", "price_distance"], "rank_c", "score_c")
    by_b = {row["region_code"]: row["rank_b"] for row in rows}
    by_c = {row["region_code"]: row["rank_c"] for row in rows}
    assert by_b["MID"] == 1
    assert by_b["CHEAP"] > by_b["MID"]
    assert by_c["CHEAP"] == 3
    assert by_c["MID"] < by_c["NEAR"]


def test_zone_mix_changes_c_when_jimok_and_price_match():
    vocab = ["대", "전", "답", "임", "도"]
    anchor = {name: (40, 10.0 * (i + 1)) for i, name in enumerate(vocab)}
    profiles = {"A": anchor, "MATCH": dict(anchor), "SKEW": dict(anchor)}
    zones = {
        "A": {"자녹": 100, "계관": 80, "농림": 60, "보전": 40},
        "MATCH": {"자녹": 50, "계관": 40, "농림": 30, "보전": 20},
        "SKEW": {"자녹": 200, "계관": 10, "농림": 5, "보전": 5},
    }
    rows = rank_land_twins("A", profiles, vocab, zone_profiles=zones, zone_vocab=list(zones["A"]))
    by_code = {row["region_code"]: row for row in rows}
    assert by_code["MATCH"]["zone_js"] < 1e-9
    assert by_code["SKEW"]["zone_js"] > by_code["MATCH"]["zone_js"]
    assert by_code["MATCH"]["rank_c"] < by_code["SKEW"]["rank_c"]


def test_d_ranks_cell_shape_and_skips_fewer_than_five_cells():
    vocab = ["대", "전", "답", "임", "도"]
    anchor = {name: (40, 10.0 * (i + 1)) for i, name in enumerate(vocab)}
    profiles = {"A": anchor, "NEAR": dict(anchor), "FAR": dict(anchor), "THIN": dict(anchor)}
    zones = {code: {"자녹": 100, "농림": 50} for code in profiles}
    base = [10.0, 20.0, 30.0, 40.0, 50.0]
    keys = ["자녹 대", "자녹 전", "자녹 답", "농림 대", "농림 전"]

    def cells(meds: list[float], n_keep: int = 5) -> dict[str, tuple[int, float]]:
        return {key: (20, med) for key, med in list(zip(keys, meds))[:n_keep]}

    rows = rank_land_twins(
        "A",
        profiles,
        vocab,
        zone_profiles=zones,
        zone_vocab=["자녹", "농림"],
        cell_profiles={
            "A": cells(base),
            "NEAR": cells([11.0, 21.0, 31.0, 42.0, 52.0]),
            "FAR": cells([50.0, 10.0, 40.0, 15.0, 80.0]),
            "THIN": cells(base, n_keep=4),
        },
    )
    by_code = {row["region_code"]: row for row in rows}
    assert by_code["THIN"]["cell_distance"] is None
    assert by_code["THIN"]["rank_d"] is None
    assert len(by_code["NEAR"]["shared_cells"]) == 5
    assert by_code["NEAR"]["rank_d"] < by_code["FAR"]["rank_d"]


def _basket(counts: list[int], medians: list[float]) -> dict[str, tuple[int, float]]:
    from app.land_lab.land_twin import BASKET

    cells = {}
    for (zone, cat), count, median in zip(BASKET, counts, medians):
        if count > 0 and median > 0:
            cells[f"{zone} {cat}"] = (count, median)
    return cells


def test_basket_scale_does_not_change_composition():
    counts = [100, 80, 60, 50, 40, 30, 20, 20, 16, 16]
    medians = [100.0, 80, 40, 50, 30, 20, 25, 90, 200, 15]
    left_n, left_m, left_t = basket_amounts(_basket(counts, medians))
    right_n, right_m, right_t = basket_amounts(_basket([n * 2 for n in counts], medians))
    assert basket_structure_distance(basket_share(left_t), basket_share(right_t)) < 1e-9
    distance, shared = basket_price_distance(
        basket_share(left_t), basket_share(right_t), left_m, right_m, left_n, right_n
    )
    assert shared == 10
    assert distance < 1e-9


def test_basket_price_moves_when_medians_double_and_shares_stay():
    counts = [40] * 10
    medians = [10.0, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    left_n, left_m, left_t = basket_amounts(_basket(counts, medians))
    right_n, right_m, right_t = basket_amounts(_basket(counts, [m * 2 for m in medians]))
    left_p = basket_share(left_t)
    right_p = basket_share(right_t)
    assert basket_structure_distance(left_p, right_p) < 1e-9
    distance, shared = basket_price_distance(left_p, right_p, left_m, right_m, left_n, right_n)
    assert shared == 10
    assert abs(distance - np.log(2)) < 1e-9


def test_missing_basket_cell_is_zero_share():
    counts = [40] * 10
    medians = [10.0] * 10
    dropped = counts.copy()
    dropped[0] = 0
    right = basket_share(basket_amounts(_basket(dropped, medians))[2])
    assert right[0] == 0.0
    left = basket_share(basket_amounts(_basket(counts, medians))[2])
    assert basket_structure_distance(left, right) > 0


def test_basket_price_is_blank_below_five_cells():
    counts = [40, 40, 40, 40, 3, 3, 3, 3, 3, 3]
    medians = [10.0] * 10
    n, m, t = basket_amounts(_basket(counts, medians))
    share = basket_share(t)
    assert basket_price_distance(share, share, m, m, n, n) is None


def test_basket_rank_follows_composition_not_scale_or_price():
    counts = [40] * 10
    medians = [20.0] * 10
    cells = {
        "A": _basket(counts, medians),
        "HALF": _basket([n * 2 for n in counts], medians),
        "DEAR": _basket(counts, [m * 3 for m in medians]),
        "SKEW": _basket([80, 40, 40, 40, 40, 40, 40, 40, 20, 20], medians),
    }
    _, rows = rank_basket_twins(
        "A",
        cells,
        {"A": "기준", "HALF": "절반", "DEAR": "비싼", "SKEW": "기울"},
    )
    by_code = {row["region_code"]: row for row in rows}
    assert by_code["HALF"]["structure_distance"] < 1e-9
    assert abs(by_code["HALF"]["scale_ratio"] - 2) < 1e-9
    assert by_code["DEAR"]["structure_distance"] < 1e-9
    assert abs(by_code["DEAR"]["price_distance"] - np.log(3)) < 1e-6
    assert by_code["SKEW"]["rank"] == 3
    assert by_code["HALF"]["price_distance"] < 1e-9


def test_basket_price_weight_follows_share():
    share = np.array([0.91] + [0.01] * 9)
    med_a = np.full(10, 10.0)
    med_b = np.array([20.0] + [1000.0] * 9)
    counts = np.full(10, 40.0)
    distance, shared = basket_price_distance(share, share, med_a, med_b, counts, counts)
    assert shared == 10
    assert distance < 1.2
    assert distance > np.log(2)
