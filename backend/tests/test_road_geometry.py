"""도로명 정규화·매칭 (VWorld LT_L_SPRD 속성)."""

import pytest
from shapely.geometry import Point, shape

from app.collective_commercial import road_geometry
from app.collective_commercial.road_geometry import (
    clip_linestring_to_box,
    filter_road_features,
    intersect_boxes,
    normalize_road_name,
    resolve_search_box,
    score_road_name,
)


def test_normalize_strips_spaces():
    assert normalize_road_name(" 1 순환로 ") == "1순환로"


def test_score_exact_only():
    assert score_road_name("1순환로", "1순환로") == 100
    assert score_road_name("1순환로123", "1순환로") == 0
    assert score_road_name("중앙로2길", "중앙로") == 0
    assert score_road_name("흥덕로", "1순환로") == 0


def test_filter_keeps_exact_over_partial():
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"rn": "중앙로2길"},
                "geometry": {"type": "LineString", "coordinates": [[127.0, 36.0], [127.1, 36.1]]},
            },
            {
                "type": "Feature",
                "properties": {"rn": "중앙로"},
                "geometry": {"type": "LineString", "coordinates": [[127.2, 36.2], [127.3, 36.3]]},
            },
        ],
    }
    out = filter_road_features(fc, road_name="중앙로")
    names = [f["properties"]["rn"] for f in out["features"]]
    assert names == ["중앙로"]


def test_filter_skips_points():
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"rn": "1순환로"},
                "geometry": {"type": "Point", "coordinates": [127.0, 36.0]},
            }
        ],
    }
    assert filter_road_features(fc, road_name="1순환로")["features"] == []


def test_intersect_boxes():
    hit = intersect_boxes((0.0, 0.0, 2.0, 2.0), (1.0, 1.0, 3.0, 3.0))
    assert hit == (1.0, 1.0, 2.0, 2.0)
    assert intersect_boxes((0.0, 0.0, 1.0, 1.0), (2.0, 2.0, 3.0, 3.0)) is None


def test_resolve_prefers_intersection_then_point():
    box = resolve_search_box(
        west=127.0,
        south=36.0,
        east=128.0,
        north=37.0,
        longitude=127.5,
        latitude=36.5,
    )
    assert box is not None
    west, south, east, north = box
    assert west == 127.5 - 0.012
    assert east == 127.5 + 0.012
    # 행정 bbox와 점 버퍼가 안 겹치면 점 버퍼
    fallback = resolve_search_box(
        west=120.0,
        south=30.0,
        east=121.0,
        north=31.0,
        longitude=127.5,
        latitude=36.5,
    )
    assert fallback is not None
    assert fallback[0] == 127.5 - 0.012


def test_clip_linestring_keeps_interior():
    box = (0.0, 0.0, 1.0, 1.0)
    parts = clip_linestring_to_box([[-1.0, 0.5], [0.5, 0.5], [2.0, 0.5]], box)
    assert len(parts) == 1
    xs = [p[0] for p in parts[0]]
    assert min(xs) >= 0.0 - 1e-9
    assert max(xs) <= 1.0 + 1e-9
    assert len(parts[0]) >= 2


def test_admin_road_line_clips_to_polygon_and_places_label_on_line(monkeypatch):
    boundary = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [3, 0], [3, 1], [1, 1], [1, 3], [0, 3], [0, 0]]],
    }
    monkeypatch.setattr(road_geometry, "fetch_named_layer_features", lambda **_: {
        "features": [{"geometry": boundary, "properties": {"emd_cd": "43150123"}}],
    })
    monkeypatch.setattr(road_geometry, "fetch_road_line_collection", lambda **_: {
        "features": [
            {"geometry": {"type": "LineString", "coordinates": [[0, 2], [3, 2]]}, "properties": {"rn_cd": "1"}},
            {"geometry": {"type": "LineString", "coordinates": [[2, 2], [3, 2]]}, "properties": {"rn_cd": "2"}},
        ],
    })
    lines, anchor = road_geometry.fetch_admin_road_line(
        api_key="", domain="", road_name="중앙로", admin_level="eupmyeondong", admin_code="43150123",
    )
    assert len(lines["features"]) == 1
    line = shape(lines["features"][0]["geometry"])
    assert shape(boundary).covers(line)
    assert anchor == (0.5, 2)
    assert line.covers(Point(anchor))


def test_admin_road_line_rejects_multiple_matching_road_codes(monkeypatch):
    boundary = {"type": "Polygon", "coordinates": [[[0, 0], [3, 0], [3, 3], [0, 3], [0, 0]]]}
    monkeypatch.setattr(road_geometry, "fetch_named_layer_features", lambda **_: {
        "features": [{"geometry": boundary, "properties": {"sig_cd": "43150"}}],
    })
    monkeypatch.setattr(road_geometry, "fetch_road_line_collection", lambda **_: {
        "features": [
            {"geometry": {"type": "LineString", "coordinates": [[0, 1], [3, 1]]}, "properties": {"rn_cd": "1"}},
            {"geometry": {"type": "LineString", "coordinates": [[0, 2], [3, 2]]}, "properties": {"rn_cd": "2"}},
        ],
    })
    with pytest.raises(ValueError, match="ambiguous_road_name"):
        road_geometry.fetch_admin_road_line(
            api_key="", domain="", road_name="중앙로", admin_level="sigungu", admin_code="43150",
        )
