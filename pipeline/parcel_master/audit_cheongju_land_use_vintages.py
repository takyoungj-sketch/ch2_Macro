"""Read-only source-vintage audit of Chungbuk land-use-plan CSVs."""
import json,zipfile
from pathlib import Path
from collections import Counter
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'raw/raw addition/토지이용계획csv(브이월드)'
reports=[]
sources=sorted(BASE.glob('AL_D155_43_*.zip'))+sorted(BASE.glob('AL_D155_43_*/*.csv'))
for src in sources:
 z=None
 if src.suffix=='.zip':
  z=zipfile.ZipFile(src);member=next(n for n in z.namelist() if n.endswith('.csv'));stream=z.open(member);size=z.getinfo(member).file_size
 else:stream=src.open('rb');size=src.stat().st_size
 cols=['고유번호','저촉여부','용도지역지구코드','용도지역지구명','데이터기준일자','등록일자']
 total=rows=0;pnus=set();pergu=Counter();dates=Counter();contacts=Counter();labels=Counter();codes=Counter();blanks=Counter();regdates=[]
 for chunk in pd.read_csv(stream,encoding='cp949',dtype=str,chunksize=200000,usecols=cols):
  total+=len(chunk)
  frame=chunk[chunk['고유번호'].str[:5].isin(['43111','43112','43113','43114'])]
  rows+=len(frame);pnus.update(frame['고유번호'].dropna());pergu.update(frame['고유번호'].str[:5])
  for col in cols:blanks[col]+=int(frame[col].isna().sum())
  dates.update(frame['데이터기준일자'].fillna('<EMPTY>'));contacts.update(frame['저촉여부'].fillna('<EMPTY>'));labels.update(frame['용도지역지구명'].fillna('<EMPTY>'));codes.update(frame['용도지역지구코드'].str[:2].fillna('<EMPTY>'))
  valid=frame['등록일자'].dropna()
  if len(valid):regdates.extend([valid.min(),valid.max()])
 stream.close()
 if z:z.close()
 report={'file':str(src.relative_to(ROOT)),'uncompressed_bytes':size,'province_rows':total,'cheongju_rows':rows,'cheongju_unique_pnu':len(pnus),'rows_by_gu':dict(pergu),'data_dates':dict(dates),'contact_counts':dict(contacts),'code_prefix_counts':dict(codes),'label_counts':dict(labels),'null_counts':dict(blanks),'registration_min':min(regdates) if regdates else None,'registration_max':max(regdates) if regdates else None,'full_snapshot_status':('publisher listing confirms 전체데이터 for matching date and Chungbuk CSV' if src.suffix=='.zip' else 'existing local 2026 regional file; listing classification not rechecked')}
 reports.append(report);print(src.name,rows,len(pnus),dict(dates),contacts.most_common(),flush=True)
(ROOT/'docs/lab/cheongju_land_use_vintages_20261004.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
