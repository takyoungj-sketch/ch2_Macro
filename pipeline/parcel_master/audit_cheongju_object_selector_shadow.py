"""Frozen cohort selector replay, with new title coverage for 33 multi-PNU keys."""
import gzip
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from time import perf_counter

from ledger_consumer_input_preview import ROOT, OUT, LAB
from audit_cheongju_apartment_site_review import scan_titles
from audit_cheongju_address_pair_impact import canonical_hash
from parcel_master.paths import title_path
from ledger_object_selector_shadow import VERSION, select_shadow, raw_pair


def load(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)


def summary(plans):
    return {'keys':len(plans),'transactions':sum(p['transactions'] for p in plans),
        'address_partitions':sum(len(p['candidates']) for p in plans),'statuses':dict(Counter(p['status'] for p in plans)),
        'reason_counts':dict(Counter(r for p in plans for r in p['reasons'])),
        'baseline_price_mart_keys':sum(p['baseline']['price_mart'] is not None for p in plans),
        'baseline_building_attribute_keys':sum(bool(p['baseline']['attribute_rows']) for p in plans),
        'selected_representatives':sum(p['new_representative_pnu'] is not None for p in plans),
        'inherited_prices':sum(p['inherited_price_mart'] is not None for p in plans)}


def main():
    paths=[OUT/f for f in ('named_object_mix_evidence.json.gz','named_object_mix_review_queue.json.gz',
                          'address_pair_impact_evidence.json.gz','apartment_site_review_evidence.json.gz','remaining_object_review_evidence.json.gz')]
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    named,queue,addresses,apartments,remainder=[load(p) for p in paths]
    named_report=json.loads((LAB/'cheongju_named_object_mix.json').read_text(encoding='utf-8'))
    if canonical_hash(named)!=named_report['provenance']['evidence_content_sha256']:raise ValueError('Frozen named evidence content differs')
    key=lambda r:(r['building_key'],r['asset_type'])
    selected=[r for r in named if r['named_key'] and r['distinct_legal_dongs']==1 and r['distinct_observed_pnus']>1]
    qkeys={key(r) for r in queue}; skeys={key(r) for r in selected}
    if len(queue)!=52 or len(selected)!=33 or len(qkeys)!=52 or len(skeys)!=33 or qkeys&skeys:raise ValueError('Selector cohorts changed')
    by_key={key(r):r for r in named}
    if any(canonical_hash(r)!=canonical_hash(by_key[key(r)]) for r in queue):raise ValueError('Review queue differs from frozen named evidence')
    stats={(r['product_key'],r['asset_type']):r for r in addresses['residential'] if r['window_years']==7}
    coverage={}; known_titles={}; source_refs={}
    apt_meta=json.loads((LAB/'cheongju_apartment_site_review.json').read_text(encoding='utf-8'))['source_inventory']['title']
    remaining_meta=json.loads((LAB/'cheongju_remaining_object_review.json').read_text(encoding='utf-8'))['source_inventory']['titles']['2026-07']
    if apt_meta['sha256']!=remaining_meta['sha256']:raise ValueError('Prior title inventories differ')
    for case in apartments:
        for s in case['sites']:
            known_titles[s['pnu']]=s['raw_titles']
            source_refs[s['pnu']]='apartment_site_review_evidence.json.gz'
    for case in remainder['cases']:
        for s in case['sites']:
            if s['address_identity'][0]!='pnu':continue
            pnu=s['address_identity'][1]
            if pnu in known_titles and canonical_hash(known_titles[pnu])!=canonical_hash(s['raw_titles']):raise ValueError('Co-address prior title payload differs')
            known_titles[pnu]=s['raw_titles'];source_refs[pnu]='remaining_object_review_evidence.json.gz'
    for pnu,raw in known_titles.items():coverage[pnu]='titles_present' if raw else 'no_titles_in_latest_snapshot'
    pnus={p for r in selected for p in r['observed_pnus']}
    fresh,meta=scan_titles(title_path('2026-07'),pnus)
    if meta['sha256']!=apt_meta['sha256'] or meta['rows']!=apt_meta['rows']:raise ValueError('Frozen title source changed')
    pks=[t['mgmt_pk'] for ts in fresh.values() for t in ts]
    if len(pks)!=len(set(pks)):raise ValueError('Duplicate source title management PK')
    for pnu in pnus:
        raw=fresh.get(pnu,[])
        if pnu in known_titles and canonical_hash(known_titles[pnu])!=canonical_hash(raw):raise ValueError('Fresh source differs from prior co-address evidence')
        known_titles[pnu]=raw;coverage[pnu]='titles_present' if raw else 'no_titles_in_latest_snapshot'
        source_refs[pnu]='object_selector_shadow_title_coverage.json.gz'
    rows=sorted(queue+selected,key=key)
    start=perf_counter();plans=[]
    for r in rows:
        baseline=stats[key(r)]
        plan=select_shadow(r,[str(baseline['beopjungri_code'] or ''),str(baseline['lot_number'] or '')],coverage)
        plan['cohort']='review_queue_52' if key(r) in qkeys else 'same_legal_dong_multi_pnu_33'
        plan['as_of_month']=r['as_of_month'];plan['period_start']=str(baseline['period_start']);plan['period_end']=str(baseline['period_end'])
        for c in plan['candidates']:
            pnu=c['address_identity'][1] if c['address_identity'][0]=='pnu' else None
            c['title_source_provenance']={'source_sha256':meta['sha256'],'snapshot':'2026-07','evidence_file':source_refs[pnu],
                'raw_title_rows':len(known_titles[pnu]),'relation_kind':'title_address','membership_certified':False} if pnu else None
        plans.append(plan)
    selector_seconds=perf_counter()-start
    repeated=[]
    for r in reversed(rows):
        b=stats[key(r)]
        repeated.append(select_shadow(r,[str(b['beopjungri_code'] or ''),str(b['lot_number'] or '')],coverage))
    # Compare core output separately from audit annotations; shuffled inputs must preserve candidates and decisions.
    def core(p):return {k:v for k,v in p.items() if k not in ('cohort','as_of_month','period_start','period_end')}
    clean=[]
    for p in plans:
        p=json.loads(json.dumps(core(p)))
        for c in p['candidates']:c.pop('title_source_provenance')
        clean.append(p)
    stable=canonical_hash(clean)==canonical_hash(sorted(repeated,key=key))
    commercial=[r for r in addresses['commercial'] if r['window_years']==7]
    controls=[{'existing_cluster_key':r['product_key'],'asset_type':r['asset_type'],**select_shadow(r,[],{},'road_cluster')} for r in commercial]
    checks={'85_unique_existing_keys':len(plans)==85 and len({key(p) for p in plans})==85,
        'cohorts_have_no_overlap':not qkeys&skeys,'transactions_conserved':sum(p['transactions'] for p in plans)==13975,
        '177_address_partitions_conserved':sum(len(p['candidates']) for p in plans)==177,
        'all_baseline_enrichment_preserved':all(p['baseline']['price_mart']==by_key[key(p)]['baseline_price_mart'] and p['baseline']['attribute_rows']==by_key[key(p)]['existing_attribute_rows'] for p in plans),
        'no_assignments_or_inheritance':all(p['selected_observed_pair'] is None and p['new_object_key'] is None and p['new_representative_pnu'] is None and p['inherited_price_mart'] is None and p['inherited_building_attributes'] is None and not p['production_apply'] for p in plans),
        'core_replay_stable_after_row_order_reversal':stable,
        'no_unreviewed_canonical_source_coverage':all(c['source_coverage_status']!='not_reviewed' for p in plans for c in p['candidates']),
        'commercial_306_cluster_identities_preserved':len(controls)==306 and all(not c['residential_scope_rules_applied'] for c in controls),
        'protected_inputs_unchanged':all(hashlib.sha256(p.read_bytes()).hexdigest()==hashes[p.name] for p in paths)}
    if not all(checks.values()):raise AssertionError(checks)
    brief=[{'case_number':i,'asset_type':p['asset_type'],'cohort':p['cohort'],'status':p['status'],'reasons':p['reasons'],
        'transactions':p['transactions'],'address_partitions':len(p['candidates']),'baseline_price_present':p['baseline']['price_mart'] is not None,
        'baseline_attributes_present':bool(p['baseline']['attribute_rows']),'source_missing_partitions':sum(c['source_coverage_status']=='no_titles_in_latest_snapshot' for c in p['candidates']),
        'observed_address_labels':sorted({' '.join(str(g[k] or '') for k in ('addr4','lot_number','building_name')) for c in by_key[key(p)]['address_review_partitions'] for g in c['address_groups']})} for i,p in enumerate(plans,1)]
    report={'audit_version':VERSION,'run_date':date.today().isoformat(),'scope_summary':summary(plans),
        'by_cohort':{c:summary([p for p in plans if p['cohort']==c]) for c in ('review_queue_52','same_legal_dong_multi_pnu_33')},
        'by_asset_type':{a:summary([p for p in plans if p['asset_type']==a]) for a in sorted({p['asset_type'] for p in plans})},
        'source_coverage_partition_counts':dict(Counter(c['source_coverage_status'] for p in plans for c in p['candidates'])),
        'fresh_33_key_title_coverage':{'distinct_pnus_requested':len(pnus),'pnus_with_titles':len(fresh),'title_rows':len(pks)},
        'commercial_control':{'keys':len(controls),'analysis_unit':'road_cluster','action':'keep_existing_cluster_identity','source':'protected prior address audit, not a new DB query'},
        'selector_runtime_seconds':selector_seconds,'selector_runtime_scope':'In-memory 85-key candidate validation and review gates only; excludes file IO and source scan, not production latency.',
        'checks':checks,'cases':brief,'source_inventory':{'title':meta},
        'provenance':{'protected_inputs_sha256':hashes,'plan_content_sha256':canonical_hash(plans),
                      'selector_code_sha256':hashlib.sha256((ROOT/'pipeline/parcel_master/ledger_object_selector_shadow.py').read_bytes()).hexdigest(),
                      'audit_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        'limitations':['No source-specific membership verifier is implemented. Caller verification flags are rejected.',
                       'All outputs are observations and review holds, not new objects or regression inputs.',
                       'Source title coverage is latest 2026-07; absence is not demolition or historical nonexistence.',
                       'No current DB re-query: source windows and enrichment reuse protected frozen inputs.',
                       'Commercial control reuses prior clusters and deliberately skips residential scope rules.',
                       'In-memory runtime is not a product/API/database performance measurement.']}
    for filename,payload in [('object_selector_shadow_plans.json.gz',plans),('object_selector_shadow_title_coverage.json.gz',fresh),('object_selector_shadow_commercial_control.json.gz',controls)]:
        with gzip.open(OUT/filename,'wt',encoding='utf-8') as f:json.dump(payload,f,ensure_ascii=False)
    (LAB/'cheongju_object_selector_shadow.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('cases','source_inventory','provenance','limitations')},ensure_ascii=True),flush=True)


if __name__=='__main__':main()
