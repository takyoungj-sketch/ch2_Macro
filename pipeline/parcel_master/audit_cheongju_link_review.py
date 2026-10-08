"""Read-only link review: bias summaries and local evidence review queue.

No matching inputs are treated as independent ground truth.
"""
import csv
import gzip
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'pipeline'))
from db_utils import get_engine

OUT = ROOT / 'data/research/cheongju_ledger'
links = pd.read_csv(OUT / 'transaction_candidates.csv.gz', dtype=str, keep_default_na=False)
with get_engine().connect() as connection:
    connection.execute(text('SET TRANSACTION READ ONLY'))
    tx = pd.read_sql(text("SELECT transaction_hash, contract_year, contract_date, beopjungri_code, land_category, zone_type, area_sqm, unit_price_per_sqm, lot_display FROM land_transactions WHERE sigungu_code IN ('43111','43112','43113','43114') AND contract_year BETWEEN 2024 AND 2026"), connection).set_index('transaction_hash')

for col in ('area_sqm', 'unit_price_per_sqm'):
    tx[col] = pd.to_numeric(tx[col], errors='coerce')

annual = links[links.policy == 'annual'].set_index('transaction_hash')
prior = links[links.policy == 'observed_before_trade'].set_index('transaction_hash')
both = annual.index[(annual.status == 'unique_candidate') & (prior.loc[annual.index, 'status'] == 'unique_candidate')]
conflicts = both[annual.loc[both, 'candidate_pnus'] != prior.loc[both, 'candidate_pnus']]
queue = []
for policy in ('annual', 'observed_before_trade'):
    unique = links[(links.policy == policy) & (links.status == 'unique_candidate')].copy()
    unique['district'] = unique.transaction_hash.map(tx.beopjungri_code.str[:5])
    for _, group in unique.groupby(['contract_year', 'district']):
        for record in group.sort_values('transaction_hash').head(3).to_dict('records'):
            queue.append({**record, 'reason': 'stratified_review_sample', 'independent_evidence': '', 'verdict': 'unverified'})
for key in conflicts:
    for frame in (annual, prior):
        queue.append({**frame.loc[key].to_dict(), 'transaction_hash': key,
                      'reason': 'policy_pnu_conflict', 'independent_evidence': '', 'verdict': 'unverified'})
needed = {(int(row['source_year']), pnu) for row in queue for pnu in json.loads(row['candidate_pnus'])}
parcels = {}
for year in range(2023, 2027):
    with gzip.open(OUT / f'parcels_{year}.csv.gz', 'rt', encoding='utf-8') as stream:
        for row in csv.DictReader(stream):
            if (year, row['pnu']) in needed:
                parcels[(year, row['pnu'])] = row
for row in queue:
    row['transaction'] = tx.loc[row['transaction_hash']].to_dict()
    row['parcel'] = parcels[(int(row['source_year']), json.loads(row['candidate_pnus'])[0])]
(OUT / 'link_review_queue.json').write_text(json.dumps(queue, ensure_ascii=False, indent=2, default=str), encoding='utf-8')

groups = []
eligible_status = {'unique_candidate', 'ambiguous', 'no_candidate', 'no_prior_snapshot'}
for policy in ('annual', 'observed_before_trade'):
    frame = links[links.policy == policy].set_index('transaction_hash').join(tx, rsuffix='_transaction')
    eligible = frame[frame.status.isin(eligible_status)].copy()
    eligible['district'] = eligible.beopjungri_code.str[:5]
    eligible['linked'] = eligible.status == 'unique_candidate'
    for linked, subset in eligible.groupby('linked'):
        record = {'policy': policy, 'group': 'unique_candidate' if linked else 'eligible_unlinked', 'n': len(subset)}
        for col in ('area_sqm_transaction', 'unit_price_per_sqm_transaction'):
            values = pd.to_numeric(subset[col], errors='coerce')
            record[col] = {'median': float(values.median()), 'p10': float(values.quantile(.1)), 'p90': float(values.quantile(.9))}
        for col in ('contract_year', 'district', 'land_category', 'zone_type'):
            record[col] = subset[col].value_counts().to_dict()
        groups.append(record)

manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [OUT / 'transaction_candidates.csv.gz', OUT / 'paired_trait_codes.json', *sorted(OUT.glob('parcels_*.csv.gz'))]}
report = {'run_date': '2026-10-04', 'policy_conflicts': len(conflicts), 'review_queue_rows': len(queue),
          'independently_validated_matches': 0, 'accuracy': None,
          'limitations': ['Review queue requires independent evidence; matching inputs do not certify accuracy.',
                         'Unlinked comparison excludes cancelled, invalid, partial-ownership and unsupported inputs.',
                         'Local queue contains identifiers; aggregate report excludes them.'],
          'input_sha256': manifest, 'selection_bias_groups': groups}
(ROOT / 'docs/lab/cheongju_link_review_20261004.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'conflicts': len(conflicts), 'queue_rows': len(queue), 'bias_groups': len(groups)}, ensure_ascii=False))
