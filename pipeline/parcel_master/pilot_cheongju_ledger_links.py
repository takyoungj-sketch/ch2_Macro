"""Cheongju local research: annual source joins and unverified transaction candidates.
Writes research CSV/JSON only; transaction connection is READ ONLY.
"""
import csv,gzip,json,re,struct,sys,zipfile
from collections import Counter,defaultdict
from datetime import date
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
import pandas as pd
from sqlalchemy import text
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'pipeline'))
from db_utils import get_engine
from constants import LAND_CATEGORY_COMPACT_MAP,ZONE_TYPE_COMPACT_MAP
RAW=ROOT/'raw/raw addition';OUT=ROOT/'data/research/cheongju_ledger';OUT.mkdir(parents=True,exist_ok=True)
def area_key(x):
 try:return str(Decimal(str(x)).quantize(Decimal('.1'),rounding=ROUND_HALF_UP))
 except Exception:return None
def fields(src):
 with zipfile.ZipFile(src) as z:
  with z.open(next(n for n in z.namelist() if n.endswith('.dbf'))) as f:
   h=f.read(32);n=struct.unpack('<I',h[4:8])[0];hl,rl=struct.unpack('<HH',h[8:12]);offset=1;cols={}
   for _ in range((hl-33)//32):
    d=f.read(32);cols[d[:11].split(b'\0')[0].decode()]=(offset,d[16]);offset+=d[16]
   f.read(hl-32-32*len(cols));sample=f.read(rl)
   try:sample.decode('utf-8');enc='utf-8'
   except UnicodeDecodeError:enc='cp949'
   f.seek(hl)
   for _ in range(n):
    row=f.read(rl)
    if row[:1]==b'*':continue
    yield {k:row[a:a+l].decode(enc).replace(chr(0),'').strip() for k,(a,l) in cols.items()}
   f.read()
ledger={};summary={}
for year in range(2023,2027):
 cache=OUT/f'parcels_{year}.csv.gz'
 if cache.exists():
  with gzip.open(cache,'rt',encoding='utf-8') as f:
   parcels={r['pnu']:r for r in csv.DictReader(f)}
  print('cache',year,len(parcels),flush=True)
 else:
  parcels={}
  for src in sorted((RAW/'토지특성정보(브이월드)').glob(f'AL_D194_*_{year}*.zip')):
   for r in fields(src):
    parcels[r['A1']]={'pnu':r['A1'],'bjd':r['A2'],'lot':r['A6'],'year':r['A8'],'month':r['A9'],'jimok':LAND_CATEGORY_COMPACT_MAP.get(r['A11'],r['A11']),'area':r['A12'],'zone1':r['A14'],'zone2':r['A16'],'use':r['A18'],'height':r['A20'],'shape':r['A22'],'road':r['A24'],'price':r['A25'],'trait_asof':r['A26'][:10],'trait_source':src.name}
  plan=defaultdict(set);plan_dates=Counter();base=RAW/'토지이용계획csv(브이월드)'
  src=next(base.glob(f'AL_D155_43_{year}*.zip'),None)
  z=zipfile.ZipFile(src) if src else None
  if z:stream=z.open(next(n for n in z.namelist() if n.endswith('.csv')))
  else:src=next(base.glob(f'AL_D155_43_{year}*/*.csv'));stream=src.open('rb')
  cols=['고유번호','용도지역지구코드','용도지역지구명','저촉여부','데이터기준일자']
  for chunk in pd.read_csv(stream,encoding='cp949',dtype=str,usecols=cols,chunksize=200000):
   frame=chunk[chunk['고유번호'].isin(parcels)]
   for pnu,code,label,contact,asof in frame[cols].fillna('').itertuples(index=False,name=None):
    plan[pnu].add((code,label,contact));plan_dates[asof]+=1
  stream.close()
  if z:z.close()
  plan_asof=max(plan_dates) if plan_dates else ''
  for pnu,r in parcels.items():
   r.update(plan_json=json.dumps(sorted(plan.get(pnu,set())),ensure_ascii=False),plan_asof=plan_asof,plan_source=src.name)
  with gzip.open(cache,'wt',encoding='utf-8',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(next(iter(parcels.values()))));w.writeheader();w.writerows(parcels.values())
  print('joined',year,len(parcels),len(plan),flush=True)
 index=defaultdict(list);covered=0
 for pnu,r in parcels.items():
  plans=json.loads(r['plan_json']);covered+=bool(plans)
  zones=sorted({ZONE_TYPE_COMPACT_MAP[label] for code,label,contact in plans if label in ZONE_TYPE_COMPACT_MAP and contact in ('포함','저촉')})
  r['_zones']=zones
  if r['year']==str(year) and r['jimok'] and area_key(r['area']):index[(r['bjd'],r['jimok'],area_key(r['area']))].append(pnu)
 ledger[year]=(parcels,index)
 summary[str(year)]={'parcels':len(parcels),'with_plan':covered,'plan_asof':next(iter(parcels.values()))['plan_asof'],'trait_asof':next(iter(parcels.values()))['trait_asof'],'compact_bytes':cache.stat().st_size}
with get_engine().connect() as c:
 c.execute(text('SET TRANSACTION READ ONLY'))
 tx=pd.read_sql(text("SELECT transaction_hash, contract_year, contract_month, contract_date, beopjungri_code, land_category, zone_type, area_sqm, unit_price_per_sqm, is_partial_ownership, is_cancelled, is_valid, lot_display FROM land_transactions WHERE sigungu_code IN ('43111','43112','43113','43114') AND contract_year BETWEEN 2024 AND 2026"),c)
results=[];counts=defaultdict(Counter)
for r in tx.to_dict('records'):
 y=int(r['contract_year']);d=r['contract_date'];base={'transaction_hash':r['transaction_hash'],'contract_year':y,'contract_date':str(d),'area_sqm':str(r['area_sqm']),'unit_price_per_sqm':str(r['unit_price_per_sqm'])}
 reason=''
 if r['is_cancelled']:reason='cancelled'
 elif not r['is_valid']:reason='invalid'
 elif r['is_partial_ownership']:reason='partial'
 elif r['zone_type'] not in set(ZONE_TYPE_COMPACT_MAP.values()):reason='unsupported_zone'
 lot=str(r['lot_display'] or '').strip();mountain=lot.startswith('산');pat=lot.removeprefix('산').strip()
 if not reason and not re.fullmatch(r'[0-9*]+',pat):reason='unsupported_lot'
 if not reason and not area_key(r['area_sqm']):reason='missing_area'
 for policy in ['annual','observed_before_trade']:
  selected=y
  if policy=='observed_before_trade':
   if d is None: selected=None
   else:
    options=[yr for yr,(p,_) in ledger.items() if max(next(iter(p.values()))['trait_asof'],next(iter(p.values()))['plan_asof'])<=str(d)]
    selected=max(options) if options else None
  status=reason; candidates=[]
  if not status and selected is None:status='no_prior_snapshot'
  if not status:
   p,idx=ledger[selected]
   for pnu in idx.get((str(r['beopjungri_code']),r['land_category'],area_key(r['area_sqm'])),[]):
    a=p[pnu];bun=a['lot'].removeprefix('산').strip().split('-')[0]
    if (pnu[10]=='2')!=mountain:continue
    if not re.fullmatch(pat.replace('*','[0-9]'),bun):continue
    if r['zone_type'] not in a['_zones']:continue
    candidates.append(pnu)
   status='unique_candidate' if len(candidates)==1 else 'ambiguous' if candidates else 'no_candidate'
  counts[f'{y}:{policy}'][status]+=1
  a=ledger[selected][0][candidates[0]] if len(candidates)==1 else {}
  results.append({**base,'policy':policy,'source_year':selected,'status':status,'candidate_count':len(candidates),'candidate_pnus':json.dumps(sorted(candidates)),'trait_asof':a.get('trait_asof',''),'plan_asof':a.get('plan_asof',''),'price':a.get('price',''),'use':a.get('use',''),'height':a.get('height',''),'shape':a.get('shape',''),'road':a.get('road',''),'match_accuracy':'unverified'})
with gzip.open(OUT/'transaction_candidates.csv.gz','wt',encoding='utf-8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
report={'run_date':'2026-10-04','source_join':summary,'transaction_rows':len(tx),'counts':{k:dict(v) for k,v in counts.items()},'rules':'BJD+jimok+area rounded half-up to 0.1+mountain flag+masked main-lot digits+AL_D155 zone labels with 포함/저촉; no price matching','accuracy':'unique candidate is not independently validated','timing':'annual is retrospective reference; observed_before_trade requires both source observation dates before contract_date; neither proves effective validity','outputs':str(OUT.relative_to(ROOT))}
(ROOT/'docs/lab/cheongju_ledger_link_pilot_20261004.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False),flush=True)
