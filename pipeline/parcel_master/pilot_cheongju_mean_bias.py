"""Training-only calibration/window diagnostics; fixed local inputs."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm
from pilot_cheongju_historical_regression import prepare, design

ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/research/cheongju_ledger';LAB=ROOT/'docs/lab'

def main():
    tx=pd.read_csv(OUT/'trait_transaction_snapshot.csv.gz',dtype={'transaction_hash':str,'beopjungri_code':str},keep_default_na=False).set_index('transaction_hash')
    for name in ('area_sqm','unit_price_per_sqm','contract_year'):tx[name]=pd.to_numeric(tx[name],errors='coerce')
    candidates=pd.read_csv(OUT/'trait_candidates.csv.gz',dtype=str,keep_default_na=False)
    results=[]
    for policy in ('annual','observed_before_trade'):
        d,_=prepare(tx,candidates[candidates.policy==policy])
        for year in (2024,2025,2026):
            test=d[d.contract_year==year]
            for window in ('expanding','last3','last1'):
                train=d[d.contract_year<year]
                if window!='expanding':train=train[train.contract_year>=year-(3 if window=='last3' else 1)]
                for model in ('baseline','assessed','combined'):
                    X,T,_,_=design(train,test,model);fit=sm.OLS(np.log(train.unit_price_per_sqm),X).fit()
                    train_base=np.exp(np.asarray(fit.predict(X)));base=np.exp(np.asarray(fit.predict(T)))
                    residual_factor=np.exp(np.asarray(fit.resid));global_factor=float(residual_factor.mean())
                    keys=train.zone_type.astype(str)+'|'+train.land_category.astype(str)
                    group=pd.DataFrame({'key':keys,'factor':residual_factor}).groupby('key').factor.agg(['size','mean'])
                    group_factor={k:float((r['size']*r['mean']+100*global_factor)/(r['size']+100)) for k,r in group.iterrows() if r['size']>=50}
                    conditional=np.array([group_factor.get(k,global_factor) for k in test.zone_type.astype(str)+'|'+test.land_category.astype(str)])
                    recent=(train.contract_year==train.contract_year.max()).to_numpy()
                    ratio=float(train.unit_price_per_sqm.to_numpy()[recent].mean()/(train_base[recent].mean()*global_factor))
                    factors={'global_duan':np.full(len(test),global_factor),'group_duan':conditional,'recent_training_ratio':np.full(len(test),global_factor*ratio)}
                    truth=test.unit_price_per_sqm.to_numpy()
                    for correction,factor in factors.items():
                        pred=base*factor
                        groups=[]
                        temp=test[['zone_type','land_category','beopjungri_code']].copy();temp['actual']=truth;temp['predicted']=pred;temp['district']=temp.beopjungri_code.str[:5]
                        for dimension in ('district','zone_type','land_category'):
                            for label,g in temp.groupby(dimension):
                                if len(g)>=20:groups.append({'dimension':dimension,'label':str(label),'n':len(g),'actual_mean':float(g.actual.mean()),'predicted_mean':float(g.predicted.mean()),'signed_bias':float((g.predicted-g.actual).mean())})
                        cells=temp.groupby(['zone_type','land_category']).agg(n=('actual','size'),actual=('actual','mean'),predicted=('predicted','mean'));cells=cells[cells.n>=20]
                        results.append({'policy':policy,'year':year,'window':window,'model':model,'correction':correction,'n_train':len(train),'n_test':len(test),
                                        'global_duan_factor':global_factor,'recent_training_ratio':ratio,'actual_mean':float(truth.mean()),'predicted_mean':float(pred.mean()),
                                        'signed_mean_bias':float((pred-truth).mean()),'relative_mean_bias_pct':float((pred.mean()/truth.mean()-1)*100),
                                        'cell_mean_mae':float(np.average(abs(cells.predicted-cells.actual),weights=cells.n)),
                                        'log_rmse':float(np.sqrt(np.mean((np.log(pred)-np.log(truth))**2))), 'groups':groups})
                    print(policy,year,window,model,flush=True)
    report={'run_date':'2026-10-04','results':results,'method':'Fixed test sample; training-only window/category fitting and calibration. Group Duan uses training zone×jimok residual factors, minimum 50, shrinkage 100. Recent ratio uses last training-year in-sample arithmetic means.',
            'limitations':['Exploratory diagnostics, no operational winner selected.','Calibration uses training fitted residuals, not independent calibration holdout; further validation required.','Matching and source availability remain unverified.','Window effects confound temporal drift and sample composition; not causal attribution.']}
    assert len(results)==162
    for policy in ('annual','observed_before_trade'):
        for year in (2024,2025,2026):assert len({r['n_test'] for r in results if r['policy']==policy and r['year']==year})==1
    (LAB/'cheongju_mean_bias_20261004.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

if __name__=='__main__':main()
