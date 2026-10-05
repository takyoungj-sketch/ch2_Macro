"""Read-only representative-address trace and stratified raw-title group review."""
import gzip
import hashlib
import json
import sys
from collections import Counter,defaultdict
from datetime import date
from sqlalchemy import text
from ledger_consumer_input_preview import ROOT,OUT,LAB
from audit_cheongju_product_link_candidates import address_pnu
from audit_cheongju_relation_source_evidence import scan_titles,scan_summary,title_path,bldrgst_dir,SNAPSHOTS
sys.path.insert(0,str(ROOT/'pipeline'))
from collective.db_utils import get_collective_engine
from parcel_master.db_utils import get_parcel_engine


def read_queries(factory,queries,params):
    engine=factory()
    try:
        if engine.url.host not in ('localhost','127.0.0.1','::1'): raise RuntimeError('Local database required')
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            conn.execute(text("SET LOCAL statement_timeout='60s'"))
            return {name:[dict(r._mapping) for r in conn.execute(text(sql),params)] for name,sql in queries.items()}
    finally: engine.dispose()


def stratified_groups(rows,pnu_field,key_field,limit=5):
    selected=[]
    for district in ('43111','43112','43113','43114'):
        eligible=[r for r in rows if r['candidate_status']=='multiple_title_candidates' and (r[pnu_field] or '').startswith(district)]
        eligible.sort(key=lambda r:hashlib.sha256(str(r[key_field]).encode()).hexdigest())
        selected.extend(eligible[:limit])
    return selected


def group_kind(records):
    roles=Counter(r['main_aux_label'].strip() for r in records)
    main=roles['주건축물']; aux=roles['부속건축물']
    if main and aux: return 'main_and_auxiliary_titles'
    if main>1: return 'multiple_main_titles'
    if aux==len(records) and aux: return 'auxiliary_titles_only'
    return 'other_or_unknown_role_composition'


def main():
    input_path=OUT/'product_link_candidate_review.json.gz'; input_sha=hashlib.sha256(input_path.read_bytes()).hexdigest()
    with gzip.open(input_path,'rt',encoding='utf-8') as stream: original=json.load(stream)
    conflicts=[r for r in original['collective_residential'] if r['pnu_difference_components']]
    keys=[r['building_key'] for r in conflicts]
    latest="""WITH ranked AS (SELECT *,ROW_NUMBER() OVER(PARTITION BY building_key,asset_type ORDER BY as_of_month DESC,window_years DESC) rn
       FROM collective_building_stats WHERE building_key IN (SELECT unnest(CAST(:keys AS text[])))) """
    data=read_queries(get_collective_engine,{
      'latest':latest+"""SELECT s.building_key,s.asset_type,s.as_of_month,s.window_years,s.period_start,s.period_end,s.beopjungri_code,s.lot_number,s.computed_at,
        lp.representative_pnu,lp.assessed_land_price_year,lp.loaded_at
        FROM ranked s JOIN collective_building_assessed_land_price lp USING(building_key,asset_type) WHERE rn=1""",
      'transaction_addresses':latest+"""SELECT t.building_key,t.asset_type,t.beopjungri_code,t.lot_number,t.building_name,
        count(*) AS transactions,min(t.contract_date) first_contract,max(t.contract_date) last_contract
        FROM collective_transactions t JOIN ranked s ON s.building_key=t.building_key AND s.asset_type=t.asset_type AND s.rn=1
        WHERE t.is_valid=true AND t.unit_price>0 AND t.contract_date>=s.period_start AND t.contract_date<=s.period_end
        GROUP BY t.building_key,t.asset_type,t.beopjungri_code,t.lot_number,t.building_name""",
      'stats_history':"""SELECT building_key,asset_type,as_of_month,window_years,beopjungri_code,lot_number,computed_at
        FROM collective_building_stats WHERE building_key IN (SELECT unnest(CAST(:keys AS text[])))""",
      'attributes':"""SELECT building_key,asset_type,snapshot_ym,match_tier,match_rule,danji_code,match_danji_codes,households,dong_count,max_floor
        FROM collective_building_attributes WHERE building_key IN (SELECT unnest(CAST(:keys AS text[])))"""
    },{'keys':keys})
    pnus={p for r in conflicts for p in (r['representative_pnu'],r['strict_latest_stats_pnu']) if p}
    built_sample=stratified_groups(original['built'],'derived_address_pnu','transaction_hash')
    collective_sample=stratified_groups(original['collective_residential'],'lookup_pnu','building_key')
    selected=[{'product':'built','product_key':r['transaction_hash'],'pnu':r['derived_address_pnu']} for r in built_sample]
    selected += [{'product':'collective','product_key':r['building_key'],'pnu':r['lookup_pnu']} for r in collective_sample]
    mountain=[r for r in original['built'] if 'mountain_counterpart_in_latest_title_index' in r['flags']]
    pnus.update(r['pnu'] for r in selected)
    for row in mountain:
        p=row['derived_address_pnu']; pnus.update((p,p[:10]+'2'+p[11:]))
    parcel=read_queries(get_parcel_engine,{
      'buildings':"SELECT mgmt_pk,pnu,ledger_kind,building_name,dong_name,main_purpose,purpose_detail,households,ho_cnt,parking_total,floors_above FROM building WHERE snapshot='2026-07' AND pnu IN (SELECT unnest(CAST(:pnus AS text[])))",
      'prices':"SELECT pnu,price_year,price_per_m2,base_date,snapshot FROM parcel_land_price WHERE pnu IN (SELECT unnest(CAST(:pnus AS text[])))"
    },{'pnus':sorted(pnus)})
    prices=defaultdict(list)
    for r in parcel['prices']: prices[r['pnu']].append(r)
    traces=[]
    for row in data['latest']:
        k=row['building_key']; tx=[r for r in data['transaction_addresses'] if r['building_key']==k and r['asset_type']==row['asset_type']]
        observed={address_pnu(r['beopjungri_code'],r['lot_number']) for r in tx}; observed.discard(None)
        current=address_pnu(row['beopjungri_code'],row['lot_number']); old=str(row['representative_pnu']).strip()
        history={address_pnu(r['beopjungri_code'],r['lot_number']) for r in data['stats_history'] if r['building_key']==k}
        traces.append({**row,'transaction_address_groups':tx,'strict_current_pnu':current,
          'current_address_pair_observed_in_window_transactions':current in observed,
          'mart_address_observed_in_window_transactions':old in observed,'distinct_window_transaction_pnus':len(observed),
          'mart_address_seen_in_stored_stats_history':old in history,
          'current_source_price_rows':prices.get(current,[]),'mart_source_price_rows':prices.get(old,[]),
          'attribute_rows':[r for r in data['attributes'] if r['building_key']==k],
          'interpretation':'no_automatic_representative_switch_or_key_split'})
    print('representative traces collected',len(traces),'group sample',len(selected),flush=True)
    targets={r['mgmt_pk'] for r in parcel['buildings']}
    titles,meta=scan_titles(title_path('2026-07'),targets)
    path=bldrgst_dir()/f'국토교통부_건축물대장_총괄표제부+({SNAPSHOTS["2026-07"]})'/'mart_djy_02.txt'
    summaries,summary_meta=scan_summary(path,pnus)
    frozen=json.loads((LAB/'cheongju_relation_source_evidence.json').read_text(encoding='utf-8'))['raw_inventory']
    for source,new in (('title',meta),('summary',summary_meta)):
        expected=next(r for r in frozen if r.get('snapshot')=='2026-07' and r['source']==source)
        if new['sha256']!=expected['sha256'] or new['rows']!=expected['rows']: raise ValueError('Raw source changed')
    if meta['duplicate_target_pks'] or set(titles)!=targets: raise ValueError('Raw PK missing or duplicated')
    by_pnu=defaultdict(list)
    for processed in parcel['buildings']:
        raw=titles[processed['mgmt_pk']][0]
        by_pnu[processed['pnu']].append({'processed':processed,'raw':raw})
    groups=[]
    for row in selected:
        records=by_pnu[row['pnu']]; raw=[r['raw'] for r in records]
        groups.append({**row,'composition':group_kind(raw),'title_records':records,
          'raw_identity_conflicts':sum(r['pnu']!=row['pnu'] for r in raw),
          'coaddress_summary_records':summaries.get(row['pnu'],[]),
          'aggregation_status':'membership_unverified_do_not_sum','confirmed_parent_links':[]})
    for trace in traces:
        trace['current_title_records']=by_pnu.get(trace['strict_current_pnu'],[])
        trace['mart_title_records']=by_pnu.get(str(trace['representative_pnu']).strip(),[])
    checks={'four_conflicts_traced':len(traces)==4,'all_sample_titles_found_in_raw':set(titles)==targets,
            'no_inferred_parent_links':all(not r['confirmed_parent_links'] for r in groups),
            'prior_candidate_file_unchanged':hashlib.sha256(input_path.read_bytes()).hexdigest()==input_sha}
    if not all(checks.values()): raise AssertionError(checks)
    with gzip.open(OUT/'representative_multibuilding_evidence.json.gz','wt',encoding='utf-8') as stream:
        json.dump({'traces':traces,'groups':groups,'mountain_transactions':mountain,
                   'all_selected_titles':dict(by_pnu),'coaddress_summaries':summaries},stream,ensure_ascii=False,default=str)
    report={'run_date':date.today().isoformat(),'conflict_trace_count':len(traces),
      'conflict_findings':{'current_pair_not_observed_in_eligible_window_transactions':sum(not r['current_address_pair_observed_in_window_transactions'] for r in traces),
                          'mart_pair_observed_in_eligible_window_transactions':sum(r['mart_address_observed_in_window_transactions'] for r in traces),
                          'current_pnu_without_positive_same_year_source_price':sum(not any(p['price_year']==r['assessed_land_price_year'] and p['price_per_m2'] and p['price_per_m2']>0 for p in r['current_source_price_rows']) for r in traces),
                          'mart_pnu_seen_in_stats_history':sum(r['mart_address_seen_in_stored_stats_history'] for r in traces)},
      'multibuilding_sample':{'groups':len(groups),'sampling':'Up to 5 multiple-candidate product keys per district/product; SHA256 order; can repeat same PNU.',
                            'by_product':dict(Counter(r['product'] for r in groups)),
                            'composition':dict(Counter(r['composition'] for r in groups)),
                            'groups_with_coaddress_summary':sum(bool(r['coaddress_summary_records']) for r in groups),
                            'groups_with_identity_conflicts':sum(bool(r['raw_identity_conflicts']) for r in groups)},
      'raw_inventory':[meta,summary_meta],'checks':checks,
      'limitations':['Source address/role observations, not certified danji or transaction membership.',
                     'Separate local read-only snapshots; price source absence does not prove historical import cause.',
                     'Co-address summary is not a confirmed parent; roles/counts alone do not authorize sums.',
                     'Small stratified group review, not city-wide composition proportions.']}
    (LAB/'cheongju_representative_multibuilding.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)


if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('Evidence audit failed:',type(exc).__name__,flush=True); sys.exit(1)
