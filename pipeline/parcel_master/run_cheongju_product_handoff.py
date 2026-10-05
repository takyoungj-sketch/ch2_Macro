"""Publish one frozen city source baseline and build a source-bound shadow handoff."""
import json
from pathlib import Path
from time import perf_counter

from ledger_consumer_input_preview import ROOT,OUT,LAB
from ledger_operations import Operations
from ledger_supply_bundle import sha
from ledger_supply_artifacts import write_json_atomic
from extend_cheongju_product_fields import TARGET,RELEASE
from ledger_product_handoff import build,load
from ledger_product_transition import inspect,conditions


def main():
    started=perf_counter();ops=Operations(OUT/'operations_product_v1');source_before=sha(TARGET)
    report_path=LAB/'cheongju_product_handoff.json'
    previous=json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else None
    source_started=perf_counter();batch='ops-city-2026-07-product-fields'
    try:
        path=ops.export_package(TARGET,RELEASE,batch)
        stage=ops.stage(path)
        ops.publish(batch,stage['impact_sha256'],stage['expected_revision'])
        source_seconds=perf_counter()-source_started
        print('City normalized source baseline published',flush=True)
        identifier='city-handoff-1'
        # Use an independent attempt id; retries never overwrite historical receipts.
        if ops.db.execute("SELECT count(*) FROM sqlite_master WHERE name='product_handoff'").fetchone()[0]:
            identifier='city-handoff-'+str(ops.db.execute('SELECT count(*) FROM product_handoff').fetchone()[0]+1)
        receipt=build(ops,ROOT,identifier)
        print('Source-bound compatibility artifact built',flush=True)
        state_before=ops.state();selected_before=ops.db.execute('SELECT active_id FROM product_control').fetchone()[0]
        try:build(ops,ROOT,identifier+'-failure',fail_at='pointer')
        except RuntimeError:pass
        else:raise AssertionError('Injected product pointer failure did not occur')
        verified,payload=load(ops,ROOT)
        checks={'handoff_receipt_verified':receipt==verified,
                'failed_handoff_keeps_selected_product':ops.db.execute('SELECT active_id FROM product_control').fetchone()[0]==selected_before,
                'source_state_unchanged_by_product_handoff':ops.state()==state_before,
                'original_city_extension_unchanged':sha(TARGET)==source_before,
                '893_title_keys_recomputed':receipt['counts']['title_source_keys']==893,
                '1302_price_keys_recomputed':receipt['counts']['price_source_keys']==1302,
                '1471_residential_keys_preserved':len(payload['residential'])==1471,
                '306_commercial_keys_preserved':len(payload['commercial_stats'])==306,
                '13293_built_transactions_preserved':len(payload['built'])==13293,
                'actual_sql_fixture_inputs_equal':receipt['http_sql_fixture_equal_to_accepted_supply'],
                'no_new_product_permission':all(not r['attributes']['permissions']['product_enrichment'] and not r['price']['permissions']['product_enrichment'] for r in payload['residential'])}
        if not all(checks.values()):raise AssertionError(checks)
        gate=inspect(ROOT,operations=ops)
        report={'experiment':'city-source-bound-product-handoff-v1','checks':checks,'source_state':ops.state(),
            'source_stage':stage,'source_baseline_seconds':source_seconds,'source_baseline_bytes':(ops.root/'candidates'/batch/'ledger.sqlite').stat().st_size,
            'original_extension_sha256':source_before,'selected_handoff':selected_before,'receipt':receipt,
            'gate':gate,'elapsed_seconds':perf_counter()-started,'production_apply':False,
            'runner_sha256':sha(Path(__file__)),
            'limitations':['Single current city snapshot bootstrap; previous city releases remain in original research DB, not in this operations lane.',
                           'Historical normalized intake, not new raw extraction or a future-month update.',
                           'Existing held bindings pass through; equal legacy fields only. Built/commercial remain frozen input.',
                           'Verified output equality reuses prior actual SQL/ASGI acceptance; no new TCP/browser test.']}
        history=[] if previous is None else previous.get('execution_records',[{
            'source_baseline_seconds':previous['source_baseline_seconds'],'elapsed_seconds':previous['elapsed_seconds'],
            'checks':previous['checks'],'receipt':previous['receipt'],'runner_sha256':previous['runner_sha256']}])
        report['execution_records']=history+[{'source_baseline_seconds':source_seconds,'elapsed_seconds':report['elapsed_seconds'],
            'checks':checks,'receipt':receipt,'runner_sha256':report['runner_sha256']}]
        write_json_atomic(report_path,report)
        write_json_atomic(LAB/'cheongju_product_transition_gate.json',gate)
        print(json.dumps({'checks':checks,'counts':receipt['counts'],'source_baseline_seconds':source_seconds,
             'source_baseline_bytes':report['source_baseline_bytes'],'elapsed_seconds':report['elapsed_seconds'],'blockers':gate['blockers']},ensure_ascii=True))
    finally:ops.close()


if __name__=='__main__':main()
