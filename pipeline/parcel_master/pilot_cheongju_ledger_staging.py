"""Replay two real source snapshots in an isolated, sampled SQLite ledger."""
import hashlib
import json
from pathlib import Path
import pandas as pd
from ledger_staging import connect,ingest,restore,DISTRICTS

ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/research/cheongju_ledger';LAB=ROOT/'docs/lab'
path=OUT/'ledger_staging_pilot.sqlite'
frames={y:pd.read_csv(OUT/f'traits_{y}.csv.gz',dtype=str,keep_default_na=False) for y in (2025,2026)}
inventory=json.loads((LAB/'cheongju_trait_links_20261004.json').read_text(encoding='utf-8'))
for year,frame in frames.items():
    recorded=inventory['source_join'][str(year)]
    assert frame.pnu.nunique()==recorded['parcels']
    assert hashlib.sha256((OUT/f'traits_{year}.csv.gz').read_bytes()).hexdigest()==recorded['sha256']
universe=set().union(*(set(f.pnu) for f in frames.values()))
scope=set()
for district in sorted(DISTRICTS):
    scope.update(sorted((p for p in universe if p.startswith(district)),key=lambda p:hashlib.sha256(p.encode()).digest())[:1000])
scope_hash=hashlib.sha256('\n'.join(sorted(scope)).encode()).hexdigest()
db=connect(path);counts={}
for year,frame in frames.items():
    subset=frame[frame.pnu.isin(scope)].copy()
    rows=subset.to_dict('records')
    manifest={'source_districts':sorted(DISTRICTS),'sha256':hashlib.sha256((OUT/f'traits_{year}.csv.gz').read_bytes()).hexdigest(),
              'expected_unique_pnu':subset.pnu.nunique(),'scope_sha256':scope_hash,'scope':'deterministic 1000 PNU per district from two-year union',
              'source_base_date':max(subset.trait_asof.str[:10]),'collected_date':'2026-10-04'}
    result=ingest(db,str(year),rows,manifest)
    replay=ingest(db,str(year),rows,manifest)
    assert replay['idempotent_replay']
    counts[str(year)]={**result,'idempotency_verified':True}

def state():
    return (db.execute("SELECT value FROM state WHERE key='head'").fetchone()[0],
            db.execute('SELECT COUNT(*) FROM versions').fetchone()[0],
            db.execute('SELECT COUNT(*) FROM membership').fetchone()[0])

before=state();latest=frames[2026][frames[2026].pnu.isin(scope)].to_dict('records')
manifest={**manifest,'sha256':'f'*64}
try:ingest(db,'2027-failure-test',latest,manifest,fail_after=20)
except RuntimeError:pass
else:raise AssertionError('Failure injection did not trigger')
assert state()==before
restore(db,'2025');assert state()[0]=='2025'
restore(db,'2026');assert state()==before
stale=db.execute("SELECT COUNT(*) FROM current_values WHERE last_snapshot<>'2026'").fetchone()[0]
report={'run_date':'2026-10-04','scope_pnu':len(scope),'scope_sha256':scope_hash,'snapshot_counts':counts,
        'failure_rollback_verified':True,'historical_restore_verified':True,'missing_retained_as_stale':stale,
        'versions':before[1],'observations':before[2],'sqlite_bytes':path.stat().st_size,
        'limitations':['Local SQLite prototype on 1000 PNU per district, not full-city production migration.',
                       'Missing observations are retained as stale; no legal extinction inferred.',
                       'Quarterly collection, building/plan histories and transaction enrichment are not implemented.']}
db.close()
(LAB/'cheongju_ledger_staging_20261004.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
