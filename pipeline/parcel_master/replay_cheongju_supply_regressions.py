"""Refit fixed specifications with actual product engines on frozen shadow inputs."""
import gzip
import json
import sys
import warnings
from collections import Counter

import numpy as np
import pandas as pd

from ledger_consumer_input_preview import ROOT, OUT, LAB
from integrated_ledger_v2 import digest
from run_cheongju_integrated_ledger_v2 import file_hash
from ledger_supply_artifacts import write_json_atomic

sys.path.insert(0,str(ROOT/'backend'))
from app.collective.regional_regression import engine as regional
from app.collective.regional_regression.schemas import RegionalRegressionVariables
from app.built.regression.engine import _fit_ols as built_fit
from app.built.schemas import RegressionVariableSpec
from app.collective_commercial.regression.engine import _run_regression_core
from app.collective_commercial.schemas import CommercialRegressionRequest, CommercialRegressionSpec


def frame(rows,columns):
    df=pd.DataFrame(rows)
    for column in columns:
        if column not in df:df[column]=np.nan
        df[column]=pd.to_numeric(df[column],errors='coerce')
    return df


def regional_frame(rows,branch):
    records=[]
    for r in rows:
        s=r['stats'];a=r[branch+'_attributes'] or {}
        if s['asset_type']=='presale':continue
        record={**a,'building_key':s['building_key'],'asset_type':s['asset_type'],'median':s['median'],
                'n_tx':s['count'],'building_year':s['building_year'],
                'assessed_land_price':r['legacy_price'] if branch=='legacy' else r['compatible_price'],
                'as_of_year':int(s['as_of_month'][:4])}
        records.append(record)
    df=frame(records,['households','max_floor','parking_per_household','approved_year','building_year','assessed_land_price','median','n_tx','as_of_year'])
    df['building_age']=df['as_of_year']-df['approved_year'].fillna(df['building_year'])
    df.loc[(df['building_age']<0)|(df['building_age']>80),'building_age']=np.nan
    flags=df['attr_quality_flags'].fillna('').astype(str).map(regional._flags)
    df.loc[flags.map(lambda s:'hh_zero' in s or 'scale_inconsistent' in s),'households']=np.nan
    df.loc[flags.map(lambda s:'floor_implausible' in s or 'scale_inconsistent' in s),'max_floor']=np.nan
    df.loc[flags.map(lambda s:'parking_implausible' in s),'parking_per_household']=np.nan
    df.loc[df['households']<=0,'households']=np.nan
    df.loc[df['max_floor']<=0,'max_floor']=np.nan
    df.loc[df['parking_per_household']<0,'parking_per_household']=np.nan
    return df


def regional_fit(df,v):
    eligible=df.loc[regional._eligible_mask(df,v,min_tx=5)].copy()
    x,_,_=regional._design(eligible,v)
    fit=regional._fit_ols(eligible,x,model_type='log',weight_mode='tx')
    if fit is None:raise ValueError('Fixed regional replay cannot fit')
    return {'n':fit['n'],'r_squared':fit['r_squared'],'adj_r_squared':fit['adj_r_squared'],'mape':fit['mape'],
            'rmse':fit['rmse'],'coefficients':[c.model_dump() for c in fit['coefficients']],
            'fitted_mean_unit_price_10k_krw_per_m2':float(np.mean(fit['y_hat'])),
            'target_mean_unit_price_10k_krw_per_m2':float(eligible['median'].mean()),
            'sample_keys_sha256':digest(sorted(eligible['building_key'].tolist()))}


def plain_result(result):
    raw=result.model_dump()
    return {key:raw.get(key) for key in ('n','r_squared','adj_r_squared','mape','coefficients')}


def main():
    path=OUT/'product_numeric_supply_shadow.json.gz'
    meta=json.loads((LAB/'cheongju_numeric_supply_shadow.json').read_text(encoding='utf-8'))
    if file_hash(path)!=meta['gzip_sha256']:raise ValueError('Shadow numeric input changed')
    with gzip.open(path,'rt',encoding='utf-8') as f:paired=json.load(f)
    if digest(paired)!=meta['paired_content_sha256']:raise ValueError('Shadow content changed')
    v=RegionalRegressionVariables(households=True,max_floor=True,building_age=True,parking=False,
                                  assessed_land_price=True,asset_type_dummy=True)
    regional_results={branch:regional_fit(regional_frame(paired['residential'],branch),v)
                      for branch in ('legacy','compatible','candidate_replay')}
    vars_spec=RegressionVariableSpec(road_width_dummy=False,zone_type_dummy=False,building_use_dummy=False,
                                    structure_dummy=True,asset_type_dummy=True)
    built_results={}
    for branch in ('legacy','compatible'):
        records=[{**r['transaction'],'structure_group':(r[branch+'_enrichment'] or {}).get('structure_group')}
                 for r in paired['built'] if r['transaction']['is_valid'] and not r['transaction']['is_partial_ownership']]
        df=frame(records,['price','gross_area','land_area','building_age','road_code','contract_year'])
        result=built_fit(df,vars_spec,'sigungu',unified=True,response_scale='loglog')
        built_results[branch]=plain_result(result)
    req=CommercialRegressionRequest(model_type='log',variables=CommercialRegressionSpec(
        gross_area=True,building_age=True,floor=False,zone_type=False,building_use=False,road_width=False,contract_period=False))
    commercial_results={}
    captured_warnings=Counter()
    for branch in ('legacy','compatible'):
        df=frame(paired['commercial_transactions'],['price','gross_area','building_age','building_year','contract_year','unit_price'])
        commercial_results[branch]={}
        for asset in ('collective_shop','collective_factory'):
            with warnings.catch_warnings(record=True) as recorded:
                warnings.simplefilter('always')
                _,_,_,result=_run_regression_core(df.loc[df['asset_type']==asset].copy(),req,is_shop=asset=='collective_shop',cohort_mode=True)
            captured_warnings.update((w.category.__name__,str(w.message)) for w in recorded)
            public=plain_result(result)
            public['coefficients_sha256']=digest(public.pop('coefficients'))
            commercial_results[branch][asset]=public
    checks={'regional_compatibility_fit_exact':regional_results['legacy']==regional_results['compatible'],
            'built_compatibility_fit_exact':built_results['legacy']==built_results['compatible'],
            'commercial_compatibility_fit_exact':commercial_results['legacy']==commercial_results['compatible'],
            'frozen_shadow_unchanged':file_hash(path)==meta['gzip_sha256']}
    if not all(checks.values()):raise AssertionError(checks)
    report={'baseline_sha256':paired['baseline_sha256'],'published_release':paired['published_release'],
            'regional':regional_results,'built':built_results,'commercial':commercial_results,'checks':checks,
            'captured_engine_warnings':[{'category':category,'message':message,'count':count} for (category,message),count in captured_warnings.items()],
            'specifications':{'regional':{'model':'log','weight':'tx','min_tx':5,'variables':v.model_dump()},
                              'built':{'response_scale':'loglog','partial_excluded':True,'variables':vars_spec.model_dump()},
                              'commercial':req.model_dump()},
            'engine_code_sha256':{str(p.relative_to(ROOT)):file_hash(p) for p in (
                ROOT/'backend/app/collective/regional_regression/engine.py',ROOT/'backend/app/built/regression/engine.py',
                ROOT/'backend/app/collective_commercial/regression/engine.py')},
            'limitations':['Actual product engines, fixed audit specifications; not every UI request or production API end-to-end parity.',
                           'Compatibility preserves legacy numeric attributes and built enrichment; equal refits prove this specified input path, not new membership accuracy.',
                           'Candidate title substitution is exploratory and blocked on review holds; no regression adoption or product permissions.',
                           'No train/test model-selection study; in-sample metrics must not be treated as generalization improvement.',
                           'Built replay uses original transaction numeric variables and frozen legacy enrichment structure; not newly joined historical land prices or candidate structure.',
                           'Commercial control keeps road-cluster inputs and includes cluster effects in the fixed engine specification.']}
    write_json_atomic(LAB/'cheongju_supply_regression_replay.json',report)
    print(json.dumps({p:{b:{k:v for k,v in r.items() if k!='coefficients'} for b,r in report[p].items()} for p in ('regional','built','commercial')},ensure_ascii=True))


if __name__=='__main__':main()
