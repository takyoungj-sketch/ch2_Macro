"""Rehearse receipt/stage/publication/restore with real historical 4,000-PK inputs."""
import hashlib
import json
from pathlib import Path
from time import perf_counter

from integrated_ledger_v2 import consumer,encode
from ledger_consumer_input_preview import OUT,LAB
from ledger_operations import Operations,read_json
from ledger_release_cli import open_ledger
from ledger_supply_bundle import sha
from ledger_supply_artifacts import write_json_atomic
from ledger_product_transition import inspect


def output_digest(path):
    db=open_ledger(path);h=hashlib.sha256()
    try:
        for pk, in db.execute('SELECT pk FROM current_building ORDER BY pk'):
            h.update(encode(consumer(db,pk)).encode());h.update(b'\n')
    finally:db.close()
    return h.hexdigest()


def main():
    started=perf_counter();source=OUT/'integrated_ledger_v2_4000.sqlite';source_sha=sha(source)
    report_path=LAB/'cheongju_ledger_operations_rehearsal.json'
    prior=read_json(report_path) if report_path.exists() else None
    ops=Operations(OUT/'operations_rehearsal_v1');checks={};stages=[];digests={}
    releases=[('ops-4000-2024-09','cheongju-4000-2024-09-identity-2.2'),
              ('ops-4000-2025-07','cheongju-4000-2025-07-identity-2.2'),
              ('ops-4000-2026-07','cheongju-4000-2026-07-identity-2.2')]
    try:
        # Re-running an already complete rehearsal verifies immutable publications.
        existing={r[0] for r in ops.db.execute('SELECT id FROM publication')}
        for batch,release in releases:
            path=ops.export_package(source,release,batch)
            before=ops.state()
            if batch not in existing and batch==releases[-1][0]:
                for phase in ('sources','traits','buildings','published'):
                    try:ops.stage(path,fail_at=phase)
                    except RuntimeError:pass
                    else:raise AssertionError('Injected staging failure did not occur')
                    checks['stage_failure_'+phase+'_preserves_pointer']=ops.state()==before
            stage=ops.stage(path);stages.append(stage)
            checks[batch+'_stage_no_pointer_change']=ops.state()==before
            checks[batch+'_stage_replay_equal']=ops.stage(path)==stage
            if batch not in existing:
                before=ops.state()
                if batch==releases[-1][0]:
                    try:ops.publish(batch,stage['impact_sha256'],before['revision'],fail_at='pointer')
                    except RuntimeError:pass
                    else:raise AssertionError('Injected publication failure did not occur')
                    checks['publication_failure_preserves_pointer']=ops.state()==before
                ops.publish(batch,stage['impact_sha256'],before['revision'])
            # Immutable databases can be compared without changing their selected release.
            digests[batch]=output_digest(ops.root/'candidates'/batch/'ledger.sqlite')
            checks[batch+'_staged_artifacts_unchanged']=ops.verify_stage(batch)==stage
            print('Validated historical operations batch',batch,flush=True)
        oldest,latest=releases[0][0],releases[-1][0]
        before=ops.state()
        try:ops.restore(oldest,before['revision'],fail_at='pointer')
        except RuntimeError:pass
        else:raise AssertionError('Injected restore failure did not occur')
        checks['restore_failure_preserves_pointer']=ops.state()==before
        ops.restore(oldest,ops.state()['revision'])
        state,active=ops.active();checks['oldest_consumer_output_restored']=output_digest(active['path'])==digests[oldest]
        blocked=ops.export_package(source,releases[-1][1],'blocked-after-restore')
        try:ops.stage(blocked)
        except ValueError:checks['append_from_restored_old_head_rejected']=True
        else:raise AssertionError('Old restored head accepted a new publication')
        ops.restore(latest,ops.state()['revision'])
        state,active=ops.active();checks['latest_consumer_output_restored']=output_digest(active['path'])==digests[latest]
        before=ops.state();checks['publication_replay_no_pointer_change']=ops.publish(latest,stages[-1]['impact_sha256'],stages[-1]['expected_revision']) is False and ops.state()==before
        checks['original_integrated_4000_database_unchanged']=sha(source)==source_sha
        checks['registry_foreign_keys_clean']=not ops.db.execute('PRAGMA foreign_key_check').fetchall()
        checks['registry_integrity']=ops.db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
        gate=inspect();checks['product_transition_remains_blocked']=gate['status']=='blocked'
        if not all(checks.values()):raise AssertionError(checks)
        impacts=[read_json(ops.root/'candidates'/batch/'impact.json') for batch,_ in releases]
        report={'rehearsal':'historical-4000-source-operations-v1','actual_future_source_update_tested':False,
                'source_database_sha256':source_sha,'batches':impacts,'checks':checks,'active_state':ops.state(),
                'immutable_consumer_output_sha256':digests,'publication_events':ops.db.execute('SELECT action,previous_id,next_id,revision FROM event ORDER BY id').fetchall(),
                'stage_receipts':[{'batch_id':s['batch_id'],'database_sha256':s['database_sha256'],'impact_sha256':s['impact_sha256'],'package_sha256':s['package_sha256']} for s in stages],
                'product_transition_gate':gate,'elapsed_seconds':perf_counter()-started,'production_apply':False,
                'immutable_database_bytes':{batch:(ops.root/'candidates'/batch/'ledger.sqlite').stat().st_size for batch,_ in releases},
                'implementation_sha256':{name:sha(Path(__file__).with_name(name)) for name in (
                    'ledger_operations.py','ledger_operations_cli.py','ledger_product_transition.py',
                    'run_cheongju_ledger_operations_rehearsal.py','integrated_ledger_v2.py','run_cheongju_integrated_ledger_city.py')},
                'limitations':['Real three historical 4,000-PK input releases exported from already verified ledger; not a future month ingestion.',
                               'Normalized JSON/gzip intake verified; original nationwide raw files are not re-extracted by this operational wrapper.',
                               'Separate immutable research databases and registry, not a live product supply switch.']}
        history=[] if prior is None else prior.get('execution_records',[{'checks':prior['checks'],'active_state':prior['active_state'],
                                          'elapsed_seconds':prior['elapsed_seconds'],'source_database_sha256':prior['source_database_sha256']}])
        report['execution_records']=history+[{'checks':checks,'active_state':ops.state(),'elapsed_seconds':report['elapsed_seconds'],
                      'source_database_sha256':source_sha,'implementation_sha256':report['implementation_sha256']}]
        write_json_atomic(report_path,report)
        write_json_atomic(LAB/'cheongju_product_transition_gate.json',gate)
        print(json.dumps({'checks':checks,'active_state':ops.state(),'product_transition_blockers':gate['blockers'],'elapsed_seconds':report['elapsed_seconds']},ensure_ascii=True))
    finally:ops.close()


if __name__=='__main__':main()
