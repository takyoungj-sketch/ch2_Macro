"""COL2-002 보완 화면용 로컬 응답. 운영 DB에 접속하지 않는다."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).with_name("col2-002-supplement.json")
DATA = json.loads(ROOT.read_text(encoding="utf-8"))


def _addr2(query: dict[str, list[str]]) -> str:
    return (query.get("addr2") or [""])[0]


def _line(item: dict) -> dict:
    geometry = item.get("geometry")
    if geometry is None:
        geometry = {"type": "LineString", "coordinates": item["coordinates"]}
    point = geometry["coordinates"][0]
    if geometry["type"] == "MultiLineString":
        point = point[0]
    return {
        "cluster_key": item["cluster_key"],
        "label_point": point,
        "geometry": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"cluster_key": item["cluster_key"], "asset_type": item["asset_type"]},
                "geometry": geometry,
            }],
        },
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        addr2 = _addr2(query)
        if path == "/api/collective2/access":
            self._send(200, {"ok": True})
            return
        if path == "/api/auth/status":
            self._send(200, {"logged_in": False})
            return
        if path == "/api/map/config":
            self._send(200, {"vworld_configured": True, "neighbor_graph_ready": False})
            return
        if path == "/api/map/boundaries":
            self._send(200, {
                "level": (query.get("level") or ["eupmyeondong"])[0],
                "selected": query.get("selected") or [],
                "feature_collection": DATA["boundaries"],
            })
            return
        if path == "/api/map/neighbors":
            self._send(200, {
                "level": (query.get("level") or ["eupmyeondong"])[0],
                "codes": query.get("codes") or [],
                "neighbors_by_code": {},
                "neighbor_codes": [],
                "graph_ready": False,
                "edge_count": 0,
            })
            return
        if path in ("/api/collective/regions/resolve-codes", "/api/collective/commercial/regions/resolve-codes"):
            self._send(200, DATA["resolve"])
            return
        if path == "/api/collective/regions/addr1":
            self._send(200, DATA["addr1"])
            return
        if path in ("/api/collective/regions/addr2", "/api/collective/commercial/regions/addr2"):
            self._send(200, DATA["addr2"].get((query.get("addr1") or [""])[0], []))
            return
        if path == "/api/collective/regions/structure":
            self._send(200, DATA["residential_structure"].get(addr2, DATA["residential_structure"]["같은구"]))
            return
        if path == "/api/collective/commercial/regions/structure":
            self._send(200, DATA["commercial_structure"].get(addr2, DATA["commercial_structure"]["같은구"]))
            return
        if path in ("/api/collective/regions/addr3", "/api/collective/regions/leaf"):
            self._send(200, DATA["residential_regions"].get(addr2, []))
            return
        if path in ("/api/collective/commercial/regions/addr3", "/api/collective/commercial/regions/leaf"):
            self._send(200, DATA["commercial_regions"].get(addr2, []))
            return
        if path == "/api/collective/meta/filters":
            self._send(200, {"asset_types": ["apartment"], "contract_years": [2024], "addr1_list": DATA["addr1"]})
            return
        if path == "/api/collective/buildings":
            rows = DATA["buildings"]
            self._send(200, {"total": len(rows), "items": rows, "data_source": "live", "window_years": 5, "stats_as_of_label": "2026-10"})
            return
        if path == "/api/collective/commercial/clusters":
            rows = [row for row in DATA["clusters"] if not addr2 or row["addr2"] == addr2]
            self._send(200, {
                "total": len(rows), "items": rows, "data_source": "live", "window_years": 5,
                "stats_as_of_label": "2026-10", "period_start": "2021-11-01", "period_end": "2026-10-31",
            })
            return
        self._send(200, {"items": [], "total": 0, "points": [], "series": []})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        if parsed.path == "/api/collective/commercial/roads/viewport-lines":
            body = json.loads(raw.decode("utf-8") or "{}")
            wanted = set(body.get("cluster_keys") or [])
            lines = [_line(item) for item in DATA["viewport_lines"] if item["cluster_key"] in wanted]
            self._send(200, {"lines": lines, "truncated": False, "unavailable": 0})
            return
        self._send(200, {"items": [], "total": 0, "ok": True, "lines": []})

    def log_message(self, fmt: str, *args) -> None:
        return


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
