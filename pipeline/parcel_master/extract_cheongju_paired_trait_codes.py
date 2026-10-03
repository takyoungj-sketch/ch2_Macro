"""Extract code-based categorical values for paired pilot transactions."""
import json,struct,zipfile
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/research/cheongju_ledger'
x=pd.read_csv(OUT/'transaction_candidates.csv.gz',dtype=str,keep_default_na=False);u=x[x.status=='unique_candidate'];a=u[u.policy=='annual'].set_index('transaction_hash');b=u[u.policy=='observed_before_trade'].set_index('transaction_hash');ids=a.index.intersection(b.index);ids=ids[a.loc[ids,'candidate_pnus']==b.loc[ids,'candidate_pnus']]
needed={y:set() for y in range(2023,2027)}
for f in [a.loc[ids],b.loc[ids]]:
 for r in f.to_dict('records'):needed[int(r['source_year'])].add(json.loads(r['candidate_pnus'])[0])
result={};mismatch={k:0 for k in ['use','height','shape','road']}
for year,pnus in needed.items():
 for src in sorted((ROOT/'raw/raw addition/토지특성정보(브이월드)').glob(f'AL_D194_*_{year}*.zip')):
  with zipfile.ZipFile(src) as z:
   with z.open(next(n for n in z.namelist() if n.endswith('.dbf'))) as f:
    h=f.read(32);n=struct.unpack('<I',h[4:8])[0];hl,rl=struct.unpack('<HH',h[8:12]);offset=1;cols={}
    for _ in range((hl-33)//32):
     d=f.read(32);cols[d[:11].split(b'\0')[0].decode()]=(offset,d[16]);offset+=d[16]
    f.read(hl-32-32*len(cols))
    for _ in range(n):
     row=f.read(rl)
     if row[:1]==b'*':continue
     start,size=cols['A1'];pnu=row[start:start+size].decode('ascii').replace(chr(0),'').strip()
     if pnu not in pnus:continue
     values={}
     for name,col in [('use','A17'),('height','A19'),('shape','A21'),('road','A23')]:
      start,size=cols[col];code=row[start:start+size].decode('ascii').replace(chr(0),'').strip()
      values[name]=str(int(code)) if code.isdigit() and int(code)>0 else 'UNKNOWN'
     result[f'{year}:{pnu}']=values
    f.read()
 print(year,len([k for k in result if k.startswith(str(year)+':')]),len(pnus),flush=True)
assert len(result)==sum(len(v) for v in needed.values())
(OUT/'paired_trait_codes.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
