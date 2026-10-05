"""One command: fixed baseline, source field supply, numeric adapters and refit audit."""
import json
import subprocess
from pathlib import Path
from time import perf_counter
from datetime import datetime, timezone

from freeze_cheongju_product_numeric import main as freeze, load
from extend_cheongju_product_fields import main as extend, TARGET, RELEASE, EXTENSION
from cheongju_numeric_supply_shadow import main as compare
from integrated_ledger_v2 import restore, consumer
from ledger_release_cli import open_ledger
from ledger_consumer_input_preview import ROOT, OUT, LAB
from run_cheongju_integrated_ledger_v2 import file_hash
from parcel_master.paths import TITLE_COLS
from ledger_supply_artifacts import write_json_atomic


def verify_extension():
    report_path=LAB/'cheongju_product_field_extension.json'
    if not TARGET.exists() or not report_path.exists():
        extend()
    report=json.loads(report_path.read_text(encoding='utf-8'))
    if file_hash(OUT/'integrated_ledger_v2_cheongju.sqlite')!=report['original_city_database_sha256']:
        raise ValueError('Original city database changed; frozen pipeline cannot be reused')
    db=open_ledger(TARGET)
    selected=db.execute("SELECT value FROM state WHERE key='published_release'").fetchone()[0]
    latest=db.execute('SELECT id FROM release ORDER BY ordinal DESC LIMIT 1').fetchone()[0]
    row=db.execute('SELECT manifest,content_hash FROM release WHERE id=?',(RELEASE,)).fetchone()
    if not row or latest!=RELEASE:raise ValueError('Unexpected extension history')
    manifest=json.loads(row[0])
    if manifest['field_extension']!=EXTENSION or manifest['sources']['title']['product_fields_columns']!=TITLE_COLS:
        raise ValueError('Source field policy changed; create a new extension release')
    if manifest['sources']['title']['sha256']!=report['source_title_sha256']:
        raise ValueError('Extension source hash conflict')
    count=db.execute('SELECT count(*) FROM building_observation WHERE release_id=?',(RELEASE,)).fetchone()[0]
    if count!=manifest['expected_buildings'] or count!=report['extended_building_observations']:
        raise ValueError('Extension observation scope incomplete')
    db.close()
    restored=selected!=RELEASE
    if restored:
        db=open_ledger(TARGET,writable=True);restore(db,RELEASE);db.close()
    db=open_ledger(TARGET)
    pk=db.execute("SELECT pk FROM building_observation WHERE release_id=? AND identity_status='canonical_address' ORDER BY pk LIMIT 1",(RELEASE,)).fetchone()[0]
    sample=consumer(db,pk);db.close()
    if sample['building']['value']['raw'].get('product_fields_policy')!=EXTENSION or sample['building']['permissions']['product_enrichment']:
        raise ValueError('Published consumer field/permission contract differs')
    return {'selected_release':RELEASE,'release_content_sha256':row[1],
            'resumed_from_previous_publication':restored,'previous_selected_release':selected,'sample_consumer_field_and_permission_contract':True}


def main():
    started=perf_counter()
    backend_python=ROOT/'backend/.venv/Scripts/python.exe'
    if not backend_python.is_file():raise ValueError('Existing backend Python runtime required for actual product engine audit')
    freeze();_,baseline=load();extension=verify_extension();compare()
    subprocess.run([str(backend_python),str(Path(__file__).with_name('replay_cheongju_supply_regressions.py'))],check=True,cwd=Path(__file__).parent)
    names=['cheongju_product_numeric_baseline.json','cheongju_product_field_extension.json',
           'cheongju_numeric_supply_shadow.json','cheongju_supply_regression_replay.json']
    reports={name:json.loads((LAB/name).read_text(encoding='utf-8')) for name in names}
    checks={name:all(report['checks'].values()) for name,report in reports.items()}
    if not all(checks.values()):raise AssertionError(checks)
    report={'pipeline':'cheongju-product-supply-shadow-v1','baseline_sha256':baseline['content_sha256'],
            'extension':extension,'checks':checks,'report_sha256':{name:file_hash(LAB/name) for name in names},
            'script_sha256':{name:file_hash(Path(__file__).with_name(name)) for name in (
                'freeze_cheongju_product_numeric.py','extend_cheongju_product_fields.py','cheongju_numeric_supply_shadow.py',
                'replay_cheongju_supply_regressions.py','run_cheongju_product_supply.py','ledger_supply_artifacts.py')},
            'elapsed_seconds':perf_counter()-started,'production_apply':False,
            'limitations':['Fixed historical source and product baseline; not a new-month production update or full API deployment.',
                           'Existing verified field extension is reused without repeating full original extraction; immutable release metadata and original city DB hash are checked.',
                           'Explicit replay selects the known latest experimental release; unexpected later releases are rejected.']}
    path=LAB/'cheongju_product_supply_pipeline.json'
    history=[]
    if path.exists():
        prior=json.loads(path.read_text(encoding='utf-8'))
        history=prior.get('execution_records',[{'extension':prior['extension'],'elapsed_seconds':prior['elapsed_seconds'],
                       'script_sha256':prior['script_sha256'],'checks':prior['checks']}])
    report['execution_records']=history+[{'finished_at':datetime.now(timezone.utc).isoformat(),'extension':extension,
                  'elapsed_seconds':report['elapsed_seconds'],'script_sha256':report['script_sha256'],'checks':checks}]
    write_json_atomic(path,report)
    print(json.dumps(report,ensure_ascii=True))


if __name__=='__main__':main()
