"""City-wide, local read-only address audit. Never assigns a representative.

Inspect every stored window at each key's latest month. Include keys touching
Cheongju in either transactions or stored stats; retain ALL matching window
transactions so a mixed-region key is not silently truncated.
"""
import gzip
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from time import perf_counter
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam, text

from audit_cheongju_product_link_candidates import address_pnu
from ledger_consumer_input_preview import ROOT, OUT, LAB

sys.path.insert(0, str(ROOT / 'pipeline'))
from collective.db_utils import get_collective_engine

DISTRICTS = ('43111', '43112', '43113', '43114')
FIELDS = {
    'residential': ('beopjungri_code', 'lot_number'),
    'commercial': ('addr1', 'addr2', 'addr3', 'addr4', 'road_name'),
}


def queries(product):
    residential = product == 'residential'
    key = 'building_key' if residential else 'cluster_key'
    stats = 'collective_building_stats' if residential else 'collective_commercial_cluster_stats'
    transactions = 'collective_transactions' if residential else 'collective_commercial_transactions'
    city_stats = ('s.sigungu_code IN :districts OR substring(s.beopjungri_code,1,5) IN :districts'
                  if residential else "s.addr2 LIKE '%청주시%'")
    # Stats-only keys and all city transaction keys are both included.
    cte = f"""WITH city_keys AS (
      SELECT DISTINCT {key},asset_type FROM {transactions}
      WHERE sigungu_code IN :districts OR substring(beopjungri_code,1,5) IN :districts
      UNION SELECT DISTINCT {key},asset_type FROM {stats} s WHERE {city_stats}
    ), months AS (
      SELECT s.{key},s.asset_type,MAX(s.as_of_month) AS latest_month
      FROM {stats} s JOIN city_keys k USING({key},asset_type)
      GROUP BY s.{key},s.asset_type
    ), selected AS (
      SELECT s.* FROM {stats} s JOIN months m USING({key},asset_type)
      WHERE s.as_of_month=m.latest_month
    ) """
    extra = (',s.beopjungri_code,s.lot_number,s.sigungu_code,lp.representative_pnu,lp.assessed_land_price_year'
             if residential else ',s.addr1,s.addr2,s.addr3,s.addr4,s.road_name')
    mart_join = ('LEFT JOIN collective_building_assessed_land_price lp USING(building_key,asset_type)'
                 if residential else '')
    selected_sql = cte + f"""SELECT s.id,s.{key} product_key,s.asset_type,s.as_of_month,
      s.window_years,s.period_start,s.period_end,s.count stored_count,s.computed_at {extra}
      FROM selected s {mart_join} ORDER BY s.id"""
    fields = FIELDS[product]
    tx_exprs = [f't.{f}' if f != 'road_name' or residential else 't.audit_road_name' for f in fields]
    select_fields = ','.join(f'{expr} AS {f}' for f, expr in zip(fields, tx_exprs))
    max_fields = ','.join(f'MAX({f}) OVER(PARTITION BY stats_id) AS max_{f}' for f in fields)
    cluster_join = 'JOIN commercial_clusters c ON c.id=t.cluster_id' if not residential else ''
    # Replay the exact eligibility filter and PostgreSQL collation of ROLLING_SQL.
    grouped_sql = cte + f""", eligible AS MATERIALIZED (
      SELECT t.* {',c.road_name AS audit_road_name' if not residential else ''}
      FROM {transactions} t JOIN city_keys k USING({key},asset_type) {cluster_join}
      WHERE t.is_valid=true AND t.unit_price IS NOT NULL AND t.unit_price>0
        AND t.contract_date IS NOT NULL
    ), grouped AS (
      SELECT s.id stats_id,{select_fields},COUNT(t.id) transactions,
        MIN(t.contract_date) first_contract,MAX(t.contract_date) last_contract,
        array_remove(array_agg(DISTINCT t.sigungu_code ORDER BY t.sigungu_code),NULL) district_codes
      FROM selected s LEFT JOIN eligible t ON t.{key}=s.{key} AND t.asset_type=s.asset_type
        AND t.contract_date BETWEEN s.period_start AND s.period_end
      GROUP BY s.id,{','.join(tx_exprs)}
    ) SELECT *,{max_fields} FROM grouped ORDER BY stats_id,{','.join(fields)}"""
    return selected_sql, grouped_sql


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    default=str, separators=(',', ':')).encode()).hexdigest()


def classify_row(product, stats, groups):
    fields = FIELDS[product]
    groups = [g for g in groups if g['transactions'] > 0]
    stored = tuple(stats.get(f) for f in fields)
    observed = {tuple(g.get(f) for f in fields) for g in groups}
    maximum = tuple(groups[0].get('max_' + f) for f in fields) if groups else None
    tx_count = sum(g['transactions'] for g in groups)
    reasons = []
    if not groups:
        reasons.append('no_current_eligible_window_transactions')
    elif stored not in observed:
        reasons.append('stored_address_tuple_not_observed')
    if maximum is not None and maximum not in observed:
        reasons.append('component_max_tuple_not_observed')
    if maximum is not None and maximum != stored:
        reasons.append('stored_tuple_differs_from_current_component_max')
    if tx_count != stats['stored_count']:
        reasons.append('stored_count_differs_from_current_eligible_count')
    codes = sorted({str(c).strip() for g in groups for c in g['district_codes'] if c})
    district = (codes[0] if len(codes) == 1 else 'multiple_districts' if codes else 'unknown')
    result = {**stats, 'product': product, 'district': district,
              'observed_district_codes': codes, 'eligible_transaction_count': tx_count,
              'distinct_raw_address_tuples': len(observed), 'flags': reasons,
              'stored_tuple_observed': stored in observed if groups else None,
              'component_max_tuple_observed': maximum in observed if groups else None,
              'component_max_reproduces_stored': maximum == stored if groups else None,
              'address_groups': groups, 'new_representative_assignment': None,
              'independent_membership_verification': 'unverified'}
    if product == 'residential':
        pnus = {address_pnu(g['beopjungri_code'], g['lot_number']) for g in groups}
        pnus.discard(None)
        current = address_pnu(stats['beopjungri_code'], stats['lot_number'])
        mart = str(stats.get('representative_pnu') or '').strip() or None
        if current is None:
            reasons.append('stored_address_not_strictly_parseable_as_cheongju_pnu')
        if len(pnus) > 1:
            reasons.append('multiple_observed_cheongju_pnus')
        if mart and current and mart != current:
            reasons.append('mart_pnu_differs_from_stats_pnu')
        if mart and groups and mart not in pnus:
            reasons.append('mart_pnu_not_in_current_window_cheongju_candidates')
        if mart and current and groups and mart == current and current not in pnus:
            reasons.append('price_mart_uses_unobserved_stats_pnu')
        result.update(strict_stats_pnu=current, observed_cheongju_pnus=sorted(pnus),
                      distinct_observed_cheongju_pnus=len(pnus),
                      unparseable_address_group_count=sum(address_pnu(g['beopjungri_code'],g['lot_number']) is None for g in groups))
    else:
        result['analysis_unit'] = 'road_cluster_not_parcel_or_danji'
    return result


def summarize(rows):
    keys = {(r['product_key'], r['asset_type']) for r in rows}
    flag_keys = defaultdict(set)
    for r in rows:
        for f in r['flags']:
            flag_keys[f].add((r['product_key'], r['asset_type']))
    return {'stats_rows': len(rows), 'unique_product_keys': len(keys),
            'eligible_transaction_window_memberships': sum(r['eligible_transaction_count'] for r in rows),
            'flag_rows': dict(Counter(f for r in rows for f in r['flags'])),
            'flag_unique_product_keys': {f: len(k) for f,k in sorted(flag_keys.items())},
            'component_max_reproduces_stored_rows': sum(r['component_max_reproduces_stored'] is True for r in rows)}


def breakdown(rows, field):
    return {str(value): summarize([r for r in rows if r[field] == value])
            for value in sorted({r[field] for r in rows}, key=str)}


def build_report(records, provenance):
    products = {}
    for product, rows in records.items():
        # Same consumer selector as the prior audit: latest month, longest window.
        selected = {}
        for row in rows:
            key = (row['product_key'], row['asset_type'])
            if key not in selected or row['window_years'] > selected[key]['window_years']:
                selected[key] = row
        consumer = list(selected.values())
        products[product] = {'all_latest_windows': summarize(rows),
                             'latest_longest_window': summarize(consumer),
                             'by_asset_type': breakdown(consumer, 'asset_type'),
                             'by_district': breakdown(consumer, 'district'),
                             'by_window_years': breakdown(rows, 'window_years'),
                             'snapshot_months': sorted({str(r['as_of_month']) for r in rows})}
        if product == 'residential':
            products[product]['ledger_consumer_latest_longest_window'] = summarize([
                r for r in consumer if r['asset_type'] in ('apartment', 'officetel', 'rowhouse')])
            products[product]['price_mart_exposure_latest_longest_window'] = {
                'keys_with_price_mart': sum(bool(r.get('representative_pnu')) for r in consumer),
                'unobserved_stats_tuple_with_price_mart': sum(bool(r.get('representative_pnu')) and r['stored_tuple_observed'] is False for r in consumer),
                'mart_uses_unobserved_stats_pnu': sum('price_mart_uses_unobserved_stats_pnu' in r['flags'] for r in consumer),
                'mart_uses_unobserved_stats_pnu_by_asset_type': dict(Counter(r['asset_type'] for r in consumer if 'price_mart_uses_unobserved_stats_pnu' in r['flags']))}
    return {'run_date_kst': datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat(),
            'audit_version': 'cheongju-address-pair-impact-v1', 'provenance': provenance,
            'products': products,
            'checks': {'unique_stats_ids': all(len({r['id'] for r in rows}) == len(rows) for rows in records.values()),
                       'no_representative_assignment': all(r['new_representative_assignment'] is None for rows in records.values() for r in rows),
                       'district_breakdowns_partition_consumer_keys': all(sum(v['unique_product_keys'] for v in p['by_district'].values()) == p['latest_longest_window']['unique_product_keys'] for p in products.values())},
            'limitations': [
                'Current local read-only snapshot, not a production VPS audit or historical import reconstruction.',
                'Address tuple observation is not independently verified transaction/danji membership.',
                'All-window row totals repeat keys and transactions; they are not unique city transaction counts.',
                'Latest longest window is per key, not a single globally synchronized observation month.',
                'Component maxima use PostgreSQL collation. Raw tuple absence and strict PNU parsing are separate flags.',
                'Count/tuple drift may reflect later transaction corrections; do not attribute all absence to the MAX rule.',
                'Commercial five-field tuples describe road clusters; multiple parcel addresses are expected and not certified assignments.',
                'No new prices, building aggregates, representative choices, or regression samples are published.']}


def main():
    protected = [OUT/'product_link_candidate_review.json.gz', OUT/'representative_multibuilding_evidence.json.gz']
    prior = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    engine = get_collective_engine()
    records, inputs, sql_hashes = {}, {}, {}
    try:
        if engine.url.host not in ('localhost', '127.0.0.1', '::1'):
            raise RuntimeError('Local database required')
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            conn.execute(text("SET LOCAL statement_timeout='60s'"))
            # CTE cardinality estimates can select a nationwide sorted index
            # scan for this small city audit. Scope the planner override to this
            # read-only transaction; never change database/server settings.
            conn.execute(text('SET LOCAL enable_mergejoin=off'))
            readonly = conn.execute(text('SHOW transaction_read_only')).scalar_one()
            if readonly != 'on':
                raise RuntimeError('Read-only transaction required')
            snapshot = dict(conn.execute(text('SELECT current_database() db,txid_current_snapshot() snapshot,current_timestamp observed_at')).one()._mapping)
            for product in FIELDS:
                sqls = queries(product)
                values = []
                for sql in sqls:
                    started = perf_counter()
                    statement = text(sql).bindparams(bindparam('districts', expanding=True))
                    values.append([dict(r._mapping) for r in conn.execute(statement, {'districts': DISTRICTS})])
                    print(product, 'query', len(values), 'seconds', round(perf_counter()-started,2), flush=True)
                stats, groups = values
                by_id = defaultdict(list)
                for g in groups:
                    by_id[g['stats_id']].append(g)
                if set(by_id) != {s['id'] for s in stats}:
                    raise AssertionError('Missing or unexpected stats address groups')
                records[product] = [classify_row(product, s, by_id[s['id']]) for s in stats]
                inputs[product] = canonical_hash(values)
                sql_hashes[product] = canonical_hash(sqls)
                print(product, 'stats rows', len(stats), 'address groups', len(groups), flush=True)
    finally:
        engine.dispose()
    provenance = {'database_snapshot': snapshot, 'transaction_read_only': readonly,
                  'transaction_local_planner': {'enable_mergejoin': 'off'},
                  'query_output_sha256': inputs, 'query_text_sha256': sql_hashes,
                  'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'protected_prior_evidence_sha256': prior}
    report = build_report(records, provenance)
    with gzip.open(OUT/'representative_multibuilding_evidence.json.gz', 'rt', encoding='utf-8') as stream:
        previous_traces = json.load(stream)['traces']
    longest = {(r['product_key'], r['asset_type']): r for r in records['residential'] if r['window_years'] == 7}
    report['checks']['prior_four_traces_reproduced'] = all(
        (old['building_key'], old['asset_type']) in longest and
        longest[(old['building_key'], old['asset_type'])]['stored_tuple_observed'] == old['current_address_pair_observed_in_window_transactions'] and
        longest[(old['building_key'], old['asset_type'])]['component_max_reproduces_stored'] is True
        for old in previous_traces)
    report['checks']['prior_evidence_unchanged'] = all(hashlib.sha256(p.read_bytes()).hexdigest() == prior[p.name] for p in protected)
    if not all(report['checks'].values()):
        raise AssertionError(report['checks'])
    OUT.mkdir(parents=True, exist_ok=True)
    # Canonical content digest excludes run/snapshot metadata, preserves evidence.
    report['evidence_content_sha256'] = canonical_hash(records)
    with gzip.open(OUT/'address_pair_impact_evidence.json.gz', 'wt', encoding='utf-8') as stream:
        json.dump(records, stream, ensure_ascii=False, default=str)
    (LAB/'cheongju_address_pair_impact.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, default=str), flush=True)


if __name__ == '__main__':
    main()
