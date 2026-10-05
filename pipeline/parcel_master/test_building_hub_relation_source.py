import copy
import unittest

from building_hub_relation_source import admit_relations, address, read_bundle
from prepare_cheongju_hub_relation_queries import prepare_queries


STAMP = '2026-10-05T12:00:00+09:00'


def row(pk='child', parent='parent'):
    return {'mgmBldrgstPk': pk, 'mgmUpBldrgstPk': parent, 'sigunguCd': '43111',
            'bjdongCd': '12000', 'platGbCd': '0', 'bun': '0012', 'ji': '0000'}


def bundle(rows, endpoint='getBrBasisOulnInfo', size=None):
    size = size or max(1, len(rows))
    pages = []
    for n in range(max(1, (len(rows) + size - 1) // size)):
        items = rows[n * size:(n + 1) * size]
        pages.append({'response': {'header': {'resultCode': '00'}, 'body': {
            'pageNo': n + 1, 'numOfRows': size, 'totalCount': len(rows),
            'items': {'item': items}}}})
    return {'endpoint': endpoint, 'query': {'sigunguCd': '43111', 'bjdongCd': '12000'}, 'pages': pages}


def attached(gb='0'):
    return {**row(), 'atchSigunguCd': '43111', 'atchBjdongCd': '12000',
            'atchPlatGbCd': gb, 'atchBun': '0034', 'atchJi': '0005'}


class RelationSourceTests(unittest.TestCase):
    def test_explicit_parent_requires_target_and_never_certifies_transaction(self):
        r = admit_relations([bundle([row(), row('parent', '')])], STAMP)
        self.assertEqual(r['relations'][0]['status'], 'explicit_parent_resolved_in_batch')
        self.assertFalse(r['membership_verified']); self.assertFalse(r['production_apply'])
        self.assertFalse(r['old_txt_pk_mapping_applied'])
        self.assertIsNone(r['relations'][0]['valid_from'])
        self.assertEqual(len(r['ledger_nodes']), 2)
        self.assertEqual(r['ledger_nodes'][1]['raw_row']['mgmBldrgstPk'], 'parent')

    def test_missing_parent_target_is_retained_on_hold(self):
        r = admit_relations([bundle([row()])], STAMP)
        self.assertEqual(r['relations'][0]['status'], 'explicit_parent_target_missing')

    def test_coaddress_without_explicit_parent_does_not_make_relation(self):
        r = admit_relations([bundle([row('one', ''), row('two', '')])], STAMP)
        self.assertEqual(r['relations'], [])

    def test_additional_parcel_uses_attached_fields_not_base_address(self):
        r = admit_relations([bundle([row('child', '')]), bundle([attached()], 'getBrAtchJibunInfo')], STAMP)
        rel = r['relations'][0]
        self.assertEqual(rel['target']['pnu'], '4311112000100340005')
        self.assertEqual(rel['status'], 'explicit_additional_parcel_resolved_in_batch')
        self.assertFalse(rel['transaction_membership_verified'])

    def test_additional_parcel_needs_ledger_target(self):
        r = admit_relations([bundle([attached()], 'getBrAtchJibunInfo')], STAMP)
        self.assertEqual(r['relations'][0]['status'], 'additional_parcel_ledger_missing')

    def test_block_code_has_confirmed_meaning_but_no_canonical_pnu(self):
        r = admit_relations([bundle([row()]), bundle([attached('2')], 'getBrAtchJibunInfo')], STAMP)
        rel = r['relations'][-1]
        self.assertEqual(rel['target']['land_type'], 'block'); self.assertIsNone(rel['target']['pnu'])
        self.assertEqual(rel['status'], 'additional_parcel_identity_hold')

    def test_mountain_maps_to_pnu_land_digit_two(self):
        self.assertEqual(address(attached('1'), 'atch')['pnu'], '4311112000200340005')

    def test_missing_invalid_or_unknown_fields_never_generate_pnu(self):
        for field, value in [('atchJi', ''), ('atchBun', '0000'), ('atchBun', '10000'),
                             ('atchPlatGbCd', '9'), ('atchBjdongCd', '1200')]:
            with self.subTest(field=field, value=value):
                x = attached(); x[field] = value
                self.assertIsNone(address(x, 'atch')['pnu'])

    def test_cycle_and_self_parent_rejected(self):
        for rows in ([row('a', 'a')], [row('a', 'b'), row('b', 'a')]):
            with self.assertRaisesRegex(ValueError, 'Cyclic'): admit_relations([bundle(rows)], STAMP)

    def test_conflicting_pk_payload_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            admit_relations([bundle([row()]), bundle([row(parent='other')])], STAMP)

    def test_duplicate_rows_cannot_disguise_complete_pagination(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate source'):
            read_bundle(bundle([row(), row()], size=1))

    def test_matching_pk_with_conflicting_base_address_is_rejected(self):
        x = attached(); x['bun'] = '0099'
        with self.assertRaisesRegex(ValueError, 'Conflicting ledger address'):
            admit_relations([bundle([row()]), bundle([x], 'getBrAtchJibunInfo')], STAMP)

    def test_no_source_bundle_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'source bundle'): admit_relations([], STAMP)

    def test_incomplete_or_duplicate_pages_rejected(self):
        b = bundle([row('a'), row('b')], size=1)
        for pages in (b['pages'][:1], [b['pages'][0], b['pages'][0]]):
            with self.assertRaises(ValueError): read_bundle({**b, 'pages': pages})

    def test_changed_counts_and_page_row_distribution_rejected(self):
        b = bundle([row('a'), row('b')], size=1)
        b['pages'][1]['response']['body']['totalCount'] = 3
        with self.assertRaises(ValueError): read_bundle(b)
        b = bundle([row('a'), row('b')], size=1)
        b['pages'][0]['response']['body']['items']['item'].append(row('b'))
        b['pages'][1]['response']['body']['items']['item'] = []
        with self.assertRaises(ValueError): read_bundle(b)

    def test_out_of_scope_and_credentials_rejected(self):
        b = bundle([row()]); b['query']['serviceKey'] = 'not-a-real-key'
        with self.assertRaisesRegex(ValueError, 'credentials'): read_bundle(b)
        b = bundle([row()]); b['query']['bun'] = '9999'
        with self.assertRaisesRegex(ValueError, 'scope'): read_bundle(b)

    def test_api_error_rejected(self):
        b = bundle([row()]); b['pages'][0]['response']['header']['resultCode'] = '30'
        with self.assertRaisesRegex(ValueError, 'succeed'): read_bundle(b)

    def test_single_item_and_empty_success_response(self):
        b = bundle([row()]); b['pages'][0]['response']['body']['items']['item'] = row()
        self.assertEqual(len(read_bundle(b)[0]), 1)
        b = bundle([]); b['pages'][0]['response']['body']['items'] = ''
        self.assertEqual(read_bundle(b)[0], [])

    def test_replay_input_immutability_and_order_independence(self):
        bs = [bundle([row(), row('parent', '')]), bundle([attached()], 'getBrAtchJibunInfo')]
        before = copy.deepcopy(bs); r = admit_relations(bs, STAMP)
        self.assertEqual(bs, before); self.assertEqual(admit_relations(list(reversed(bs)), STAMP), r)
        bs[0]['pages'][0]['response']['body']['items']['item'].reverse()
        # Source hashes retain raw page order; relation decisions remain deterministic.
        self.assertEqual(admit_relations(bs, STAMP)['relations'], r['relations'])

    def test_observation_time_must_have_timezone(self):
        with self.assertRaisesRegex(ValueError, 'timezone'): admit_relations([bundle([])], '2026-10-05')

    def test_query_manifest_deduplicates_scopes_and_keeps_candidate_refs(self):
        def plan(stats):
            return {'stats_id': stats, 'building_key': str(stats), 'asset_type': 'apartment',
                    'new_representative_pnu': None, 'production_apply': False,
                    'candidates': [{'address_identity': ['pnu', '4311112000100340005']}]}
        r = prepare_queries([plan(1), plan(2)])
        self.assertEqual(r['unique_address_scopes'], 1); self.assertEqual(len(r['queries']), 2)
        self.assertEqual(len(r['queries'][0]['candidate_refs']), 2)
        self.assertEqual(r['queries'][0]['query']['bun'], '0034')
        self.assertFalse(r['requests_executed'])

    def test_raw_block_query_does_not_guess_pnu_or_land_type(self):
        p = {'stats_id': 1, 'building_key': '1', 'asset_type': 'presale',
             'new_representative_pnu': None, 'production_apply': False,
             'candidates': [{'address_identity': ['raw', '4311112000', 'BL-B1']}]}
        r = prepare_queries([p])
        self.assertEqual(r['queries'][0]['query'], {'sigunguCd': '43111', 'bjdongCd': '12000'})
        self.assertEqual(len(r['raw_address_candidates']), 1)


if __name__ == '__main__': unittest.main()
