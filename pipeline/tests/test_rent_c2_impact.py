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


def test_availability_lists_missing_null_and_gate_state():
    from pipeline.rent.rent_c2_impact import availability_changes

    before = [
        {"addr1": "서울", "addr2": "강남구", "addr3": "", "asset_type": "apartment",
         "window_years": 5, "r_selected": None, "gate_passed": None},
        {"addr1": "서울", "addr2": "송파구", "addr3": "", "asset_type": "officetel",
         "window_years": 3, "r_selected": 1.0, "gate_passed": True},
    ]
    after = [
        {"addr1": "서울", "addr2": "강남구", "addr3": "", "asset_type": "apartment",
         "window_years": 5, "r_selected": 2.0, "gate_passed": False},
        {"addr1": "부산", "addr2": "해운대구", "addr3": "", "asset_type": "rowhouse",
         "window_years": 7, "r_selected": 3.0, "gate_passed": True},
    ]
    changes = availability_changes(before, after)
    reasons = {item["region"]: item["reason"] for item in changes}
    assert reasons["서울 강남구"] == "r_selected,gate_passed"
    assert reasons["서울 송파구"] == "한쪽"
    assert reasons["부산 해운대구"] == "한쪽"
    assert rate_alarms(before, after) == []
