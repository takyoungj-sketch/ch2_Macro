"""Product adapters for frozen research replay; never a production writer."""
import copy
import gzip
import json
from collections import Counter
from decimal import Decimal, InvalidOperation
from time import perf_counter

from freeze_cheongju_product_numeric import load
from extend_cheongju_product_fields import TARGET, RELEASE, product_row
from integrated_ledger_v2 import digest, validate_pnu
from ledger_release_cli import open_ledger
from audit_cheongju_product_link_candidates import address_pnu, recovered_pnu
from run_cheongju_integrated_ledger_v2 import OUT, LAB, file_hash
from parcel_master.title_fill import aggregate_title_dongs
from build_collective_building_attributes import structure_group
from built.enrichment_rows import structure_group as built_structure_group
from ledger_supply_artifacts import write_gzip_atomic,write_json_atomic

FIELDS=('approved_year','households','dong_count','max_floor','parking_total','parking_per_household','structure_group')


def strict_pnu(bjd,lot):
    value=address_pnu(bjd,lot)
    if not value:return None
    try:validate_pnu(value)
    except ValueError:return None
    return value


def equal_value(a,b):
    if a is None or b is None:return a is b
    try:
        left,right=Decimal(str(a)),Decimal(str(b))
        return left.is_finite() and right.is_finite() and left==right
    except InvalidOperation:return str(a)==str(b)


def projected_attributes(rows,asset):
    agg=aggregate_title_dongs(rows,kind=asset)
    if agg is None:return None
    hh,park=agg['households'],agg['parking_total']
    return {'approved_year':agg['approved_year'],'households':hh,'dong_count':agg['dong_count'],
            'max_floor':agg['max_floor'],'parking_total':park,
            'parking_per_household':round(park/hh,3) if hh and park else None,
            'structure_group':structure_group(agg['structure_raw'])}


def value_contract(payload,source,base_date,trust,last_seen):
    return {'value':payload,'source':source,'base_date':base_date,'trust_state':trust,'last_seen':last_seen,
            'permissions':{'legacy_replay_audit':True,'product_enrichment':False,'quantity_aggregation':False,'regression':False}}


def candidate_replay(old,candidate,status,hold):
    result=copy.deepcopy(old)
    if status=='title_numeric_changed' and not hold:
        if result is None or candidate is None or set(candidate)!=set(FIELDS):
            raise ValueError('Complete whitelisted title projection required')
        result.update(candidate)
    return result


def compatibility_attributes(old,candidate,status,hold):
    result=copy.deepcopy(old)
    if status!='title_numeric_equal' or hold:return result,False
    if result is None or candidate is None or set(candidate)!=set(FIELDS):
        raise ValueError('Complete equal-valued title projection required')
    for field,value in candidate.items():
        baseline=old.get(field)
        if not equal_value(baseline,value):raise ValueError('Compatibility field changed')
        # Use the source value, preserving the legacy serialized numeric type/scale.
        if isinstance(baseline,str) and value is not None:
            try:
                reference=Decimal(baseline);number=Decimal(str(value))
                value=format(number.quantize(Decimal(1).scaleb(reference.as_tuple().exponent)),'f')
            except InvalidOperation:value=str(value)
        elif isinstance(baseline,int) and not isinstance(baseline,bool):value=int(value)
        elif isinstance(baseline,float):value=float(value)
        result[field]=value
    return result,True


def main():
    start=perf_counter();frozen,meta=load();db=open_ledger(TARGET)
    head=db.execute("SELECT value FROM state WHERE key='published_release'").fetchone()[0]
    if head!=RELEASE:raise ValueError('Product field extension must be selected')
    manifest=json.loads(db.execute('SELECT manifest FROM release WHERE id=?',(head,)).fetchone()[0])
    with gzip.open(OUT/'object_selector_shadow_plans.json.gz','rt',encoding='utf-8') as f:holds={(r['building_key'],r['asset_type']) for r in json.load(f)}
    with gzip.open(OUT/'named_object_mix_evidence.json.gz','rt',encoding='utf-8') as f:named={(r['building_key'],r['asset_type']):r for r in json.load(f)}
    attrs={};prices={(r['building_key'],r['asset_type']):r for r in frozen['collective']['prices']}
    for r in frozen['collective']['attributes']:
        k=(r['building_key'],r['asset_type'])
        if k not in attrs or r['snapshot_ym']>attrs[k]['snapshot_ym']:attrs[k]=r
    cache={}
    requested={strict_pnu(r['beopjungri_code'],r['lot_number']) for r in frozen['collective']['residential_stats']}
    for r in frozen['built']['transactions']:
        if r['enrichment']:
            pnu=recovered_pnu(r['enrichment']['recovered_lot'],r['transaction']['beopjungri_code'])
            if pnu:
                try:validate_pnu(pnu);requested.add(pnu)
                except ValueError:pass
    requested.discard(None)
    # TEMP is memory-only; the main integrated database remains mode=ro.
    db.execute('PRAGMA temp_store=MEMORY')
    db.execute('CREATE TEMP TABLE requested_parcel(pnu TEXT PRIMARY KEY)')
    db.executemany('INSERT INTO requested_parcel VALUES(?)',[(p,) for p in sorted(requested)])
    for pnu in requested:cache[pnu]=[]
    load_start=perf_counter()
    for pnu,pk,raw,raw_hash in db.execute('''WITH selected AS MATERIALIZED (
        SELECT o.pnu,o.pk,o.raw_hash FROM building_observation o JOIN requested_parcel p ON p.pnu=o.pnu
        WHERE o.release_id=? ORDER BY o.pk)
        SELECT s.pnu,s.pk,v.raw,v.hash FROM selected s CROSS JOIN building_raw v ON v.pk=s.pk AND v.hash=s.raw_hash''',(head,)):
        decoded=json.loads(raw)
        if digest(decoded)!=raw_hash:raise ValueError('Consumed source raw version corrupted')
        cache[pnu].append({'pk':pk,'row':product_row(decoded['product_fields'],'2026-07'),
                           'source_identity_status':'canonical_address'})
    load_seconds=perf_counter()-load_start
    def titles(pnu):
        return cache.get(pnu,[])
    residential=[];comparisons=Counter();field_diffs=Counter();price_counts=Counter()
    for stats in frozen['collective']['residential_stats']:
        k=(stats['building_key'],stats['asset_type']);old=attrs.get(k);old_price=prices.get(k)
        pnu=strict_pnu(stats['beopjungri_code'],stats['lot_number'])
        rows=[r['row'] for r in titles(pnu) if r['row']['ledger_kind']=='집합']
        candidate=projected_attributes(rows,k[1]) if rows and k[1]!='presale' else None
        differences=[field for field in FIELDS if old and candidate and not equal_value(old.get(field),candidate[field])]
        if not old:status='no_existing_attribute_row'
        elif old['match_rule']!='title_pnu':status='retain_existing_non_title_pnu_source'
        elif old['snapshot_ym']!='202607':status='different_title_snapshot_not_comparable'
        elif candidate is None:status='latest_source_candidate_missing'
        else:status='title_numeric_changed' if differences else 'title_numeric_equal'
        comparisons[status]+=1
        if status=='title_numeric_changed':field_diffs.update(differences)
        gated=k in holds or not named[k]['stored_stats_address_observed']
        compatible,source_fed=compatibility_attributes(old,candidate,status,gated)
        # Preserve compatibility input. Candidate numeric substitution is isolated
        # as an audit scenario, never an approved new product attribute.
        replay=candidate_replay(old,candidate,status,gated)
        source_price=None
        if old_price:
            rep=old_price['representative_pnu']
            source_price=db.execute('SELECT price_year,raw_price,status FROM price_observation WHERE release_id=? AND pnu=?',(head,rep)).fetchone()
            from compare_cheongju_integrated_product_supply import compare_price
            pc=compare_price(old_price,dict(zip(('price_year','raw_price','status'),source_price)) if source_price else None)
        else:pc='no_existing_price'
        price_counts[pc]+=1
        price=old_price['assessed_land_price'] if old_price else None
        compatible_price=source_price[1] if pc=='same_year_equal' else price
        residential.append({'stats':stats,'legacy_attributes':old,'compatible_attributes':compatible,'candidate_replay_attributes':replay,
            'legacy_price':price,'compatible_price':compatible_price,'comparison':status,'different_fields':differences,
            'compatible_title_values_from_integrated_source':source_fed,
            'review_hold':gated,'new_representative_pnu':None,'production_apply':False,
            'title_candidate':value_contract(candidate,manifest['sources']['title'],None,'legacy_aggregation_replay_membership_unverified',head if rows else None),
            'retained_attributes':value_contract(old,{'table':'collective_building_attributes','baseline_sha256':meta['content_sha256']},old['snapshot_ym'] if old else None,'frozen_existing_product_input',meta['frozen_at']),
            'effective_attributes':value_contract(compatible,{'baseline_sha256':meta['content_sha256'],
                'title_source':manifest['sources']['title'] if source_fed else None,'title_fields':list(FIELDS) if source_fed else []},
                old['snapshot_ym'] if old else None,'legacy_match_equal_value_source_replay' if source_fed else 'frozen_existing_product_input',head if source_fed else meta['frozen_at']),
            'price_comparison':pc})
    built=[];built_counts=Counter();built_diffs=Counter()
    for r in frozen['built']['transactions']:
        tx,e=r['transaction'],r['enrichment'];pnu=None
        if e:
            derived=recovered_pnu(e['recovered_lot'],tx['beopjungri_code'])
            if derived:
                try:validate_pnu(derived);pnu=derived
                except ValueError:pass
        candidates=titles(pnu)
        status='no_legacy_recovered_address' if not e else 'invalid_legacy_recovered_identity' if not pnu else 'no_latest_title_candidate' if not candidates else 'single_latest_title_candidate' if len(candidates)==1 else 'multiple_latest_title_candidates'
        built_counts[status]+=1
        compared=[]
        for c in candidates:
            from parcel_master.title_fill import parse_year
            row=c['row'];values={'max_floor':row['floors_above'],'approve_year':parse_year(row['approve_date']),
                               'structure_group':built_structure_group(row['structure_name'])}
            diff=[field for field in values if not equal_value(e.get(field),values[field])]
            built_diffs.update(diff)
            compared.append({'management_pk':c['pk'],'values':values,'different_fields':diff,'membership_verified':False})
        built.append({'transaction':tx,'legacy_enrichment':e,'compatible_enrichment':copy.deepcopy(e),
                      'candidate_status':status,'candidate_comparisons':value_contract(compared,manifest['sources']['title'],None,'latest_coaddress_not_historical_membership',head if candidates else None),
                      'new_building_pk':None,'production_apply':False})
    checks={'1471_residential_keys_preserved':len(residential)==1471,
            '13293_built_hashes_preserved':len(built)==13293 and len({r['transaction']['transaction_hash'] for r in built})==13293,
            'all_existing_attributes_preserved':all(r['legacy_attributes']==r['compatible_attributes'] for r in residential),
            'all_existing_prices_preserved':all(equal_value(r['legacy_price'],r['compatible_price']) for r in residential),
            'all_existing_built_enrichment_preserved':all(r['legacy_enrichment']==r['compatible_enrichment'] for r in built),
            'holds_never_substituted':all(r['legacy_attributes']==r['candidate_replay_attributes'] for r in residential if r['review_hold']),
            'numeric_differences_all_in_existing_holds':all(r['review_hold'] for r in residential if r['comparison']=='title_numeric_changed'),
            'no_new_assignment':all(r['new_building_pk'] is None for r in built) and all(r['new_representative_pnu'] is None for r in residential),
            'commercial_306_3987_preserved':len(frozen['collective']['commercial_stats'])==306 and len(frozen['collective']['commercial_transactions'])==3987}
    if not all(checks.values()):raise AssertionError(checks)
    paired={'published_release':head,'baseline_sha256':meta['content_sha256'],'residential':residential,'built':built,
            'commercial_stats':frozen['collective']['commercial_stats'],'commercial_transactions':frozen['collective']['commercial_transactions']}
    path=OUT/'product_numeric_supply_shadow.json.gz'
    write_gzip_atomic(path,paired)
    report={'published_release':head,'baseline_sha256':meta['content_sha256'],'paired_content_sha256':digest(paired),'gzip_sha256':file_hash(path),
            'residential_attribute_comparisons':dict(comparisons),'title_numeric_changed_by_field':dict(field_diffs),
            'price_comparisons':dict(price_counts),'review_hold_keys':sum(r['review_hold'] for r in residential),
            'candidate_replay_substitutions':sum(r['legacy_attributes']!=r['candidate_replay_attributes'] for r in residential),
            'compatible_title_source_keys':sum(r['compatible_title_values_from_integrated_source'] for r in residential),
            'title_numeric_changed_in_review_holds':sum(r['review_hold'] and r['comparison']=='title_numeric_changed' for r in residential),
            'built_candidate_statuses':dict(built_counts),'built_candidate_field_differences':dict(built_diffs),
            'title_bulk_lookup':{'requested_parcels':len(requested),'title_rows':sum(map(len,cache.values())),'seconds':load_seconds,
                                 'mode':'read-only main DB and in-memory TEMP scope; one ordered title payload query','consumed_raw_hashes_verified':True},
            'built_title_candidate_comparisons':sum(len(r['candidate_comparisons']['value']) for r in built),
            'checks':checks,'elapsed_seconds':perf_counter()-start,
            'limitations':['Candidate aggregate uses the existing product algorithm for audit only, not independent site/membership certification.',
                           'K-apt and other existing numeric attributes pass through frozen product inputs; they are not re-sourced from title originals.',
                           'Built legacy PKs may be absent; single current candidate never implies historical transaction membership.',
                           'Compatibility preserves baseline values; candidate replay is separate and subject to review holds.',
                           'Commercial road-cluster inputs preserved without residential title aggregation.']}
    db.close();write_json_atomic(LAB/'cheongju_numeric_supply_shadow.json',report)
    print(json.dumps(report,ensure_ascii=True))


if __name__=='__main__':main()
