"""One command for source supply, fixed regressions, price marts and response audit."""
import json
import subprocess
from pathlib import Path
from time import perf_counter

from ledger_consumer_input_preview import ROOT,OUT,LAB
from ledger_supply_bundle import verify_manifest,sha
from ledger_supply_artifacts import write_json_atomic


def main():
    started=perf_counter()
    tasks=[('supply',ROOT/'pipeline/.venv/Scripts/python.exe','run_cheongju_product_supply.py'),
           ('marts_api',ROOT/'backend/.venv/Scripts/python.exe','replay_cheongju_supply_marts_api.py')]
    for label,python,script in tasks:
        print('Running',label,flush=True)
        with (OUT/('product_acceptance_'+label+'.log')).open('w',encoding='utf-8') as log:
            subprocess.run([str(python),str(Path(__file__).with_name(script))],cwd=Path(__file__).parent,
                           stdout=log,stderr=subprocess.STDOUT,check=True)
    _,manifest_hash=verify_manifest(ROOT)
    audit_path=LAB/'cheongju_supply_marts_api_replay.json'
    audit=json.loads(audit_path.read_text(encoding='utf-8'))
    if audit['supply_manifest_sha256']!=manifest_hash or audit['production_apply'] is not False or not all(v is True for v in audit['checks'].values()):
        raise ValueError('Acceptance audit is incomplete or belongs to another supply')
    regression=json.loads((LAB/'cheongju_supply_regression_replay.json').read_text(encoding='utf-8'))
    for mapping in (audit['implementation_sha256'],regression['engine_code_sha256']):
        for name,expected in mapping.items():
            if sha(ROOT/name)!=expected:raise ValueError('Product implementation changed during acceptance: '+name)
    if sha(OUT/'product_marts_api_replay.json.gz')!=audit['gzip_sha256']:raise ValueError('Response artifact changed')
    report={'acceptance':'cheongju-fixed-product-input-acceptance-v1','supply_manifest_sha256':manifest_hash,
            'marts_api_report_sha256':sha(audit_path),'response_artifact_sha256':audit['gzip_sha256'],
            'runner_sha256':sha(Path(__file__)),'checks':{'completed_supply_verified':True,
               'price_marts_and_response_helpers_passed':True,'product_implementation_hashes_verified':True,
               'response_artifact_verified':True},'production_apply':False,
            'actual_next_month_update_tested':False,'http_end_to_end_tested':False,
            'elapsed_seconds':perf_counter()-started}
    write_json_atomic(LAB/'cheongju_product_acceptance.json',report)
    print(json.dumps(report,ensure_ascii=True))


if __name__=='__main__':main()
