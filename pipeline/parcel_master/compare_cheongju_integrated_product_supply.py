"""Pair frozen product keys with integrated source candidates, without assignment."""
import gzip
import json
from collections import Counter
from decimal import Decimal, InvalidOperation
from time import perf_counter

from integrated_ledger_v2 import CONTRACT, consumer, digest
from ledger_release_cli import open_ledger
from run_cheongju_integrated_ledger_v2 import OUT, LAB, file_hash


def compare_price(baseline, candidate):
    if baseline is None:
        return 'no_existing_price'
    if candidate is None or candidate['status'] != 'positive_known_year':
        return 'selected_source_price_unavailable'
    if baseline['assessed_land_price_year'] != candidate['price_year']:
        return 'different_price_year_not_comparable'
    try:
        old = Decimal(str(baseline['assessed_land_price']))
        new = Decimal(str(candidate['raw_price']))
    except InvalidOperation:
        return 'invalid_existing_or_source_price'
    if not old.is_finite() or not new.is_finite() or old <= 0 or new <= 0:
        return 'invalid_existing_or_source_price'
    return 'same_year_equal' if old == new else 'same_year_changed'


def main():
    started = perf_counter()
    named_path = OUT / 'named_object_mix_evidence.json.gz'
    commercial_path = OUT / 'object_selector_shadow_commercial_control.json.gz'
    hashes = {p.name: file_hash(p) for p in (named_path, commercial_path)}
    with gzip.open(named_path, 'rt', encoding='utf-8') as f:
        named = json.load(f)
    with gzip.open(commercial_path, 'rt', encoding='utf-8') as f:
        commercial = json.load(f)
    prior = json.loads((LAB/'cheongju_named_object_mix.json').read_text(encoding='utf-8'))
    if digest(named) != prior['provenance']['evidence_content_sha256']:
        raise ValueError('Frozen product evidence changed')
    db = open_ledger(OUT/'integrated_ledger_v2_cheongju.sqlite')
    head = db.execute("SELECT value FROM state WHERE key='published_release'").fetchone()[0]
    manifest = json.loads(db.execute('SELECT manifest FROM release WHERE id=?', (head,)).fetchone()[0])
    if manifest['title_snapshot'] != '2026-07' or len(named) != 1471:
        raise ValueError('Paired source/window scope changed')
    seen = set(); rows = []; statuses = Counter(); source_cache = {}
    def source_at(pnu):
        if pnu in source_cache:
            return source_cache[pnu]
        pks = [r[0] for r in db.execute('SELECT pk FROM address_relation WHERE release_id=? AND pnu=? ORDER BY pk', (head,pnu))]
        sources = [consumer(db, pk) for pk in pks]
        price = db.execute('SELECT price_year,raw_price,status FROM price_observation WHERE release_id=? AND pnu=?', (head,pnu)).fetchone()
        land = db.execute('SELECT raw FROM parcel_observation WHERE release_id=? AND pnu=?',(head,pnu)).fetchone()
        last = db.execute('SELECT last_seen_release FROM current_parcel WHERE pnu=?',(pnu,)).fetchone()
        raw = json.loads(land[0]) if land else None
        permissions = {'source_display':bool(land),'candidate_research':bool(land),
                       'product_enrichment':False,'quantity_aggregation':False,'regression':False}
        price_value = dict(zip(('price_year','raw_price','status'),price)) if price else None
        payload = {'relation_kind':'title_address','building_consumers':sources,
                   'parcel_traits_observation':{'value':raw,'source':manifest['sources']['traits'],
                       'base_date':{'row_observed_at':raw.get('trait_asof'),'base_year':raw.get('year'),
                                    'source_cutoff':manifest['sources']['traits']['base_date']} if raw else None,
                       'trust_state':'observed' if raw else 'not_observed_in_selected_release',
                       'last_seen':last[0] if last else None,'permissions':permissions},
                   'parcel_price_observation':{'value':price_value,'source':manifest['sources']['traits'],
                       'base_date':{'price_year':price[0]} if price else None,
                       'trust_state':price[2] if price else 'not_observed_in_selected_snapshot',
                       'last_seen':last[0] if last else None,
                       'permissions':{**permissions,'candidate_research':bool(price and price[2]=='positive_known_year')}},
                   'product_use_allowed':False,'membership_verified':False}
        source_cache[pnu] = payload
        return payload
    for r in named:
        key = (r['building_key'],r['asset_type'])
        if key in seen:
            raise ValueError('Duplicate frozen product key')
        seen.add(key)
        baseline = {'price_mart':r['baseline_price_mart'],'attribute_rows':r['existing_attribute_rows'],
                    'address_partitions':r['address_review_partitions']}
        candidates = [{'observed_pnu':pnu,**source_at(pnu)} for pnu in sorted(r['observed_pnus'])]
        old_price = r['baseline_price_mart']
        rep = old_price['representative_pnu'] if old_price else None
        # This is the EXISTING representative, not a newly selected representative.
        rep_source = source_at(rep) if rep else None
        status = compare_price(old_price, rep_source['parcel_price_observation']['value'] if rep_source else None)
        statuses[status] += 1
        rows.append({'building_key':key[0],'asset_type':key[1],'stats_id':r['stats_id'],
                     'as_of_month':r['as_of_month'],'transactions':r['transaction_count'],
                     'baseline':baseline,'baseline_content_sha256':digest(baseline),
                     'integrated_candidates':candidates,'existing_representative_source':rep_source,
                     'existing_representative_is_observed_address':rep in r['observed_pnus'] if rep else None,
                     'price_comparison':status,'new_representative_pnu':None,'production_apply':False,
                     'regression_result':'not_recomputed'})
    checks = {'1471_keys_preserved':len(rows)==1471 and len(seen)==1471,
              'transaction_counts_preserved':sum(x['transactions'] for x in rows)==sum(x['transaction_count'] for x in named),
              'all_legacy_enrichment_exact':all(x['baseline']['price_mart']==r['baseline_price_mart'] and x['baseline']['attribute_rows']==r['existing_attribute_rows'] for x,r in zip(rows,named)),
              'no_implicit_product_permissions':all(not v['permissions']['product_enrichment'] and not v['permissions']['quantity_aggregation'] and not v['permissions']['regression'] for p in source_cache.values() for b in p['building_consumers'] for v in (b['building'],b['traits'],b['price'])),
              'parcel_value_contract_preserved':all(all(field in v for field in ('value','source','base_date','trust_state','last_seen','permissions')) and not any(v['permissions'][flag] for flag in ('product_enrichment','quantity_aggregation','regression')) for p in source_cache.values() for v in (p['parcel_traits_observation'],p['parcel_price_observation'])),
              'no_new_representatives':all(x['new_representative_pnu'] is None and not x['production_apply'] for x in rows),
              'commercial_306_preserved':len(commercial)==306 and all(not c['residential_scope_rules_applied'] for c in commercial),
              'protected_product_inputs_unchanged':all(file_hash(OUT/name)==sha for name,sha in hashes.items())}
    if not all(checks.values()):
        raise AssertionError(checks)
    with gzip.open(OUT/'integrated_product_supply_paired.json.gz','wt',encoding='utf-8') as f:
        json.dump({'published_release':head,'consumer_contract':CONTRACT,'residential':rows,'commercial':commercial},f,ensure_ascii=False)
    report = {'consumer_contract':CONTRACT,'published_release':head,'keys':len(rows),
              'transactions':sum(x['transactions'] for x in rows),'by_asset_type':dict(Counter(x['asset_type'] for x in rows)),
              'address_partitions':sum(len(x['baseline']['address_partitions']) for x in rows),
              'distinct_source_parcels_requested':len(source_cache),'price_comparisons_at_existing_representative':dict(statuses),
              'keys_with_observed_address_title_candidates':sum(any(c['building_consumers'] for c in x['integrated_candidates']) for x in rows),
              'commercial_control_keys':len(commercial),'checks':checks,'frozen_inputs_sha256':hashes,
              'elapsed_seconds':perf_counter()-started,
              'limitations':['Source candidates paired with frozen residential keys including presale; no transaction-to-building assignment.',
                             'Legacy attribute evidence contains match metadata, not numeric attribute values; attribute equality cannot be certified.',
                             'Existing representative price is compared only at the same price year; candidate parcels are not summed.',
                             'Commercial existing road clusters preserved; no residential relation rules applied.',
                             'No production input replacement or regression recomputation. Full product output parity remains a later gate.']}
    db.close()
    (LAB/'cheongju_integrated_product_supply_paired.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))


if __name__ == '__main__':
    main()
