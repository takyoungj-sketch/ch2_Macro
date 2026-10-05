"""Read-only admission of explicit Building HUB relations; never certify trades.

Input is a list of bundles: {endpoint, query, pages}. Each page is the original
JSON response (with or without the outer `response` wrapper). Queries contain
public address filters only; credentials are neither accepted nor persisted.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

VERSION = 'building_hub_relation_source_v1'
NAMESPACE = 'building_hub_api_1613000'
ENDPOINTS = {'getBrBasisOulnInfo', 'getBrAtchJibunInfo'}
FILTERS = {'sigunguCd', 'bjdongCd', 'platGbCd', 'bun', 'ji'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def text(row, field):
    value = row.get(field, '')
    if not isinstance(value, str):
        raise ValueError(f'{field}: original string required')
    return value.strip()


def integer(value):
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]+', str(value)):
        raise ValueError('Nonnegative integer required')
    return int(value)


def address(row, prefix=''):
    def field(name):
        return prefix + name[0].upper() + name[1:] if prefix else name
    names = ('sigunguCd', 'bjdongCd', 'platGbCd', 'bun', 'ji')
    raw = {name: text(row, field(name)) for name in names}
    gb = raw['platGbCd']
    result = {'raw': raw, 'pnu': None, 'land_type': {'0': 'land', '1': 'mountain', '2': 'block'}.get(gb, 'unknown')}
    if gb == '2':
        result['status'] = 'block_without_canonical_pnu'
    elif gb not in ('0', '1'):
        result['status'] = 'unknown_land_type'
    elif (not re.fullmatch(r'[0-9]{5}', raw['sigunguCd'])
          or not re.fullmatch(r'[0-9]{5}', raw['bjdongCd'])
          or not re.fullmatch(r'[0-9]{1,4}', raw['bun'])
          or not re.fullmatch(r'[0-9]{1,4}', raw['ji'])
          or int(raw['bun']) == 0):
        result['status'] = 'invalid_or_missing_parcel_fields'
    else:
        result['pnu'] = raw['sigunguCd'] + raw['bjdongCd'] + ('1' if gb == '0' else '2') + raw['bun'].zfill(4) + raw['ji'].zfill(4)
        result['status'] = 'canonical_parcel_observed'
    return result


def read_bundle(bundle):
    if set(bundle) != {'endpoint', 'query', 'pages'} or bundle['endpoint'] not in ENDPOINTS:
        raise ValueError('Expected public endpoint, query and original pages')
    query = bundle['query']
    if not isinstance(query, dict) or set(query) - FILTERS or not {'sigunguCd', 'bjdongCd'} <= set(query):
        raise ValueError('Public address query required; no credentials allowed')
    for name, value in query.items():
        width = 5 if name in ('sigunguCd', 'bjdongCd') else 1 if name == 'platGbCd' else 4
        if not isinstance(value, str) or not re.fullmatch(r'[0-9]{' + str(width) + '}', value):
            raise ValueError('Query fields must use official fixed-width codes')
        if name == 'platGbCd' and value not in ('0', '1', '2'):
            raise ValueError('Unknown query land-type code')
    pages = bundle['pages']
    if not isinstance(pages, list) or not pages:
        raise ValueError('At least one original response required')
    rows = []; seen = set(); totals = set(); sizes = set(); counts = {}
    for page in pages:
        response = page.get('response', page)
        header, body = response['header'], response['body']
        if str(header['resultCode']) not in ('00', '0'):
            raise ValueError('API response did not succeed')
        number, size, total = (integer(body[k]) for k in ('pageNo', 'numOfRows', 'totalCount'))
        if number < 1 or size < 1 or number in seen:
            raise ValueError('Invalid or duplicate page')
        seen.add(number); totals.add(total); sizes.add(size)
        items = body.get('items')
        items = items.get('item', []) if isinstance(items, dict) else [] if items in ('', None) else items
        if isinstance(items, dict): items = [items]
        if not isinstance(items, list) or any(not isinstance(r, dict) for r in items):
            raise ValueError('Invalid API items')
        counts[number] = len(items)
        for row in items:
            if any(text(row, k) != v for k, v in query.items()):
                raise ValueError('Response row outside requested address scope')
        rows.extend(items)
    if len(totals) != 1 or len(sizes) != 1:
        raise ValueError('Pagination metadata changed during collection')
    total, size = totals.pop(), sizes.pop()
    needed = max(1, (total + size - 1) // size)
    if seen != set(range(1, needed + 1)) or len(rows) != total:
        raise ValueError('Incomplete response pages')
    if any(counts[n] != max(0, min(size, total - (n - 1) * size)) for n in seen):
        raise ValueError('Unexpected page row count')
    identities = [text(r, 'mgmBldrgstPk') if bundle['endpoint'] == 'getBrBasisOulnInfo' else digest(r) for r in rows]
    if len(set(identities)) != len(identities):
        raise ValueError('Duplicate source row within one query')
    return rows, {'endpoint': bundle['endpoint'], 'query': query, 'pages': needed,
                  'rows': total, 'response_bundle_sha256': digest(bundle)}


def admit_relations(bundles, observed_at):
    stamp = datetime.fromisoformat(observed_at.replace('Z', '+00:00'))
    if stamp.tzinfo is None: raise ValueError('Observation time needs timezone')
    if not isinstance(bundles, list) or not bundles:
        raise ValueError('At least one source bundle required')
    basis = {}; attached = []; sources = []
    for bundle in bundles:
        rows, provenance = read_bundle(bundle); sources.append(provenance)
        for row in rows:
            pk = text(row, 'mgmBldrgstPk')
            if not pk: raise ValueError('Missing ledger PK')
            if bundle['endpoint'] == 'getBrBasisOulnInfo':
                if pk in basis and basis[pk] != row: raise ValueError('Conflicting basic rows for one PK')
                basis[pk] = dict(row)
            else:
                attached.append(dict(row))
    parents = {pk: text(row, 'mgmUpBldrgstPk') for pk, row in basis.items()}
    for start in parents:
        path = set(); node = start
        while node in parents and parents[node]:
            if node in path: raise ValueError('Cyclic ledger parent relation')
            path.add(node); node = parents[node]
    relations = []
    def emit(kind, pk, target, state, raw):
        relations.append({'relation_kind': kind, 'ledger_pk': pk, 'target': target,
                          'status': state, 'raw_row': raw, 'raw_row_sha256': digest(raw),
                          'valid_from': None, 'valid_to': None,
                          'transaction_membership_verified': False})
    for pk, row in sorted(basis.items()):
        parent = parents[pk]
        if parent:
            emit('ledger_parent', pk, {'ledger_pk': parent},
                 'explicit_parent_resolved_in_batch' if parent in basis else 'explicit_parent_target_missing', row)
    unique_attached = {digest(r): r for r in attached}
    for _, row in sorted(unique_attached.items()):
        pk = text(row, 'mgmBldrgstPk'); target = address(row, 'atch')
        if pk in basis and address(row)['raw'] != address(basis[pk])['raw']:
            raise ValueError('Conflicting ledger address across source endpoints')
        state = ('explicit_additional_parcel_resolved_in_batch' if pk in basis and target['pnu']
                 else 'additional_parcel_identity_hold' if not target['pnu'] else 'additional_parcel_ledger_missing')
        emit('additional_parcel', pk, target, state, row)
    return {'version': VERSION, 'pk_namespace': NAMESPACE, 'observed_at': observed_at,
            'sources': sorted(sources, key=digest), 'basis_rows': len(basis), 'relations': relations,
            'ledger_nodes': [{'ledger_pk': pk, 'address': address(row), 'raw_row': row,
                              'raw_row_sha256': digest(row)} for pk, row in sorted(basis.items())],
            'old_txt_pk_mapping_applied': False, 'production_apply': False,
            'membership_verified': False, 'representative_selected': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--observed-at', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = admit_relations(json.loads(args.input.read_text(encoding='utf-8')), args.observed_at)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__': main()
