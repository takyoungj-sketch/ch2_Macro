"""Validate actual pilot outputs and fair comparison invariants."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/research/cheongju_ledger'
LAB=ROOT/'docs/lab'
candidates=pd.read_csv(OUT/'trait_candidates.csv.gz',dtype=str,keep_default_na=False)
links=json.loads((LAB/'cheongju_trait_links_20261004.json').read_text(encoding='utf-8'))
report=json.loads((LAB/'cheongju_historical_regression_20261004.json').read_text(encoding='utf-8'))
assert len(candidates)==2*links['transaction_rows']
assert not candidates.duplicated(['transaction_hash','policy']).any()
for row in candidates.to_dict('records'):
    pnus=json.loads(row['candidate_pnus'])
    assert len(set(pnus))==len(pnus)==int(row['candidate_count'])
    if row['status']=='unique_candidate':
        assert len(pnus)==1
        if row['policy']=='observed_before_trade':assert row['trait_asof']<=row['contract_date']
assert links['source_join']['2019']['deduplicated_rows']==15
for policy in ('annual','observed_before_trade'):
    for year in (2024,2025,2026):
        rows=[r for r in report['results'] if r['policy']==policy and r['test_year']==year and r['model']=='baseline' and r['scope'] in ('trait_same_sample','plan_same_sample')]
        if not rows:continue
        assert len(rows)==2
        assert (rows[0]['n_train'],rows[0]['n_test'])==(rows[1]['n_train'],rows[1]['n_test'])
        assert np.isclose(rows[0]['test_log_rmse'],rows[1]['test_log_rmse'],rtol=0,atol=1e-10)
assert all(r['rank']==r['p'] for r in report['results'])
assert all(r['test_year']>2019 for r in report['results'])
def check_aggregate(value):
    if isinstance(value,dict):
        assert not {'transaction_hash','candidate_pnus','pnu'}.intersection(value)
        for child in value.values():check_aggregate(child)
    elif isinstance(value,list):
        for child in value:check_aggregate(child)
check_aggregate(links);check_aggregate(report)
print(f"Verified {len(candidates)} candidate rows and {len(report['results'])} models: dates, uniqueness, fair sample, rank, aggregate-only reports")
