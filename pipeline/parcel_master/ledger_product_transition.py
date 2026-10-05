"""Verify current product evidence; report unmet handoff conditions without promotion."""
import json
from pathlib import Path

from ledger_consumer_input_preview import ROOT,OUT,LAB
from ledger_supply_bundle import verify_manifest,sha
from ledger_supply_artifacts import write_json_atomic
from integrated_ledger_v2 import CONTRACT
from ledger_identity_v2 import VERSION


def conditions(acceptance,contract,publication_bound=False):
    blockers=[]
    if contract['default_permissions'].get('product_enrichment') is not True:
        blockers.append('consumer_contract_does_not_authorize_new_product_use')
    if acceptance.get('actual_next_month_update_tested') is not True:blockers.append('real_next_source_update_not_tested')
    if acceptance.get('tcp_nginx_browser_tested') is not True:blockers.append('tcp_proxy_browser_path_not_tested')
    if not publication_bound:blockers.append('product_handoff_not_bound_to_selected_source_publication')
    return blockers


def inspect(root=ROOT):
    root=Path(root);lab=root/'docs/lab';out=root/'data/research/cheongju_ledger'
    _,manifest_hash=verify_manifest(root)
    acceptance_path=lab/'cheongju_product_acceptance.json';acceptance=json.loads(acceptance_path.read_text(encoding='utf-8'))
    required={'completed_supply_verified','price_marts_and_response_helpers_passed','product_implementation_hashes_verified',
              'response_artifact_verified','actual_asgi_http_and_postgresql_passed','http_sql_artifact_verified'}
    if acceptance['supply_manifest_sha256']!=manifest_hash or acceptance.get('production_apply') is not False or not required<=set(acceptance['checks']) or not all(v is True for v in acceptance['checks'].values()):
        raise ValueError('Stale or failed product acceptance')
    if acceptance['runner_sha256']!=sha(root/'pipeline/parcel_master/run_cheongju_product_acceptance.py'):raise ValueError('Acceptance runner changed')
    for filename,key,artifact,artifact_key in [('cheongju_supply_marts_api_replay.json','marts_api_report_sha256','product_marts_api_replay.json.gz','response_artifact_sha256'),
                          ('cheongju_supply_http_sql_replay.json','http_sql_report_sha256','product_http_sql_replay.json.gz','http_sql_artifact_sha256')]:
        path=lab/filename
        if sha(path)!=acceptance[key]:raise ValueError('Product report generation changed')
        report=json.loads(path.read_text(encoding='utf-8'))
        if report['supply_manifest_sha256']!=manifest_hash or report.get('production_apply') is not False or not report['checks'] or not all(v is True for v in report['checks'].values()):raise ValueError('Failed or mixed product report')
        if sha(out/artifact)!=report['gzip_sha256'] or report['gzip_sha256']!=acceptance[artifact_key]:raise ValueError('Product audit artifact changed')
        for name,expected in report['implementation_sha256'].items():
            path=(root/name).resolve()
            if not path.is_relative_to(root.resolve()) or sha(path)!=expected:raise ValueError('Product implementation changed')
    regression=json.loads((lab/'cheongju_supply_regression_replay.json').read_text(encoding='utf-8'))
    for name,expected in regression['engine_code_sha256'].items():
        if sha(root/name)!=expected:raise ValueError('Regression implementation changed')
    contract_path=root/'docs/LEDGER_SOURCE_CONSUMER_CONTRACT_V2_2.json'
    contract=json.loads(contract_path.read_text(encoding='utf-8'))
    if contract['contract']!=CONTRACT or contract['identity_rule']!=VERSION:raise ValueError('Consumer contract changed')
    blockers=conditions(acceptance,contract)
    return {'gate':'ledger-product-transition-v1','status':'blocked' if blockers else 'ready_for_scoped_review',
            'verified_existing_audit_evidence':True,'blockers':blockers,'acceptance_sha256':sha(acceptance_path),
            'source_manifest_sha256':manifest_hash,'consumer_contract_sha256':sha(contract_path),
            'default_permissions':contract['default_permissions'],'production_apply':False,
            'gate_implementation_sha256':sha(Path(__file__)),
            'limitations':['Verified fixed historical replay is not approval to replace product inputs.',
                           'The current contract keeps new membership, representative selection, quantity aggregation and model adoption separate.']}


if __name__=='__main__':
    result=inspect();write_json_atomic(LAB/'cheongju_product_transition_gate.json',result);print(json.dumps(result,ensure_ascii=True))
