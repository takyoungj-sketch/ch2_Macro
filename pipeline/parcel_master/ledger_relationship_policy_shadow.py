"""Proposed relationship gates. Shadow-only; no production writes."""
from audit_cheongju_product_link_candidates import address_pnu


def representative_shadow(address_groups, baseline_pnu, stats_pnu):
    observed={address_pnu(r['beopjungri_code'],r['lot_number']) for r in address_groups}
    observed.discard(None)
    reasons=[]
    if stats_pnu not in observed: reasons.append('stats_address_pair_not_observed')
    if baseline_pnu not in observed: reasons.append('baseline_address_not_observed_in_window')
    if len(observed)>1: reasons.append('multiple_observed_address_pairs')
    return {'status':'review_required' if reasons else 'single_observed_address_candidate',
            'observed_pnu_candidates':sorted(observed),'reasons':reasons,
            'baseline_pnu':baseline_pnu,'new_representative_assignment':None,
            'independent_verification':'unverified'}


def aggregation_gate(membership_confirmed, identities_confirmed, same_snapshot, unique_members, metric_scopes_confirmed):
    conditions={'membership_unverified':membership_confirmed,'identity_unverified':identities_confirmed,
                'mixed_snapshot':same_snapshot,'duplicate_members':unique_members,
                'metric_scope_unverified':metric_scopes_confirmed}
    reasons=[reason for reason,passed in conditions.items() if not passed]
    return {'aggregate_allowed':not reasons,'reasons':reasons}
