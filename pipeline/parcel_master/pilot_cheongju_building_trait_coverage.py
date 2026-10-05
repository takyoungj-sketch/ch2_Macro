"""Local, read-only building-PNU / land-trait coverage; no transaction matching."""
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'pipeline'))
from parcel_master.db_utils import get_parcel_engine

OUT = ROOT / 'data/research/cheongju_ledger'
LAB = ROOT / 'docs/lab'
PAIRS = {2024: '2024-09', 2025: '2025-07', 2026: '2026-07'}
DISTRICTS = ('43111', '43112', '43113', '43114')


def valid_pnu(values):
    return values.str.fullmatch(r'\d{10}[12]\d{8}', na=False)


def source_frame(year, inventory):
    path = OUT / f'traits_{year}.csv.gz'
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != inventory[str(year)]['sha256']:
        raise ValueError('Trait input has changed; audit source before reusing')
    frame = pd.read_csv(path, dtype=str, keep_default_na=False,
                        usecols=['pnu', 'bjd', 'area', 'price', 'year', 'trait_asof'])
    if not frame.pnu.is_unique or not valid_pnu(frame.pnu).all():
        raise ValueError('Invalid or duplicate trait PNU')
    if not frame.pnu.str[:5].isin(DISTRICTS).all() or not frame.pnu.str[:10].eq(frame.bjd).all():
        raise ValueError('Trait region identity conflict')
    if len(frame) != inventory[str(year)]['parcels']:
        raise ValueError('Trait parcel inventory count mismatch')
    return frame, digest


def summarize(buildings, traits):
    keys = set(traits.pnu)
    valid = valid_pnu(buildings.pnu)
    bjd_ok = buildings.pnu.str[:10].eq(buildings.beopjungri_code)
    matched = valid & bjd_ok & buildings.pnu.isin(keys)
    identity_ok = valid & bjd_ok
    unmatched = identity_ok & ~buildings.pnu.isin(keys)
    b_pnus = set(buildings.loc[identity_ok, 'pnu'])
    m_pnus = set(buildings.loc[matched, 'pnu'])
    selected = traits[traits.pnu.isin(m_pnus)]
    positive = pd.to_numeric(selected.price, errors='coerce').gt(0)
    counts = buildings.loc[identity_ok].groupby('pnu').mgmt_pk.nunique()
    return {
        'building_rows': len(buildings),
        'building_rows_matched': int(matched.sum()),
        'building_row_match_pct': round(100 * matched.mean(), 3) if len(buildings) else None,
        'invalid_pnu_rows': int((~valid).sum()),
        'pnu_bjd_conflict_rows': int((valid & ~bjd_ok).sum()),
        'valid_identity_unmatched_rows': int(unmatched.sum()),
        'building_parcels': len(b_pnus), 'matched_parcels': len(m_pnus),
        'unmatched_parcels': len(b_pnus - keys),
        'parcel_match_pct': round(100 * len(m_pnus) / len(b_pnus), 3) if b_pnus else None,
        'matched_parcels_with_positive_price': int(positive.sum()),
        'matched_parcels_without_positive_price': int((~positive).sum()),
        'parcels_with_multiple_management_pks': int(counts.gt(1).sum()),
        'maximum_management_pks_on_one_parcel': int(counts.max()) if len(counts) else 0,
    }, matched, unmatched


def main():
    inventory = json.loads((LAB / 'cheongju_trait_links_20261004.json').read_text(encoding='utf-8'))['source_join']
    trait_data = {year: source_frame(year, inventory) for year in PAIRS}
    engine = get_parcel_engine()
    if engine.url.host not in ('localhost', '127.0.0.1', '::1'):
        raise RuntimeError('Local database required')
    building_data = {}
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
        conn.execute(text('SET TRANSACTION READ ONLY'))
        conn.execute(text("SET LOCAL statement_timeout = '60s'"))
        for year, snapshot in PAIRS.items():
            frame = pd.read_sql(text("""
                SELECT mgmt_pk,snapshot,pnu,beopjungri_code,ledger_kind,
                       main_purpose,gross_area,plat_area,title_land_area,approve_date
                FROM building WHERE sido_code='43' AND snapshot=:snapshot
                  AND substring(beopjungri_code,1,5) IN ('43111','43112','43113','43114')
                ORDER BY mgmt_pk
            """), conn, params={'snapshot': snapshot})
            if frame.empty or not frame.mgmt_pk.is_unique:
                raise ValueError('Missing or conflicting building snapshot')
            for name in ('mgmt_pk', 'snapshot', 'pnu', 'beopjungri_code', 'ledger_kind'):
                frame[name] = frame[name].fillna('').astype(str).str.strip()
            if set(frame.beopjungri_code.str[:5]) != set(DISTRICTS):
                raise ValueError('Incomplete building district coverage')
            building_data[year] = frame
    engine.dispose()
    report = {'run_date': date.today().isoformat(), 'version': 'building-trait-coverage-v1',
              'scope': 'Cheongju; exact PNU, same calendar year, different observation dates',
              'pairs': [], 'building_identity_transitions': [],
              'limitations': ['PNU equality is address-parcel coverage, not transaction or whole-site certification.',
                              'Same year does not mean simultaneous observation or legal effective date.',
                              'Trait-only parcels are not certified vacant land; title register may omit buildings.',
                              'Absent PNU does not establish deletion, subdivision, merger or erroneous address.',
                              'Management-PK changes do not by themselves establish building continuity.',
                              'Positive assessed prices do not establish regression eligibility or model improvement.']}
    queues = []
    for year, snapshot in PAIRS.items():
        buildings = building_data[year]
        traits, trait_sha = trait_data[year]
        path = OUT / f'building_identity_{snapshot}.csv.gz'
        buildings.to_csv(path, index=False, compression='gzip')
        metrics, matched, unmatched = summarize(buildings, traits)
        all_years = set().union(*(set(frame.pnu) for frame, _ in trait_data.values()))
        missing = set(buildings.loc[unmatched, 'pnu'])
        metrics['unmatched_parcels_seen_in_other_2024_2026_traits'] = len(missing & all_years)
        metrics['unmatched_parcels_not_seen_in_any_2024_2026_traits'] = len(missing - all_years)
        metrics['trait_parcels'] = len(traits)
        metrics['trait_parcels_without_same_year_title_pnu'] = len(set(traits.pnu) - set(buildings.pnu))
        pair = {'trait_year': year, 'building_snapshot': snapshot,
                'trait_cutoff': inventory[str(year)]['cutoff'], 'metrics': metrics,
                'input_sha256': {'traits': trait_sha, 'buildings': hashlib.sha256(path.read_bytes()).hexdigest()},
                'groups': []}
        for (district, kind), frame in buildings.groupby([buildings.beopjungri_code.str[:5], 'ledger_kind']):
            group, _, _ = summarize(frame, traits)
            pair['groups'].append({'sigungu': district, 'ledger_kind': kind, **group})
        report['pairs'].append(pair)
        for reason, mask in [('pnu_absent_in_same_year_traits', unmatched),
                             ('invalid_building_identity', ~(matched | unmatched))]:
            review = buildings.loc[mask].copy()
            review['reason'] = reason
            review['independent_verification'] = 'unverified'
            queues.append(review)
        print(year, json.dumps(metrics), flush=True)
    for previous, current in ((2024, 2025), (2025, 2026)):
        old = building_data[previous].set_index('mgmt_pk').pnu
        new = building_data[current].set_index('mgmt_pk').pnu
        common = old.index.intersection(new.index)
        report['building_identity_transitions'].append({
            'from_snapshot': PAIRS[previous], 'to_snapshot': PAIRS[current],
            'common_management_pks': len(common), 'new_management_pks': len(new.index.difference(old.index)),
            'missing_management_pks': len(old.index.difference(new.index)),
            'common_management_pks_with_changed_pnu': int(old.loc[common].ne(new.loc[common]).sum())})
    pd.concat(queues, ignore_index=True).to_csv(OUT / 'building_trait_unmatched_review.csv.gz', index=False, compression='gzip')
    for pair in report['pairs']:
        m = pair['metrics']
        assert m['building_rows'] == sum(m[key] for key in ('building_rows_matched', 'valid_identity_unmatched_rows', 'invalid_pnu_rows', 'pnu_bjd_conflict_rows'))
        assert m['building_parcels'] == m['matched_parcels'] + m['unmatched_parcels']
        assert m['matched_parcels'] == m['matched_parcels_with_positive_price'] + m['matched_parcels_without_positive_price']
        assert m['building_rows'] == sum(group['building_rows'] for group in pair['groups'])
    (LAB / 'cheongju_building_trait_coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


if __name__ == '__main__':
    main()
