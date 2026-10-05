"""Candidate preservation and review gates, before a membership verifier exists.

This pilot never selects a representative or inherits enrichment. A caller's
`membership_verified` label is deliberately rejected until a source-specific
verifier is implemented. There is no production database dependency.
"""
import hashlib
import json
import re
from copy import deepcopy
from collections import defaultdict

from audit_cheongju_product_link_candidates import address_pnu

VERSION = 'ledger-object-selector-shadow-v1'
GROUP_FIELDS = ('stats_id','building_key','asset_type','beopjungri_code','lot_number',
                'building_name','addr1','addr2','addr3','addr4','road_name')


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()


def raw_pair(group):
    return [str(group['beopjungri_code'] or ''),str(group['lot_number'] or '')]


def select_shadow(row, baseline_stats_address, coverage, analysis_unit='named_residential_object'):
    if analysis_unit=='road_cluster':
        return {'rule_version':VERSION,'analysis_unit':analysis_unit,'status':'keep_existing_cluster_identity',
                'production_apply':False,'residential_scope_rules_applied':False}
    if analysis_unit!='named_residential_object': raise ValueError('Unsupported pilot analysis unit')
    if row['decision']['independent_membership_verification']!='unverified':
        raise ValueError('Source-specific membership verifier is not implemented; caller status cannot certify membership')
    candidates=[]; seen_partitions=set(); seen_groups=set(); total=0
    for partition in row['address_review_partitions']:
        identity=tuple(partition['address_identity'])
        if identity in seen_partitions: raise ValueError('Duplicate address partition')
        seen_partitions.add(identity)
        groups=partition['address_groups']
        if not groups: raise ValueError('Empty observation partition')
        count=0; pairs=defaultdict(int); normalized_pnus=set()
        for group in groups:
            if group['building_key']!=row['building_key'] or group['asset_type']!=row['asset_type'] or group['stats_id']!=row['stats_id']:
                raise ValueError('Observation belongs to another product key, asset or window')
            key=tuple(group[k] for k in GROUP_FIELDS)
            if key in seen_groups: raise ValueError('Duplicate transaction address/name group')
            seen_groups.add(key)
            n=group['transactions']
            if not isinstance(n,int) or isinstance(n,bool) or n<=0: raise ValueError('Invalid grouped transaction count')
            pair=raw_pair(group); pnu=address_pnu(*pair)
            expected=('pnu',pnu) if pnu else ('raw',pair[0].strip(),pair[1].strip())
            if expected!=identity: raise ValueError('Observation does not support declared address identity')
            count+=n; pairs[tuple(pair)]+=n
            if pnu: normalized_pnus.add(pnu)
        if count!=partition['transactions']: raise ValueError('Partition transaction count mismatch')
        total+=count
        pnu=next(iter(normalized_pnus)) if normalized_pnus else None
        source_status=coverage.get(pnu,'not_reviewed') if pnu else 'address_not_canonical'
        if source_status not in ('titles_present','no_titles_in_latest_snapshot','not_reviewed','address_not_canonical'):
            raise ValueError('Unsupported source coverage status')
        candidates.append({'address_identity':list(identity),'transactions':count,
            'observed_pairs':[{'raw_pair':list(pair),'transactions':n} for pair,n in sorted(pairs.items())],
            'source_coverage_status':source_status,'membership_status':'unverified',
            'new_object_key':None,'new_representative_pnu':None})
    if total!=row['transaction_count']: raise ValueError('Product key transaction count mismatch')
    candidates.sort(key=lambda c:c['address_identity'])
    pnus=sorted(c['address_identity'][1] for c in candidates if c['address_identity'][0]=='pnu')
    if pnus!=sorted(row['observed_pnus']): raise ValueError('Frozen PNU candidate set mismatch')
    observed_pairs={tuple(p['raw_pair']) for c in candidates for p in c['observed_pairs']}
    stats_observed=tuple(baseline_stats_address) in observed_pairs
    if stats_observed!=row['stored_stats_address_observed']: raise ValueError('Stored address observation baseline mismatch')
    raw_count=sum(c['address_identity'][0]=='raw' for c in candidates)
    missing=sum(c['source_coverage_status']=='no_titles_in_latest_snapshot' for c in candidates)
    not_reviewed=sum(c['source_coverage_status']=='not_reviewed' for c in candidates)
    legal_codes={pair[0] for pair in observed_pairs if re.fullmatch(r'[0-9]{10}',pair[0])}
    if len(legal_codes)!=row['distinct_legal_dongs']: raise ValueError('Legal code baseline mismatch')
    reasons=['transaction_object_membership_unverified','representative_selection_rule_pending']
    if raw_count: reasons.append('noncanonical_address_identity')
    if len(legal_codes)>1: reasons.append('named_key_spans_legal_dongs')
    if len(pnus)>1: reasons.append('multiple_observed_parcels_membership_unverified')
    if row['decision']['distinct_kapt_codes']>1: reasons.append('multiple_management_codes_membership_unverified')
    if not stats_observed: reasons.append('stored_stats_address_pair_not_observed')
    if missing: reasons.append('latest_title_source_coverage_missing')
    if not_reviewed: reasons.append('title_source_not_reviewed')
    if raw_count: status='development_block_identity_unresolved'
    elif len(legal_codes)>1 or len(pnus)>1: status='object_scope_review_hold'
    elif row['decision']['distinct_kapt_codes']>1: status='shared_parcel_management_review'
    elif missing or not_reviewed: status='source_coverage_review'
    else: status='observed_only'
    baseline=deepcopy({'stats_address':baseline_stats_address,'price_mart':row['baseline_price_mart'],'attribute_rows':row['existing_attribute_rows']})
    return {'rule_version':VERSION,'analysis_unit':analysis_unit,'building_key':row['building_key'],'asset_type':row['asset_type'],
        'stats_id':row['stats_id'],'status':status,'reasons':reasons,'candidates':candidates,'transactions':total,
        'baseline':baseline,'baseline_content_sha256':digest(baseline),'stored_stats_pair_observed':stats_observed,
        'new_object_key':None,'selected_observed_pair':None,'new_representative_pnu':None,
        'inherited_price_mart':None,'inherited_building_attributes':None,'regression_eligibility':'not_evaluated',
        'membership_verifier_implemented':False,'production_apply':False,'residential_scope_rules_applied':True}
