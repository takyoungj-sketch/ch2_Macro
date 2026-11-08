"""Read-only operational price audit against the frozen source ledger.

Private input/output belong in ignored logs, never in a committed report.
This does not materialize links or alter the V1 rule.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parcel_master.pnu import pnu_from_tx
from parcel_master.cheongju_land_link_probe import (
    compact_jimok, compact_zones, latest_consistent_plate, _matches, _later_match,
)
from parcel_master.cheongju_land_label_rule_probe import attach_price_detail, normalized_plate
from parcel_master.cheongju_land_conflict_cause_probe import conflict_signature
from parcel_master.trait_link_helpers import area_key, lot_matches


def load_parcel(db, pnu):
    raw = db.execute("SELECT * FROM parcel_observation WHERE pnu=? ORDER BY asof,price_year,price_month", (pnu,)).fetchall()
    plates = [(r[1], int(r[2]), int(r[3]), compact_jimok(r[5]), area_key(r[6]), compact_zones(r[8], r[10]), r[19]) for r in raw]
    groups = defaultdict(list)
    for r in db.execute("SELECT pnu,asof,price_year,price_month,source_file,jimok_code,jimok_label,area,zone1_code,zone1_label,zone2_code,zone2_label,use_code,use_label,height_code,height_label,shape_code,shape_label,road_code,road_label,price FROM observation_conflict WHERE pnu=?", (pnu,)):
        groups[r[:4]].append(r)
    norm = [p for rows in groups.values() if (p := normalized_plate(rows)) is not None]
    return sorted(plates), sorted(norm), raw, groups


def price_cause(plates, year):
    for y in (year, year - 1):
        periods = defaultdict(set)
        broken = False
        for p in plates:
            if p[1] != y or not str(p[6] or '').strip():
                continue
            try:
                v = Decimal(p[6])
                if not v.is_finite():
                    broken = True
                else:
                    periods[p[2]].add(v)
            except InvalidOperation:
                broken = True
        amounts = set().union(*periods.values()) if periods else set()
        if broken:
            return 'malformed', y
        if len(amounts) > 1:
            return ('between_reference_months_only' if all(len(v) == 1 for v in periods.values()) else 'same_reference_month_variation'), y
        if amounts:
            return 'not_reproduced', y
    return 'source_price_missing', None


def check_candidates(db, r, chosen_pnu, cache):
    """Search every matching masked lot in this resolved administrative code.

    The numeric area predicate is deliberately wider than 0.1 m² rounding;
    final eligibility uses the V1 Decimal helper and source plates.
    """
    mask = str(r['lot_display']).replace(' ', '').removeprefix('산')
    lo = r['ledger_beopjungri_code'] + chosen_pnu[10] + mask.replace('*', '0').zfill(4) + '0000'
    hi = r['ledger_beopjungri_code'] + chosen_pnu[10] + mask.replace('*', '9').zfill(4) + '9999'
    area = float(r['area_sqm'])
    candidates = set()
    for table in ('parcel_observation', 'observation_conflict'):
        candidates.update(row[0] for row in db.execute(
            f'SELECT DISTINCT pnu FROM {table} WHERE pnu>=? AND pnu<=? AND CAST(area AS REAL) BETWEEN ? AND ?',
            (lo, hi, area - .11, area + .11)))
    prior, later, normalized_matches = set(), set(), set()
    for candidate in candidates:
        if not lot_matches(r['lot_display'], candidate, str(int(candidate[11:15]))):
            continue
        if candidate not in cache:
            cache[candidate] = load_parcel(db, candidate)
        plates, norm, _, _ = cache[candidate]
        group = latest_consistent_plate(plates, r['contract_date'])
        if group and _matches(group, r['land_category'], area_key(r['area_sqm']), r['zone_type']):
            prior.add(candidate)
        elif _later_match(plates, r['contract_date'], r['land_category'], area_key(r['area_sqm']), r['zone_type']):
            later.add(candidate)
        combined = latest_consistent_plate(sorted(plates + norm), r['contract_date'])
        if not any(p[0] <= r['contract_date'] for p in plates) and combined and _matches(combined, r['land_category'], area_key(r['area_sqm']), r['zone_type']):
            normalized_matches.add(candidate)
    agrees = prior == {chosen_pnu} if prior else later == {chosen_pnu} and normalized_matches == {chosen_pnu}
    return {'candidate_unique_agrees': agrees, 'normal_candidate_count': len(prior), 'later_candidate_count':len(later), 'normalized_candidate_count': len(normalized_matches)}


def run(input_file: Path, output_file: Path, summary_file: Path):
    data = json.loads(input_file.read_text(encoding='utf-8'))
    db = sqlite3.connect('file:C:/CH2/parcel_master/land_trait_observations.sqlite?mode=ro&immutable=1', uri=True)
    db.execute('PRAGMA query_only=ON')
    cache, results = {}, []
    impact, parcels = Counter(), defaultdict(set)
    reference_months, same_period_same_asof = Counter(), Counter()
    for n, r in enumerate(data['conflicts'] + data['samples']):
        pnu = pnu_from_tx(r.get('ledger_beopjungri_code'), r.get('recovered_lot'))
        out = {'hash': r['transaction_hash'], 'pnu': pnu, 'stratum': r.get('stratum', 'conflict_population')}
        if not pnu or not r.get('contract_date'):
            out['cause'] = 'unresolved_identity_or_orphan'
        else:
            if pnu not in cache:
                cache[pnu] = load_parcel(db, pnu)
            plates, norm, raw, groups = cache[pnu]
            combined = sorted(plates + norm)
            year = int(r['contract_date'][:4])
            cause, target_year = price_cause(combined, year)
            out.update(cause=cause, target_year=target_year)
            if out['stratum'] == 'conflict_population':
                reference_months[','.join(map(str, sorted({p[2] for p in combined if p[1] == target_year and str(p[6] or '').strip()})))] += 1
                by_period_asof = defaultdict(set)
                for p in combined:
                    if p[1] == target_year and str(p[6] or '').strip():
                        by_period_asof[(p[0], p[2])].add(Decimal(p[6]))
                same_period_same_asof[str(any(len(v) > 1 for v in by_period_asof.values()))] += 1
            if out['stratum'] != 'conflict_population':
                status, amount, price_year = attach_price_detail(combined, year)
                out['price_agrees'] = status == r['price_status'] and (str(amount) == str(r['official_price_won']) if amount is not None else r['official_price_won'] is None) and price_year == r['price_year']
                # Decimal comparison avoids differences in numeric serialization.
                if amount is not None and r['official_price_won'] is not None:
                    out['price_agrees'] = status == r['price_status'] and amount == Decimal(str(r['official_price_won'])) and price_year == r['price_year']
                source = sorted(plates + (norm if r['link_status'] == 'label_normalized' else []))
                group = latest_consistent_plate(source, r['contract_date'])
                out['traits_agree'] = bool(group and _matches(group, r['land_category'], area_key(r['area_sqm']), r['zone_type']))
                out['trait_date_agrees'] = bool(group and group[0][0] == r['trait_asof'])
                out['lot_mask_agrees'] = lot_matches(r['lot_display'], pnu, str(int(pnu[11:15])))
                out['later_observation_exists'] = bool(source and source[-1][0] > r['trait_asof'])
                out['later_precontract_conflict'] = any(r['trait_asof'] < k[1] <= r['contract_date'] for k in groups)
                out['later_precontract_semantic_conflict'] = any(r['trait_asof'] < k[1] <= r['contract_date'] and conflict_signature(v)['category'] != 'label_only' for k, v in groups.items())
                out['source_files'] = sorted({v[20] for v in raw} | {v[4] for rows in groups.values() for v in rows})
                out['reference_periods'] = sorted({(p[1], p[2], p[6]) for p in combined if p[1] in (year, year - 1)})
                out.update(check_candidates(db, r, pnu, cache))
        if out['stratum'] == 'conflict_population':
            impact[out['cause']] += 1
            if pnu:
                parcels[out['cause']].add(pnu)
        results.append(out)
        if n % 1000 == 0:
            print(json.dumps({'processed': n, 'cached_parcels': len(cache)}), flush=True)
    samples = [r for r in results if r['stratum'] != 'conflict_population']
    summary = {'operational_counts': data['counts'], 'conflict_transactions': dict(impact), 'conflict_parcels': {k: len(v) for k, v in parcels.items()}, 'conflict_reference_month_sets':dict(reference_months), 'different_prices_same_asof_and_period':dict(same_period_same_asof), 'sample_count': len(samples), 'sample_strata': dict(Counter(r['stratum'] for r in samples)), 'sample_checks': {key: dict(Counter(str(r.get(key)) for r in samples)) for key in ('price_agrees','traits_agree','trait_date_agrees','lot_mask_agrees','candidate_unique_agrees','later_observation_exists','later_precontract_conflict','later_precontract_semantic_conflict')}, 'sample_sido_count': len({r['ledger_beopjungri_code'][:2] for r in data['samples']})}
    output_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('input', type=Path)
    p.add_argument('private_output', type=Path)
    p.add_argument('summary', type=Path)
    a = p.parse_args()
    run(a.input, a.private_output, a.summary)
