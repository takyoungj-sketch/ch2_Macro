"""Versioned source identity policy; leaves the frozen v2.1 implementation intact."""
import re

VERSION = 'cheongju-source-identity-v2.2'
DISTRICTS = {'43111', '43112', '43113', '43114'}


def identify(fields):
    if not isinstance(fields, (list, tuple)) or len(fields) != 5 or any(not isinstance(v, str) for v in fields):
        raise ValueError('Five original string identity fields required')
    sg, bd, gb, bun, ji = [v.strip() for v in fields]
    result = {'rule_version': VERSION, 'raw_fields': list(fields), 'pnu': None,
              'land_type': {'0': 'land', '1': 'mountain', '2': 'block'}.get(gb, 'unknown')}
    if sg not in DISTRICTS:
        status = 'invalid_district'
    elif re.fullmatch(r'[0-9]{1,5}', bd) and int(bd) > 0:
        bjd = sg + bd.zfill(5); status = None
    elif re.fullmatch(r'[0-9]{10}', bd) and bd.startswith(sg) and int(bd[5:]) > 0:
        bjd = bd; status = None
    else:
        status = 'invalid_bjd'
    if status is None:
        if gb == '2': status = 'block_without_canonical_pnu'
        elif gb not in ('0', '1'): status = 'unknown_land_type'
        elif not re.fullmatch(r'[0-9]{1,4}', bun): status = 'invalid_main_lot'
        elif int(bun) == 0: status = 'noncanonical_zero_main_lot'
        elif not re.fullmatch(r'[0-9]{1,4}', ji): status = 'invalid_sub_lot'
        else:
            status = 'canonical_address'
            result['pnu'] = bjd + ('2' if gb == '1' else '1') + bun.zfill(4) + ji.zfill(4)
    result['status'] = status
    return result
