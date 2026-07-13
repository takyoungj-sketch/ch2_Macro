"""인접 거대 읍·면은 prune에서 유지되는지."""

from app.map.vworld_client import _prune_oversized_features


def _poly(code: str, west: float, south: float, east: float, north: float) -> dict:
    return {
        "type": "Feature",
        "properties": {"ch2_code": code},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [west, south],
                    [east, south],
                    [east, north],
                    [west, north],
                    [west, south],
                ]
            ],
        },
    }


def test_keeps_adjacent_oversized_myeon():
    # 작은 동 + 바로 서쪽에 맞닿은 거대 면 + 멀리 떨어진 거대 면
    small = _poly("4311311900", 127.40, 36.64, 127.41, 36.65)  # area ~0.0001
    near_big = _poly("4311325000", 127.30, 36.60, 127.40, 36.70)  # touches west edge
    far_big = _poly("4311326000", 126.0, 35.0, 126.5, 35.5)  # far, oversized
    fc = {
        "type": "FeatureCollection",
        "features": [small, near_big, far_big],
    }
    out = _prune_oversized_features(fc, selected=["4311311900"], max_ratio=10.0)
    codes = {f["properties"]["ch2_code"] for f in out["features"]}
    assert "4311311900" in codes
    assert "4311325000" in codes, "인접 거대 면은 유지"
    assert "4311326000" not in codes, "떨어진 거대 면은 제외"


def test_keeps_similar_sized_neighbors():
    a = _poly("A", 127.40, 36.64, 127.41, 36.65)
    b = _poly("B", 127.41, 36.64, 127.42, 36.65)
    fc = {"type": "FeatureCollection", "features": [a, b]}
    out = _prune_oversized_features(fc, selected=["A"], max_ratio=10.0)
    codes = {f["properties"]["ch2_code"] for f in out["features"]}
    assert codes == {"A", "B"}
