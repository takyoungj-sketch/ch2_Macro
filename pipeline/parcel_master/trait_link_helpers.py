"""Deterministic, conservative helpers for the offline trait-only pilot."""
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def code(value):
    value = str(value).strip()
    return str(int(value)) if value.isdigit() and int(value) > 0 else 'UNKNOWN'


def area_key(value):
    try:
        number = Decimal(str(value))
        return str(number.quantize(Decimal('.1'), rounding=ROUND_HALF_UP)) if number.is_finite() and number > 0 else None
    except (InvalidOperation, ValueError):
        return None


def lot_matches(mask, pnu, lot):
    mask = str(mask or '').strip()
    mountain = mask.startswith('산')
    pattern = mask.removeprefix('산').strip()
    if not re.fullmatch(r'[0-9*]+', pattern) or len(pnu) != 19:
        return False
    main = lot.removeprefix('산').strip().split('-')[0]
    return (pnu[10] == '2') == mountain and bool(re.fullmatch(pattern.replace('*', '[0-9]'), main))


def unique_rows(rows):
    """Deduplicate exact attribute rows, fail on conflicting same-PNU rows."""
    seen = {}
    for row in rows:
        pnu = row['pnu']
        if pnu in seen and seen[pnu] != row:
            raise ValueError(f'Conflicting duplicate PNU: {pnu}')
        seen[pnu] = row
    return seen
