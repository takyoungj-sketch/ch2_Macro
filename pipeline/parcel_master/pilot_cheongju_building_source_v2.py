"""Re-read original title files for the review cohort and compare to frozen v1."""
import csv
import argparse
import gzip
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import date

from audit_cheongju_relation_source_evidence import ROOT, OUT, LAB, scan_titles, title_path, SNAPSHOTS
from building_source_staging_v2 import connect, ingest, fingerprint, identity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cohort', choices=('review', 'full'), default='review')
    args = parser.parse_args()
    with (OUT/'building_relation_review_queue.csv').open(encoding='utf-8-sig', newline='') as stream:
        queue = list(csv.DictReader(stream))
    pks = {r['mgmt_pk'] for r in queue if r['mgmt_pk']}
    previous_report = json.loads((LAB/'cheongju_relation_source_evidence.json').read_text(encoding='utf-8'))
    expected = {r['snapshot']: r for r in previous_report['raw_inventory'] if r['source']=='title'}
    v1 = sqlite3.connect((OUT/'building_relation_staging.sqlite').resolve().as_uri()+'?mode=ro', uri=True)
    before_v1 = fingerprint_v1(v1)
    if args.cohort == 'full':
        pks = {r[0] for r in v1.execute('SELECT pk FROM building_entity')}
        baseline = json.loads((LAB/'cheongju_building_relation_staging.json').read_text(encoding='utf-8'))
        scope_sha = hashlib.sha256('\n'.join(sorted(pks)).encode()).hexdigest()
        if len(pks) != 4000 or scope_sha != baseline['scope_sha256']:
            raise ValueError('Frozen v1 cohort differs')
    else:
        scope_sha = hashlib.sha256('\n'.join(sorted(pks)).encode()).hexdigest()
    suffix = '_full' if args.cohort == 'full' else ''
    db = connect(OUT/f'building_source_staging_v2{suffix}.sqlite')
    totals = Counter(); batches = []; detail = []; originals = {}; checks = {}; missing = []
    for snapshot in sorted(SNAPSHOTS):
        found, meta = scan_titles(title_path(snapshot), pks)
        if meta['sha256'] != expected[snapshot]['sha256'] or meta['rows'] != expected[snapshot]['rows']:
            raise ValueError('Original source differs from prior evidence')
        if meta['duplicate_target_pks']:
            raise ValueError('Duplicate raw PK')
        records = {pk: values[0] for pk, values in found.items()}
        if args.cohort == 'full':
            for raw in records.values():
                canonical, status = identity(raw['raw_identity_fields'])
                if canonical != raw['pnu']:
                    raw['source_parser_pnu_candidate'] = raw['pnu']
                    raw['pnu'] = canonical
                raw['normalization_status'] = status
        originals[snapshot] = records
        manifest = {'source_sha256':meta['sha256'], 'source_rows':meta['rows'],
                    'expected_records':len(records), 'cohort':'review_queue_pk_all_three_snapshots',
                    'source_file':meta['filename']}
        if args.cohort == 'full':
            manifest.update(cohort='frozen_v1_4000_management_pks', scope_sha256=scope_sha,
                            normalization_rule='cheongju-source-identity-v2.1')
        ingest(db, snapshot, records, manifest)
        before = fingerprint(db)
        checks[snapshot+'_idempotent'] = ingest(db, snapshot, records, manifest) is False and fingerprint(db)==before
        counts = Counter()
        status_counts = Counter(); district_counts = Counter(); role_counts = Counter()
        old_pks = {r[0] for r in v1.execute('SELECT pk FROM building_observation WHERE snapshot=?', (snapshot,))} & pks
        absent = sorted(old_pks-set(records))
        missing.extend({'snapshot':snapshot,'mgmt_pk':pk} for pk in absent)
        for pk, raw in records.items():
            old = v1.execute('SELECT pnu FROM address_relation_observation WHERE snapshot=? AND pk=?', (snapshot,pk)).fetchone()
            if not old:
                category = 'outside_v1_observation'
            elif raw['pnu'] is None:
                category = 'v1_link_withheld_unknown_identity'
                detail.append({'snapshot':snapshot,'mgmt_pk':pk,'v1_pnu':old[0],'raw_identity_fields':raw['raw_identity_fields']})
            elif old[0] == raw['pnu']:
                category = 'canonical_same_as_v1'
            else:
                category = 'canonical_differs_from_v1'
                detail.append({'snapshot':snapshot,'mgmt_pk':pk,'v1_pnu':old[0],'v2_pnu':raw['pnu']})
            counts[category]+=1; totals[category]+=1
            status_counts[identity(raw['raw_identity_fields'])[1]] += 1
            district_counts[raw['raw_identity_fields'][0].strip()] += 1
            role_counts[raw['main_aux_label']] += 1
        batches.append({'snapshot':snapshot,'source_records':len(records),'comparison':dict(counts),
                        'identity_exceptions':sum(r['pnu'] is None for r in records.values()),
                        'v1_observations_missing_in_source':len(absent),'identity_statuses':dict(status_counts),
                        'by_raw_district':dict(district_counts),'by_main_aux_role':dict(role_counts)})
        print('v2 completed',snapshot,len(records),flush=True)
    # Inject a failed new batch and compare every table before/after.
    before = fingerprint(db)
    last = originals['2026-07']
    try:
        ingest(db,'2027-07',last,{'source_sha256':expected['2026-07']['sha256'],'expected_records':len(last)},fail_after=1)
    except RuntimeError:
        pass
    checks['atomic_failure_preserves_all_tables'] = fingerprint(db)==before
    checks['foreign_keys_clean'] = not db.execute('PRAGMA foreign_key_check').fetchall()
    checks['all_raw_versions_preserved'] = all(json.loads(payload)==originals[s][pk] for s,pk,payload in db.execute('SELECT o.snapshot,o.pk,v.raw_payload FROM title_observation o JOIN source_version v ON v.id=o.version'))
    checks['uncertain_identity_has_no_canonical_link'] = db.execute("SELECT COUNT(*) FROM title_observation o JOIN canonical_address_relation r USING(snapshot,pk) WHERE o.identity_status<>'canonical_address'").fetchone()[0]==0
    checks['v1_unchanged'] = fingerprint_v1(v1)==before_v1
    checks['no_confirmed_identity_disagreement'] = totals['canonical_differs_from_v1']==0
    checks['all_v1_observations_found_in_originals'] = not missing
    if not all(checks.values()):
        raise AssertionError(checks)
    with gzip.open(OUT/f'building_source_v2_raw_review{suffix}.json.gz','wt',encoding='utf-8') as stream:
        json.dump({'originals':originals,'comparison_exceptions':detail,'v1_observations_missing_in_source':missing},stream,ensure_ascii=False)
    report = {'run_date':date.today().isoformat(),'cohort_pk_count':len(pks),'review_queue_rows':len(queue),
              'cohort':args.cohort,'scope_sha256':scope_sha,
              'identity_exception_unique_pks':len({pk for rows in originals.values() for pk,raw in rows.items() if raw['pnu'] is None}),
              'batches':batches,'comparison':dict(totals),'checks':checks,
              'table_counts':{t:db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('source_batch','building_entity','source_version','title_observation','canonical_address_relation')},
              'limitations':['Biased review cohort, not the full 4,000-building v1 sample or city-wide coverage.',
                             'Address links only; no inferred parent-child or additional-parcel edges.',
                             'No production updates, historical price migration, or legal event determination.',
                             'Current-view restoration remains in v1; v2 here validates immutable source observations only.']}
    if args.cohort == 'full':
        report['limitations'][0] = 'Frozen 4,000-PK sample deliberately forces address-change cases; not city-wide accuracy or exception-rate estimation.'
        report['normalization_rule'] = 'cheongju-source-identity-v2.1'
    (LAB/f'cheongju_building_source_v2{suffix}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)
    db.close(); v1.close()


def fingerprint_v1(db):
    from building_relation_staging import state_fingerprint
    return state_fingerprint(db)


if __name__=='__main__':
    main()
