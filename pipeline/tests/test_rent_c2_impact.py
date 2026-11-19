"""영향표 경보. 0.5%p 이상만 남긴다."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pipeline.rent.rent_c2_impact import gate_flips, rate_alarms  # noqa: E402


def test_alarm_keeps_half_point_and_names_only():
    before = [{"addr1": "서울", "addr2": "강남구", "addr3": "", "asset_type": "apartment",
               "window_years": 5, "r_selected": 4.0, "gate_passed": True}]
    after = [{"addr1": "서울", "addr2": "강남구", "addr3": "", "asset_type": "apartment",
              "window_years": 5, "r_selected": 4.6, "gate_passed": False}]
    alarms = rate_alarms(before, after)
    assert len(alarms) == 1
    assert alarms[0]["region"] == "서울 강남구"
    assert alarms[0]["before"] == 4.0 and alarms[0]["after"] == 4.6
    assert "key" not in alarms[0]
    small = rate_alarms(before, [{**after[0], "r_selected": 4.4}])
    assert small == []
    flips = gate_flips(before, after)
    assert flips[0]["before"] is True and flips[0]["after"] is False
