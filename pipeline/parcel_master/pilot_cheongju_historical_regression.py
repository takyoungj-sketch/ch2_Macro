"""Fixed-input, chronological regression and matched-method comparisons."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.linalg import qr
import statsmodels.api as sm

from pilot_validation import encode_category
from trait_link_helpers import code

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/research/cheongju_ledger'
LAB=ROOT/'docs/lab'
BASE_CATS=['beopjungri_code','land_category','zone_type','road_condition','deal_type']
TRAIT_CATS=['use_code','height_code','shape_code','road_code']


def prepare(tx, candidates):
    unique=candidates[candidates.status=='unique_candidate'].set_index('transaction_hash')
    d=tx.loc[unique.index].copy()
    d['pnu']=unique.candidate_pnus.map(lambda value:json.loads(value)[0])
    d['price']=pd.to_numeric(unique.price,errors='coerce')
    for name in TRAIT_CATS:
        if name in unique:d[name]=unique[name].map(code)
    positive=(d.area_sqm>0)&(d.unit_price_per_sqm>0)&(d.price>0)
    excluded=int((~positive).sum());d=d[positive].copy()
    d['log_area']=np.log(d.area_sqm);d['trend']=d.contract_year-2019
    d['log_assessed']=np.log(d.price/10000)
    return d,excluded


def design(train,test,model):
    numbers=['log_area','trend'];categories=BASE_CATS.copy()
    if model in ('assessed','combined'):numbers+=['log_assessed']
    if model in ('traits','combined'):categories+=TRAIT_CATS
    tr={name:train[name].astype(float) for name in numbers};te={name:test[name].astype(float) for name in numbers};audit={}
    for name in categories:
        a,b,audit[name]=encode_category(train[name],test[name])
        reference=a.value_counts().idxmax()
        for level in sorted(set(a)):
            if level==reference:continue
            tr[f'{name}:{level}']=(a==level).astype(float);te[f'{name}:{level}']=(b==level).astype(float)
    X=pd.DataFrame(tr);T=pd.DataFrame(te)
    columns=list(X.columns[X.nunique()>1]);X=sm.add_constant(X[columns],has_constant='add');T=sm.add_constant(T[columns],has_constant='add')
    _,R,pivot=qr(X.to_numpy(),mode='economic',pivoting=True)
    tolerance=np.finfo(float).eps*max(X.shape)*abs(R[0,0])
    rank=int((abs(np.diag(R))>tolerance).sum());selected=sorted(pivot[:rank])
    removed=[str(X.columns[i]) for i in range(X.shape[1]) if i not in selected]
    return X.iloc[:,selected],T.iloc[:,selected],audit,removed


def evaluate(d,scope,policy,models,years):
    results=[]
    for year in years:
        train=d[d.contract_year<year];test=d[d.contract_year==year]
        if len(train)<100 or len(test)<50:continue
        for model in models:
            X,T,audit,removed=design(train,test,model)
            fit=sm.OLS(np.log(train.unit_price_per_sqm),X).fit(cov_type='cluster',cov_kwds={'groups':train.pnu})
            predlog=np.asarray(fit.predict(T));truthlog=np.log(test.unit_price_per_sqm.to_numpy())
            pred=np.exp(predlog)*float(np.exp(fit.resid).mean());truth=test.unit_price_per_sqm.to_numpy()
            assert np.isfinite(pred).all()
            cells=test[['zone_type','land_category']].copy();cells['pred']=pred;cells['actual']=truth
            grouped=cells.groupby(['zone_type','land_category']).agg(n=('actual','size'),actual=('actual','mean'),pred=('pred','mean'))
            grouped=grouped[grouped.n>=20]
            mask=(~test.pnu.isin(set(train.pnu))).to_numpy()
            gradient=(T.to_numpy()*pred[:,None]).mean(axis=0)
            se=float(np.sqrt(max(0,gradient@fit.cov_params().to_numpy()@gradient)))
            row={'scope':scope,'policy':policy,'test_year':int(year),'model':model,'n_train':len(train),'n_test':len(test),
                 'p':X.shape[1],'rank':int(np.linalg.matrix_rank(X)), 'train_adj_r2':float(fit.rsquared_adj),
                 'test_log_rmse':float(np.sqrt(np.mean((predlog-truthlog)**2))),
                 'test_mae_10k_sqm':float(abs(pred-truth).mean()),'actual_mean':float(truth.mean()),'predicted_mean':float(pred.mean()),
                 'mean_ci95_approx':[float(pred.mean()-1.96*se),float(pred.mean()+1.96*se)],
                 'cell_mean_mae_n20':float(np.average(abs(grouped.pred-grouped.actual),weights=grouped.n)) if len(grouped) else None,
                 'cells_n20':len(grouped),'cell_covered_transactions':int(grouped.n.sum()),'category_fallbacks':audit,'dependent_columns_removed':removed,
                 'unseen_parcel':{'n':int(mask.sum()),'log_rmse':float(np.sqrt(np.mean((predlog[mask]-truthlog[mask])**2))) if mask.any() else None,
                                  'mae':float(abs(pred[mask]-truth[mask]).mean()) if mask.any() else None},'districts':[]}
            for district in sorted(set(test.beopjungri_code.str[:5])):
                mask=(test.beopjungri_code.str[:5]==district).to_numpy()
                row['districts'].append({'sigungu':district,'n':int(mask.sum()),'actual_mean':float(truth[mask].mean()),'predicted_mean':float(pred[mask].mean()),'log_rmse':float(np.sqrt(np.mean((predlog[mask]-truthlog[mask])**2)))})
            results.append(row)
            print(scope,policy,year,model,len(test),round(row['test_log_rmse'],4),flush=True)
    return results


def main():
    tx=pd.read_csv(OUT/'trait_transaction_snapshot.csv.gz',dtype={'transaction_hash':str,'beopjungri_code':str},keep_default_na=False).set_index('transaction_hash')
    for name in ('area_sqm','unit_price_per_sqm','contract_year'):tx[name]=pd.to_numeric(tx[name],errors='coerce')
    trait=pd.read_csv(OUT/'trait_candidates.csv.gz',dtype=str,keep_default_na=False)
    plan=pd.read_csv(OUT/'plan_comparison_candidates.csv.gz',dtype=str,keep_default_na=False)
    results=[];samples=[]
    for policy in ('annual','observed_before_trade'):
        d,excluded=prepare(tx,trait[trait.policy==policy])
        samples.append({'scope':'historical_trait','policy':policy,'n':len(d),'excluded_nonpositive_or_missing':excluded,'by_year':{str(int(y)):int(n) for y,n in d.contract_year.value_counts().sort_index().items()}})
        results+=evaluate(d,'historical_trait',policy,('baseline','assessed','traits','combined'),range(2020,2027))
        p,pexcluded=prepare(tx,plan[plan.policy==policy])
        ids=d.index.intersection(p.index);ids=ids[d.loc[ids,'pnu']==p.loc[ids,'pnu']]
        ids=ids[tx.loc[ids,'contract_year']>=2023]
        samples.append({'scope':'same_pnu_method_comparison','policy':policy,'n':len(ids),'plan_positive_excluded':pexcluded})
        results+=evaluate(d.loc[ids],'trait_same_sample',policy,('baseline','assessed'),(2024,2025,2026))
        results+=evaluate(p.loc[ids],'plan_same_sample',policy,('baseline','assessed'),(2024,2025,2026))
    report={'run_date':'2026-10-04','version':'historical-trait-regression-v1','samples':samples,'results':results,
            'input_sha256':{name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ('trait_transaction_snapshot.csv.gz','trait_candidates.csv.gz','plan_comparison_candidates.csv.gz')},
            'method':'Expanding chronological holdout; same sample within each scope/policy/year across models; log OLS; training-only rare pooling; training-only QR rank selection; PNU cluster covariance; training residual Duan smearing.',
            'limitations':['Matches independently unverified; linked positive-price sample is selected.',
                           '2019 is first training year, not a test year. Prior policy lacks a pre-2019 snapshot.',
                           'Annual is retrospective; source observation cutoff is not historical public availability.',
                           'Policies have different selected samples: cross-policy metric differences are not causal.',
                           'Trait zones omit additional land-use planning designations.',
                           'Approximate mean CI excludes matching, source timing, and smearing uncertainty.']}
    assert all(r['p']==r['rank'] for r in results)
    for scope in {r['scope'] for r in results}:
        for policy in ('annual','observed_before_trade'):
            for year in range(2020,2027):
                rows=[r for r in results if r['scope']==scope and r['policy']==policy and r['test_year']==year]
                assert len({(r['n_train'],r['n_test']) for r in rows})<=1
    (LAB/'cheongju_historical_regression_20261004.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

if __name__=='__main__':main()
