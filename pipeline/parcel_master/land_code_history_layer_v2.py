"""LAND_CODE_HISTORY_LAYER_V2 (shadow only, not used by the product path).

V1 (``land_code_history_layer.resolve_beopjungri``) switches to the reissued
legal-dong code on the official effective date. The national trait ledger can
lag that date. On 2026-07-01 Gwangju and Jeonnam became sido ``12``, but every
plate up to 2026-07-20 still carries the old codes 29/46. Every V1 lookup for a
contract after the effective date then finds no parcel.

V2 keeps the V1 1:1 name pairs and changes one thing. While the ledger holds no
parcel under the new sido prefix, the previous code stays in use after the
effective date. Pairs that the Honam bridge does not confirm are held: the
building ledger did not see the same building move between the two codes 1:1.
A held pair keeps the new code and so stays unmatched, which is what V1 does.

When the ledger starts loading ``12`` PNUs, the prefix is no longer missing and
V2 falls back to V1. See ``docs/lab/LAND_LINK_V2_ROLLOUT_PLAN_20261110.md`` for the
PNU split this causes.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

RULE_VERSION_V2 = "LAND_CODE_HISTORY_LAYER_V2+LAND_LINK_RULE_V1"
FAR_FUTURE = "9999-12-31"
HONAM_BRIDGE = Path(r"C:\CH2\parcel_master\honam_code_bridge_v1.sqlite")
CONFIRMED = frozenset({"observed_and_name"})


def missing_prefixes(pairs: dict, ledger) -> list[str]:
    found = []
    for prefix in sorted({current[:2] for current in pairs}):
        upper = str(int(prefix) + 1).zfill(2)
        hit = ledger.execute(
            "SELECT 1 FROM parcel_observation WHERE pnu >= ? AND pnu < ? LIMIT 1", (prefix, upper)
        ).fetchone()
        if hit is None:
            found.append(prefix)
    return found


def bridge_evidence(path: Path = HONAM_BRIDGE) -> dict[str, tuple[str | None, str]]:
    if not path.exists():
        return {}
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        return {new: (old, evidence) for new, old, evidence in db.execute("SELECT new_bjd, old_bjd, evidence FROM bridge")}


def ledger_generation_pairs(pairs: dict, ledger, bridge: dict | None = None) -> tuple[dict, dict]:
    """Return (V2 pairs, summary). ``pairs`` is the V1 map current -> (previous, effective)."""
    missing = missing_prefixes(pairs, ledger)
    bridge = bridge_evidence() if bridge is None else bridge
    adjusted = {}
    held = 0
    kept = 0
    for current, (previous, effective) in pairs.items():
        if current[:2] not in missing:
            adjusted[current] = (previous, effective)
            continue
        old, evidence = bridge.get(current, (None, "not_in_bridge"))
        if evidence in CONFIRMED and old == previous:
            adjusted[current] = (previous, FAR_FUTURE)
            kept += 1
        else:
            adjusted[current] = (previous, effective)
            held += 1
    return adjusted, {"missing_prefixes": missing, "extended_pairs": kept, "held_pairs": held}
