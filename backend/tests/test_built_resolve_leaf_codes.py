from app.built.resolve_codes import keep_emd_codes_matching_leaves


def test_keep_emd_drops_mislabelled_gangnae():
    codes, labels = keep_emd_codes_matching_leaves(
        ["43113114", "43113310"],
        {"43113114": "복대동", "43113310": "강내면"},
        ["복대동"],
    )
    assert codes == ["43113114"]
    assert labels == {"43113114": "복대동"}


def test_keep_emd_keeps_both_when_both_selected():
    codes, labels = keep_emd_codes_matching_leaves(
        ["43113114", "43113310"],
        {"43113114": "복대동", "43113310": "강내면"},
        ["복대동", "강내면"],
    )
    assert codes == ["43113114", "43113310"]
    assert labels == {"43113114": "복대동", "43113310": "강내면"}


def test_keep_emd_leaves_sejong_style_unmatched_labels():
    codes, labels = keep_emd_codes_matching_leaves(
        ["36110320"],
        {"36110320": "조치원읍"},
        ["신안리"],
    )
    assert codes == ["36110320"]
    assert labels == {"36110320": "조치원읍"}
