"""Replay stored evidence against proposed gates, preserving every baseline."""
import gzip
import hashlib
import json
from collections import Counter
from datetime import date
from ledger_consumer_input_preview import OUT,LAB
from ledger_relationship_policy_shadow import representative_shadow,aggregation_gate


def main():
    path=OUT/'representative_multibuilding_evidence.json.gz'; before=hashlib.sha256(path.read_bytes()).hexdigest()
    with gzip.open(path,'rt',encoding='utf-8') as stream: evidence=json.load(stream)
    traces=[]
    for row in evidence['traces']:
        groups=row['transaction_address_groups']
        replay=(max(str(r['beopjungri_code']).strip() for r in groups)==str(row['beopjungri_code']).strip()
                and max(str(r['lot_number']).strip() for r in groups)==str(row['lot_number']).strip())
        traces.append({'building_key':row['building_key'],
                       'component_max_reproduces_current_stats':replay,
                       'mart_loaded_before_stats_computed':row['loaded_at']<row['computed_at'],
                       **representative_shadow(groups,str(row['representative_pnu']).strip(),row['strict_current_pnu'])})
    groups=[]
    for row in evidence['groups']:
        pks=[r['processed']['mgmt_pk'] for r in row['title_records']]
        gate=aggregation_gate(False,not row['raw_identity_conflicts'],True,len(set(pks))==len(pks),False)
        groups.append({'product':row['product'],'product_key':row['product_key'],
                       'composition':row['composition'],'gate':gate,'new_aggregate':None})
    checks={'no_representative_assignment':all(r['new_representative_assignment'] is None for r in traces),
            'all_unverified_groups_blocked':all(not r['gate']['aggregate_allowed'] and r['new_aggregate'] is None for r in groups),
            'component_max_replayed_for_all_conflicts':all(r['component_max_reproduces_current_stats'] for r in traces),
            'prior_evidence_unchanged':hashlib.sha256(path.read_bytes()).hexdigest()==before}
    if not all(checks.values()): raise AssertionError(checks)
    with gzip.open(OUT/'relationship_policy_shadow.json.gz','wt',encoding='utf-8') as stream:
        json.dump({'representative_decisions':traces,'aggregation_decisions':groups},stream,ensure_ascii=False)
    report={'run_date':date.today().isoformat(),'policy_version':'relationship-gates-draft-v1',
            'representative_decisions':{'review_required':sum(r['status']=='review_required' for r in traces),
                'reasons':dict(Counter(reason for r in traces for reason in r['reasons'])),
                'component_max_reproduced':sum(r['component_max_reproduces_current_stats'] for r in traces),
                'mart_loaded_before_stats_computed':sum(r['mart_loaded_before_stats_computed'] for r in traces)},
            'aggregation_decisions':{'blocked_groups':len(groups),'reasons':dict(Counter(reason for r in groups for reason in r['gate']['reasons']))},
            'evidence_sha256':before,'checks':checks,
            'limitations':['Shadow gate experiment; no real representative assignment or new aggregate.',
                           'Current eligible transaction pairs and stored timestamps do not certify physical identity or historical import execution.']}
    (LAB/'cheongju_relationship_policy_shadow.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))


if __name__=='__main__': main()
