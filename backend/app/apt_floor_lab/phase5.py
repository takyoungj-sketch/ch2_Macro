"""실험 5 재실행 (backend에서): python -m app.apt_floor_lab.phase5"""
from __future__ import annotations

import json

from app.apt_floor_lab.fit import run_phase5


def main() -> None:
    payload = run_phase5()
    band = payload["joint_band"]["coefs"]
    height = payload["joint_height"]["coefs"]
    print(
        json.dumps(
            {
                "n": payload["joint_band"]["n"],
                "buildings": payload["joint_band"]["n_buildings"],
                "band_top_nonurban": band.get("d_top__nonurban"),
                "band_top_ge26": band.get("d_top__ge26"),
                "height_top_nonurban": height.get("d_top__nonurban"),
                "height_top_h": height.get("d_top__h"),
                "json": "docs/lab/apt_floor_utility_phase5.json",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
