"""Prepare public query scopes from frozen candidates; makes no API requests."""
import gzip
import json
import re
from pathlib import Path

from building_hub_relation_source import ENDPOINTS, digest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/research/cheongju_ledger'


def prepare_queries(plans):
    scopes = {}; raw = []
    for plan in plans:
        if plan['new_representative_pnu'] is not None or plan['production_apply']:
            raise ValueError('Expected unpromoted frozen shadow plan')
        for candidate in plan['candidates']:
            kind, value, *rest = candidate['address_identity']
            reference = {'stats_id': plan['stats_id'], 'building_key': plan['building_key'],
                         'asset_type': plan['asset_type'], 'address_identity': candidate['address_identity']}
            if kind == 'pnu':
                if rest or not re.fullmatch(r'[0-9]{10}[12][0-9]{8}', value) or int(value[11:15]) == 0:
                    raise ValueError('Invalid candidate PNU')
                query = {'sigunguCd': value[:5], 'bjdongCd': value[5:10],
                         'platGbCd': '0' if value[10] == '1' else '1', 'bun': value[11:15], 'ji': value[15:]}
            elif kind == 'raw':
                if len(rest) != 1 or not re.fullmatch(r'[0-9]{10}', value):
                    raise ValueError('Invalid raw address identity')
                # A transaction BL label does not prove the API land-type code.
                # Use legal-dong scope without inventing a parcel or block filter.
                query = {'sigunguCd': value[:5], 'bjdongCd': value[5:]}
                raw.append(reference)
            else:
                raise ValueError('Unknown candidate identity kind')
            key = digest(query)
            scopes.setdefault(key, {'query': query, 'candidate_refs': []})['candidate_refs'].append(reference)
    queries = []
    for _, scope in sorted(scopes.items()):
        for endpoint in sorted(ENDPOINTS):
            queries.append({'endpoint': endpoint, 'query': scope['query'],
                            'candidate_refs': sorted(scope['candidate_refs'], key=digest)})
    return {'version': 'cheongju_hub_relation_query_manifest_v1', 'requests_executed': False,
            'unique_address_scopes': len(scopes), 'queries': queries,
            'raw_address_candidates': sorted(raw, key=digest), 'membership_verified': False}


def main():
    path = OUT / 'object_selector_shadow_plans.json.gz'
    plans = json.loads(gzip.decompress(path.read_bytes()))
    result = prepare_queries(plans)
    result['source_plan_content_sha256'] = digest(plans)
    target = OUT / 'hub_relation_query_manifest.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'keys': len(plans), 'candidate_partitions': sum(len(p['candidates']) for p in plans),
                      'unique_address_scopes': result['unique_address_scopes'], 'endpoint_queries': len(result['queries']),
                      'raw_address_candidates': len(result['raw_address_candidates']),
                      'plan_content_sha256': result['source_plan_content_sha256'],
                      'manifest_content_sha256': digest(result), 'requests_executed': False}, indent=2))


if __name__ == '__main__': main()
