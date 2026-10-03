"""Inventory source vintages only; stream DBFs without extraction or DB writes."""
import json,struct,zipfile
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
reports=[]
for src in sorted((ROOT/'raw/raw addition/토지특성정보(브이월드)').glob('*.zip')):
 with zipfile.ZipFile(src) as z:
  with z.open(next(n for n in z.namelist() if n.lower().endswith('.dbf'))) as f:
   h=f.read(32); n=struct.unpack('<I',h[4:8])[0]; hl,rl=struct.unpack('<HH',h[8:12]); off=1; fields={}
   for _ in range((hl-33)//32):
    d=f.read(32); name=d[:11].split(b'\0')[0].decode('ascii'); fields[name]=(off,d[16]);off+=d[16]
   f.read(hl-32-32*len(fields)); first=f.read(rl)
   try: first.decode('utf-8');enc='utf-8'
   except UnicodeDecodeError: first.decode('cp949');enc='cp949'
   f.seek(hl); counts={k:Counter() for k in ('A8','A9','A26','A19','A21','A23')}; pnus=set();dups=deleted=0
   for _ in range(n):
    row=f.read(rl)
    if len(row)!=rl:raise ValueError('truncated DBF')
    if row[:1]==b'*':deleted+=1;continue
    a,l=fields['A1'];pnu=row[a:a+l].decode(enc).replace(chr(0),'').strip();dups+=pnu in pnus;pnus.add(pnu)
    for k in counts:
     a,l=fields[k];v=row[a:a+l].decode(enc).replace(chr(0),'').strip();counts[k][v or '<EMPTY>']+=1
   f.read()
  report={'file':src.name,'zip_bytes':src.stat().st_size,'rows':n,'unique_pnu':len(pnus),'duplicates':dups,'deleted':deleted,'encoding':enc,'fields':list(fields),'value_counts':{k:dict(c) for k,c in counts.items()}}
  reports.append(report)
  print(src.name,n,'year',dict(counts['A8']),'asof',dict(counts['A26']),flush=True)
(ROOT/'docs/lab/cheongju_land_vintages_20261004.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
