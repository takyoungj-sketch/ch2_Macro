"""Identifier normalization in front of land link rule V1.

V1 itself is unchanged. A current legal-dong code is rewritten to the
previous code only when the pair is a proven 1:1 and the contract date
is before the effective date. Anything else is left as-is.
"""

from __future__ import annotations

GANGWON_EFFECTIVE = "2023-06-11"
JEONBUK_EFFECTIVE = "2024-01-18"
HONAM_EFFECTIVE = "2026-07-01"

PREFIX_GENERATIONS = (
    ("51", "42", GANGWON_EFFECTIVE),
    ("52", "45", JEONBUK_EFFECTIVE),
)


class AmbiguousCodeMap(ValueError):
    """The candidate map is not 1:1, so it must not be applied."""


def prefix_previous(current: str, old_sido: str) -> str:
    code = current.strip()
    if len(code) != 10 or len(old_sido) != 2:
        raise AmbiguousCodeMap(code)
    return old_sido + code[2:]


def add_pair(
    pairs: dict[str, tuple[str, str]],
    previous_owner: dict[str, str],
    current: str,
    previous: str,
    effective: str,
) -> None:
    current = current.strip()
    previous = previous.strip()
    if len(current) != 10 or len(previous) != 10 or current == previous or len(effective) != 10:
        raise AmbiguousCodeMap(current)
    if current in pairs or previous in previous_owner:
        raise AmbiguousCodeMap(current)
    pairs[current] = (previous, effective)
    previous_owner[previous] = current


def resolve_beopjungri(code: str, day: str, pairs: dict[str, tuple[str, str]]) -> tuple[str, str]:
    """Return the ledger legal-dong code and why it was or was not changed."""
    found = pairs.get(str(code).strip())
    if found is None:
        return str(code).strip(), "held"
    previous, effective = found
    if day < effective:
        return previous, "reissued_1to1"
    return str(code).strip(), "current_code"
