"""Offline exploratory regression comparison. No production DB writes or UI edits."""
import gzip,csv,json,sys
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd
import statsmodels.api as sm
from sqlalchemy import text
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'pipeline'))
from db_utils import get_engine
from pilot_validation import encode_category
OUT=ROOT/'data/research/cheongju_ledger'
x=pd.read_csv(OUT/'transaction_candidates.csv.gz',dtype=str,keep_default_na=False)
u=x[x.status=='unique_candidate'];a=u[u.policy=='annual'].set_index('transaction_hash');b=u[u.policy=='observed_before_trade'].set_index('transaction_hash');common=a.index.intersection(b.index)
conflict=common[a.loc[common,'candidate_pnus']!=b.loc[common,'candidate_pnus']];common=common.difference(conflict)
with get_engine().connect() as c:
 c.execute(text('SET TRANSACTION READ ONLY'))
 tx=pd.read_sql(text("SELECT transaction_hash,contract_year,contract_month,beopjungri_code,land_category,zone_type,road_condition,deal_type,area_sqm,unit_price_per_sqm FROM land_transactions WHERE sigungu_code IN ('43111','43112','43113','43114') AND contract_year BETWEEN 2024 AND 2026"),c).set_index('transaction_hash')
tx=tx.loc[common].copy();tx['area_sqm']=pd.to_numeric(tx.area_sqm);tx['unit_price_per_sqm']=pd.to_numeric(tx.unit_price_per_sqm)
positive=(tx.area_sqm>0)&(tx.unit_price_per_sqm>0);tx=tx[positive];common=tx.index
needed={y:set() for y in range(2023,2027)}
for f in (a.loc[common],b.loc[common]):
 for r in f.to_dict('records'):needed[int(r['source_year'])].add(json.loads(r['candidate_pnus'])[0])
plans={}
for year,pnus in needed.items():
 with gzip.open(OUT/f'parcels_{year}.csv.gz','rt',encoding='utf-8') as f:
  for r in csv.DictReader(f):
   if r['pnu'] in pnus:plans[(year,r['pnu'])]=json.loads(r['plan_json'])
print('same sample',len(common),'conflicts excluded',len(conflict),flush=True)
CODES=json.loads((OUT/'paired_trait_codes.json').read_text(encoding='utf-8'))
def prepare(frame):
 d=tx.copy();f=frame.loc[d.index]
 for col in ['price','use','height','shape','road','source_year']:d[col]=f[col]
 d['pnu']=f.candidate_pnus.map(lambda s:json.loads(s)[0]);d['log_area']=np.log(d.area_sqm);d['trend']=d.contract_year-2024
 for name in ['use','height','shape','road']:
  d[name+'_code']=[CODES[f'{int(yr)}:{pnu}'][name] for yr,pnu in zip(d.source_year,d.pnu)]
 d['log_assessed']=np.log(pd.to_numeric(d.price)/10000)
 for name,token in [('height_district','고도지구'),('landscape_district','경관지구'),('settlement_district','자연취락지구'),('district_plan','지구단위계획구역')]:
  d[name]=[float(any(token in label and contact in ('포함','저촉') for code,label,contact in plans[(int(yr),pnu)])) for yr,pnu in zip(d.source_year,d.pnu)]
 return d
BASE_CAT=['beopjungri_code','land_category','zone_type','road_condition','deal_type'];TRAIT_CAT=['use_code','height_code','shape_code','road_code'];FLAGS=['height_district','landscape_district','settlement_district','district_plan']
def design(train,test,model):
 num=['log_area','trend'];cats=BASE_CAT.copy()
 if model in ('assessed','combined','combined_restrictions'):num+=['log_assessed']
 if model in ('traits','combined','combined_restrictions'):cats+=TRAIT_CAT
 if model=='combined_restrictions':num+=FLAGS
 tr={col:train[col].astype(float) for col in num};te={col:test[col].astype(float) for col in num};novel={}
 for col in cats:
  ta,tb,novel[col]=encode_category(train[col],test[col])
  levels=sorted(set(ta));ref=ta.value_counts().idxmax()
  for level in levels:
   if level==ref:continue
   tr[f'{col}:{level}']=(ta==level).astype(float);te[f'{col}:{level}']=(tb==level).astype(float)
 tr=pd.DataFrame(tr);te=pd.DataFrame(te)
 cols=tr.columns[tr.nunique()>1];return sm.add_constant(tr[cols],has_constant='add'),sm.add_constant(te[cols],has_constant='add'),novel
results=[];cellrows=[]
for policy,frame in [('annual',a),('observed_before_trade',b)]:
 d=prepare(frame)
 for testyear in [2025,2026]:
  train=d[d.contract_year<testyear];test=d[d.contract_year==testyear];y=np.log(train.unit_price_per_sqm)
  for model in ['baseline','assessed','traits','combined','combined_restrictions']:
   X,T,novel=design(train,test,model);fit=sm.OLS(y,X).fit(cov_type='cluster',cov_kwds={'groups':train.pnu})
   predlog=np.asarray(fit.predict(T));truthlog=np.log(test.unit_price_per_sqm.to_numpy());smear=float(np.exp(fit.resid).mean());pred=np.exp(predlog)*smear;truth=test.unit_price_per_sqm.to_numpy()
   # Delta-method interval for average fitted conditional arithmetic mean.
   gradient=(T.to_numpy()*pred[:,None]).mean(axis=0);mean=float(pred.mean());se=float(np.sqrt(max(0,gradient@fit.cov_params().to_numpy()@gradient)))
   cells=test[['zone_type','land_category']].copy();cells['pred']=pred;cells['actual']=truth
   grouped=cells.groupby(['zone_type','land_category']).agg(n=('actual','size'),actual=('actual','mean'),pred=('pred','mean'));grouped=grouped[grouped.n>=20]
   avgcellerror=float(np.average(abs(grouped.pred-grouped.actual),weights=grouped.n)) if len(grouped) else None
   rec={'policy':policy,'test_year':testyear,'model':model,'n_train':len(train),'n_test':len(test),'p':X.shape[1],'rank':int(np.linalg.matrix_rank(X)),'train_adj_r2':float(fit.rsquared_adj),'test_log_rmse':float(np.sqrt(np.mean((predlog-truthlog)**2))),'test_mae_10k_sqm':float(np.mean(abs(pred-truth))),'test_actual_mean_10k_sqm':float(truth.mean()),'test_predicted_mean_10k_sqm':mean,'mean_ci95_approx':[mean-1.96*se,mean+1.96*se],'cell_mean_mae_n20_10k_sqm':avgcellerror,'cells_n20':len(grouped),'unseen_test_categories':{key:value['unseen'] for key,value in novel.items()},'category_fallbacks':novel,'train_log_assessed_coef':float(fit.params['log_assessed']) if 'log_assessed' in fit.params else None,'train_log_area_coef':float(fit.params['log_area'])}
   worst=np.argsort(np.abs(predlog-truthlog))[-5:][::-1]
   rec['worst_test_log_errors']=[{'transaction_hash':str(test.index[i]),'pnu':str(test.pnu.iloc[i]),'use':str(test.use.iloc[i]),'road':str(test.road.iloc[i]),'log_error':float(predlog[i]-truthlog[i]),'actual':float(truth[i]),'predicted':float(pred[i])} for i in worst]
   subset = ~test.pnu.isin(set(train.pnu))
   rec['unseen_parcel_test']={'n':int(subset.sum()),'log_rmse':float(np.sqrt(np.mean((predlog[subset]-truthlog[subset])**2))) if subset.any() else None,'mae_10k_sqm':float(np.mean(abs(pred[subset]-truth[subset]))) if subset.any() else None}
   rec['district_validation']=[]
   for district in sorted(set(test.beopjungri_code.str[:5])):
    mask=(test.beopjungri_code.str[:5]==district).to_numpy()
    rec['district_validation'].append({'sigungu':district,'n':int(mask.sum()),'actual_mean':float(truth[mask].mean()),'predicted_mean':float(pred[mask].mean()),'mean_absolute_error':float(abs(pred[mask]-truth[mask]).mean()),'log_rmse':float(np.sqrt(np.mean((predlog[mask]-truthlog[mask])**2)))})
   results.append(rec)
   for (zone,jimok),r in grouped.iterrows():cellrows.append({'policy':policy,'test_year':testyear,'model':model,'zone':zone,'jimok':jimok,**r.to_dict()})
   print(policy,testyear,model,'logRMSE',round(rec['test_log_rmse'],4),'cellMeanMAE',round(avgcellerror,3) if avgcellerror is not None else None,flush=True)
report={'run_date':'2026-10-04','rule_version':'cheongju-regression-v2-explicit-fallback','sample':len(common),'conflicting_pnu_excluded':len(conflict),'positive_filter_excluded':int((~positive).sum()),'trait_encoding':'Source A17/A19/A21/A23 codes normalized across years; blank/zero=UNKNOWN; raw labels retained for audit','method':'Same transaction hashes across policies and models; 2024 trains 2025, 2024-25 train 2026; log unit-price OLS; training-only rare categories threshold 30; no target-based outlier trim; Duan smearing; cluster covariance by matched PNU','baseline':'log(area)+year trend+BJD+transaction zone/jimok/road/deal categories; this exploratory pooled design is not an exact replay of a production modal','caveats':['Matches unverified; common linked complete sample not all land transactions','Annual source policy uses later observations and is retrospective, not leakage-free forecasting','Mean CI uses coefficient cluster covariance and delta method; excludes source/matching uncertainty and uncertainty in Duan factor','Cell observed means are noisy samples; cell mean error is exploratory, not true conditional mean accuracy','Repeated parcels may cross years; chronological holdout is not unseen-parcel validation','Rule thresholds were exploratory and not pre-registered operational gates'],'results':results}
(ROOT/'docs/lab/cheongju_regression_pilot_20261004.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
pd.DataFrame(cellrows).to_csv(OUT/'regression_cell_means.csv',index=False,encoding='utf-8-sig')
