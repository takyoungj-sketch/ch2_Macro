"""Refresh aggregate-only historical experiment view from fixed local inputs."""
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/research/cheongju_ledger';LAB=ROOT/'docs/lab'
links=json.loads((LAB/'cheongju_trait_links_20261004.json').read_text(encoding='utf-8'))
regression=json.loads((LAB/'cheongju_historical_regression_20261004.json').read_text(encoding='utf-8'))
trait=pd.read_csv(OUT/'trait_candidates.csv.gz',dtype=str,keep_default_na=False)
plan=pd.read_csv(OUT/'plan_comparison_candidates.csv.gz',dtype=str,keep_default_na=False)
tx=pd.read_csv(OUT/'trait_transaction_snapshot.csv.gz',dtype={'transaction_hash':str},keep_default_na=False).set_index('transaction_hash')
comparisons=[];bias=[]
for policy in ('annual','observed_before_trade'):
    a=trait[trait.policy==policy].set_index('transaction_hash');b=plan[plan.policy==policy].set_index('transaction_hash')
    ids=a.index.intersection(b.index)
    for year in range(2023,2027):
        selected=ids[a.loc[ids,'contract_year']==str(year)];left=a.loc[selected];right=b.loc[selected]
        both=(left.status=='unique_candidate')&(right.status=='unique_candidate')
        comparisons.append({'policy':policy,'year':year,'transactions':len(selected),
                            'trait_unique':int((left.status=='unique_candidate').sum()),'plan_unique':int((right.status=='unique_candidate').sum()),
                            'both_unique':int(both.sum()),'same_pnu':int((both&(left.candidate_pnus==right.candidate_pnus)).sum()),
                            'different_pnu':int((both&(left.candidate_pnus!=right.candidate_pnus)).sum()),
                            'trait_only_unique':int(((left.status=='unique_candidate')&(right.status!='unique_candidate')).sum()),
                            'plan_only_unique':int(((right.status=='unique_candidate')&(left.status!='unique_candidate')).sum())})
    eligible=a[a.status.isin(['unique_candidate','ambiguous','no_candidate','no_prior_snapshot'])]
    for year in range(2019,2027):
        for linked in (True,False):
            rows=eligible[(eligible.contract_year==str(year))&((eligible.status=='unique_candidate')==linked)]
            values=tx.loc[rows.index]
            bias.append({'policy':policy,'year':year,'group':'unique_candidate' if linked else 'eligible_unlinked','n':len(values),
                         'area_median':float(pd.to_numeric(values.area_sqm).median()) if len(values) else None,
                         'price_median':float(pd.to_numeric(values.unit_price_per_sqm).median()) if len(values) else None})
fields=['scope','policy','test_year','model','n_train','n_test','test_log_rmse','cell_mean_mae_n20','cells_n20',
        'cell_covered_transactions','actual_mean','predicted_mean','mean_ci95_approx','unseen_parcel','districts']
result={'run_date':links['run_date'],'transaction_rows':links['transaction_rows'],'source_join':links['source_join'],
        'counts':links['counts'],'method_comparison':comparisons,'selection_bias':bias,'samples':regression['samples'],
        'results':[{k:r[k] for k in fields} for r in regression['results']],'limitations':regression['limitations']}
text=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
assert 'transaction_hash' not in text and 'candidate_pnus' not in text
(LAB/'cheongju_historical_lab_summary.json').write_text(text,encoding='utf-8')
print('Exported historical lab: ',len(result['results']),'models;',len(comparisons),'method comparisons')
