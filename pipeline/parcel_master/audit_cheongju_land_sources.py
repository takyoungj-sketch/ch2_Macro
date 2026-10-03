"""Read-only Cheongju ZIP/CSV source audit; no database writes."""
import json, struct, zipfile
from collections import Counter
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'raw' / 'raw addition'
OUT = ROOT / 'docs' / 'lab' / 'cheongju_land_characteristics_audit_20261004.json'
GU = {'43111','43112','43113','43114'}
attrs = {}
reports = []
for src in sorted((RAW / '토지특성정보(브이월드)').glob('AL_D194_*_20260520.zip')):
 counts = {k:Counter() for k in ['A8','A9','A14','A16','A18','A20','A22','A24','A26']}
 blanks=Counter(); duplicates=invalid=deleted=nonpositive=decode_errors=0; seen=set()
 with zipfile.ZipFile(src) as z:
  cpg = z.read(next(n for n in z.namelist() if n.endswith('.cpg'))).decode('ascii').strip()
  enc = {'949':'cp949','UTF-8':'utf-8','65001':'utf-8'}.get(cpg.upper(),cpg)
  with z.open(next(n for n in z.namelist() if n.endswith('.dbf'))) as f:
   h=f.read(32); n=struct.unpack('<I',h[4:8])[0]; hl,rl=struct.unpack('<HH',h[8:12]); fields=[]; off=1
   for _ in range((hl-33)//32):
    d=f.read(32); name=d[:11].split(b'\0')[0].decode('ascii'); size=d[16]; fields.append((name,off,size)); off+=size
   f.read(hl-32-32*len(fields))
   sample=f.read(rl)
   try: sample.decode(enc)
   except UnicodeDecodeError: enc='cp949'; sample.decode(enc)
   f.seek(hl)
   for _ in range(n):
    row=f.read(rl)
    if len(row)!=rl: raise ValueError('truncated DBF')
    if row[:1]==b'*': deleted+=1; continue
    values={}
    for name,start,size in fields:
     try: v=row[start:start+size].decode(enc).strip()
     except UnicodeDecodeError: decode_errors+=1; v=row[start:start+size].decode(enc,errors='replace').strip()
     values[name]=v
     if not v: blanks[name]+=1
    pnu=values['A1']; invalid+=not(len(pnu)==19 and pnu.isdigit() and pnu[:5] in GU)
    duplicates+=pnu in seen; seen.add(pnu)
    for name in counts: counts[name][values[name] or '<EMPTY>']+=1
    try: price=float(values['A25']); nonpositive+=price<=0
    except ValueError: price=None; nonpositive+=1
    attrs[pnu]=(values['A10'],values['A12'],price)
   f.read() # consume EOF and validate ZIP CRC
  reports.append({'file':str(src.relative_to(ROOT)),'zip_bytes':src.stat().st_size,'dbf_rows':n,'encoding':enc,'cpg_declared':cpg,'unique_pnu':len(seen),'duplicates':duplicates,'invalid_pnu':invalid,'deleted':deleted,'nonpositive_or_missing_price':nonpositive,'decode_errors':decode_errors,'blank_counts':dict(blanks),'value_counts':{k:dict(v) for k,v in counts.items()}})
 print(src.name,n,len(seen),flush=True)
land=set(); land_rows=0; area_diff=jimok_diff=0
src=next((RAW/'토지대장csv(브이월드)').rglob('AL_D003_43_*.csv'))
for chunk in pd.read_csv(src,encoding='cp949',dtype=str,usecols=['고유번호','면적','지목코드'],chunksize=200000):
 frame=chunk[chunk['고유번호'].str[:5].isin(GU)]
 for pnu,area,jimok in frame[['고유번호','면적','지목코드']].itertuples(index=False,name=None):
  land.add(pnu);land_rows+=1
  if pnu in attrs:
   aj,aa,_=attrs[pnu]
   jimok_diff+=str(jimok).zfill(2)!=aj.zfill(2)
   try: area_diff+=abs(float(area)-float(aa))>0.01
   except ValueError: pass
prices=set(); price_overlap=price_diff=0; diff_examples=[]
src=next((RAW/'개별공시지가(브이월드)').rglob('AL_D151_43_*.csv'))
for chunk in pd.read_csv(src,encoding='cp949',dtype=str,usecols=['고유번호','공시지가','기준연도','기준월'],chunksize=200000):
 frame=chunk[chunk['고유번호'].str[:5].isin(GU)]
 for pnu,year,month,price in frame[['고유번호','기준연도','기준월','공시지가']].itertuples(index=False,name=None):
  prices.add(pnu)
  if pnu in attrs and year=='2026' and month in ('1','01'):
   price_overlap+=1
   ap=attrs[pnu][2]
   if ap is None or ap!=float(price):
    price_diff+=1
    if len(diff_examples)<5: diff_examples.append({'pnu':pnu,'characteristic_price':ap,'price_file':price})
result={'audit_date':'2026-10-04','scope':'source files only, not transaction matching','files':reports,'characteristics_unique_pnu':len(attrs),'land_unique_pnu':len(land),'land_overlap':len(set(attrs)&land),'characteristics_only_vs_land':len(set(attrs)-land),'land_only_vs_characteristics':len(land-set(attrs)),'area_difference_gt_0_01':area_diff,'jimok_code_difference':jimok_diff,'price_unique_pnu':len(prices),'price_overlap':price_overlap,'price_difference':price_diff,'price_difference_examples':diff_examples}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False),flush=True)
