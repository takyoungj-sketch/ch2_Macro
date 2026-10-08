"""2019-26 trait-only candidate experiment. Local files; DB READ ONLY."""
import csv
import gzip
import hashlib
import json
import re
import struct
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'pipeline'))
from db_utils import get_engine
from constants import LAND_CATEGORY_COMPACT_MAP, ZONE_TYPE_COMPACT_MAP
from trait_link_helpers import area_key, code, lot_matches

OUT = ROOT / 'data/research/cheongju_ledger'
RAW = ROOT / 'raw/raw addition/토지특성정보(브이월드)'
LAB = ROOT / 'docs/lab'
MAPPING = [('pnu','A1'),('bjd','A2'),('lot','A6'),('year','A8'),('month','A9'),
           ('jimok_code','A10'),('jimok_label','A11'),('area','A12'),
           ('zone1_code','A13'),('zone1_label','A14'),('zone2_code','A15'),('zone2_label','A16'),
           ('use_code','A17'),('height_code','A19'),('shape_code','A21'),('road_code','A23'),('price','A25'),('trait_asof','A26')]

def build_cache(year):
    path = OUT / f'traits_{year}.csv.gz'
    if path.exists():
        return path
    files = sorted(RAW.glob(f'AL_D194_4311?_{year}*.zip'))
    if len(files) != 4:
        raise ValueError(f'Expected four sources for {year}')
    temporary = path.with_suffix('.gz.pending')
    with gzip.open(temporary,'wt',encoding='utf-8',newline='') as output:
        writer=csv.DictWriter(output,fieldnames=[name for name,_ in MAPPING]+['trait_source'])
        writer.writeheader()
        for src in files:
            with zipfile.ZipFile(src) as archive:
                with archive.open(next(n for n in archive.namelist() if n.lower().endswith('.dbf'))) as stream:
                    h=stream.read(32);n=struct.unpack('<I',h[4:8])[0];hl,rl=struct.unpack('<HH',h[8:12]);fields={};offset=1
                    for _ in range((hl-33)//32):
                        descriptor=stream.read(32);name=descriptor[:11].split(b'\0')[0].decode('ascii')
                        fields[name]=(offset,descriptor[16]);offset+=descriptor[16]
                    stream.read(hl-32-32*len(fields));sample=stream.read(rl)
                    try:sample.decode('utf-8');encoding='utf-8'
                    except UnicodeDecodeError:sample.decode('cp949');encoding='cp949'
                    stream.seek(hl)
                    for _ in range(n):
                        row=stream.read(rl)
                        if len(row)!=rl:raise ValueError('Truncated source')
                        if row[:1]==b'*':continue
                        values={name:row[fields[field][0]:sum(fields[field])].decode(encoding).replace('\0','').strip() for name,field in MAPPING}
                        writer.writerow({**values,'trait_source':src.name})
                    stream.read()
            print('normalized',src.name,flush=True)
    temporary.replace(path)
    return path

def main():
    # Empirical code dictionary: source pairs are retained, never inferred from price.
    pairs=defaultdict(set)
    for year in (2019,2020,2021):
        frame=pd.read_csv(build_cache(year),dtype=str,keep_default_na=False)
        for c,l,kind in [('jimok_code','jimok_label','jimok'),('zone1_code','zone1_label','zone'),('zone2_code','zone2_label','zone')]:
            for raw,label in frame[[c,l]].drop_duplicates().itertuples(index=False,name=None):
                if label and code(raw)!='UNKNOWN':pairs[(kind,code(raw))].add(label)
    if any(len(labels)!=1 for labels in pairs.values()):raise ValueError('Ambiguous source code dictionary')
    labels={key:next(iter(value)) for key,value in pairs.items()}
    (OUT/'trait_code_dictionary.json').write_text(json.dumps({f'{k}:{c}':v for (k,c),v in labels.items()},ensure_ascii=False,indent=2),encoding='utf-8')
    with get_engine().connect() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        tx=pd.read_sql(text("SELECT transaction_hash,contract_year,contract_date,beopjungri_code,land_category,zone_type,road_condition,deal_type,area_sqm,unit_price_per_sqm,is_partial_ownership,is_cancelled,is_valid,lot_display FROM land_transactions WHERE sigungu_code IN ('43111','43112','43113','43114') AND contract_year BETWEEN 2019 AND 2026"),connection)
    assert tx.transaction_hash.is_unique
    tx.to_csv(OUT/'trait_transaction_snapshot.csv.gz',index=False,compression='gzip')
    old=json.loads((LAB/'cheongju_historical_traits_20261004.json').read_text(encoding='utf-8'))
    modern=json.loads((LAB/'cheongju_ledger_link_pilot_20261004.json').read_text(encoding='utf-8'))
    cutoffs={int(y):max(d for r in old['files'] if r['year']==int(y) for d in r['source_dates_and_years']['A26']) for y in old['year_summary']}
    cutoffs.update({int(y):r['trait_asof'] for y,r in modern['source_join'].items()})
    for value in cutoffs.values():date.fromisoformat(value)
    pending=defaultdict(list);results=[];counts=defaultdict(Counter);sources={}
    for r in tx.to_dict('records'):
        reason='cancelled' if r['is_cancelled'] else 'invalid' if not r['is_valid'] else 'partial' if r['is_partial_ownership'] else 'unsupported_zone' if r['zone_type'] not in set(ZONE_TYPE_COMPACT_MAP.values()) else ''
        if not reason and not re.fullmatch(r'[0-9*]+',str(r['lot_display'] or '').removeprefix('산').strip()):reason='unsupported_lot'
        if not reason and area_key(r['area_sqm']) is None:reason='missing_area'
        for policy in ('annual','observed_before_trade'):
            options=[] if pd.isna(r['contract_date']) else [y for y,d in cutoffs.items() if d<=str(r['contract_date'])]
            selected=int(r['contract_year']) if policy=='annual' else max(options) if options else None
            base={'transaction_hash':r['transaction_hash'],'contract_year':int(r['contract_year']),'contract_date':str(r['contract_date']),'policy':policy,'source_year':selected}
            if reason or selected is None:
                status=reason or 'no_prior_snapshot';counts[f"{r['contract_year']}:{policy}"][status]+=1
                results.append({**base,'status':status,'candidate_pnus':'[]','candidate_count':0})
            else:pending[selected].append((r,base))
    for year in range(2019,2027):
        path=build_cache(year)
        frame=pd.read_csv(path,dtype=str,keep_default_na=False)
        cols=[name for name,_ in MAPPING]+['trait_source']
        # Compare only normalized columns: old caches also carry optional labels.
        normalized=frame[cols]
        repeated=normalized[normalized.duplicated('pnu',keep=False)]
        if len(repeated.drop_duplicates())!=repeated.pnu.nunique():raise ValueError(f'{year}: conflicting duplicates')
        duplicates=len(frame)-frame.pnu.nunique();frame=normalized.drop_duplicates('pnu')
        assert frame.pnu.str.fullmatch(r'4311[1-4]\d{14}').all()
        frame=frame.copy()
        frame['trait_asof']=frame.trait_asof.map(lambda value:datetime.fromisoformat(value).date().isoformat())
        dates=set(frame.trait_asof)
        for d in dates:date.fromisoformat(d)
        assert max(dates)==cutoffs[year]  # fail if audit cutoff is stale
        idx=defaultdict(list);rows={};unknown=Counter()
        for row in frame.to_dict('records'):
            pnu=row['pnu'];rows[pnu]=row
            for c,l,kind in [('jimok_code','jimok_label','jimok'),('zone1_code','zone1_label','zone'),('zone2_code','zone2_label','zone')]:
                k=(kind,code(row[c]));existing=labels.get(k)
                if row[l] and existing and row[l]!=existing:raise ValueError(f'Code label changed in {year}: {k}')
            jimok_label=labels.get(('jimok',code(row['jimok_code'])), '')
            jimok=LAND_CATEGORY_COMPACT_MAP.get(jimok_label,jimok_label)
            row['_zones']={ZONE_TYPE_COMPACT_MAP[label] for c in ('zone1_code','zone2_code') if (label:=labels.get(('zone',code(row[c])),'')) in ZONE_TYPE_COMPACT_MAP}
            for c in ('zone1_code','zone2_code'):
                if code(row[c])!='UNKNOWN' and ('zone',code(row[c])) not in labels:unknown[code(row[c])]+=1
            area=area_key(row['area'])
            if row['year']==str(year) and jimok and area:idx[(row['bjd'],jimok,area)].append(pnu)
        for r,base in pending[year]:
            candidates=sorted(pnu for pnu in idx.get((str(r['beopjungri_code']),r['land_category'],area_key(r['area_sqm'])),[]) if lot_matches(r['lot_display'],pnu,rows[pnu]['lot']) and r['zone_type'] in rows[pnu]['_zones'])
            status='unique_candidate' if len(candidates)==1 else 'ambiguous' if candidates else 'no_candidate'
            a=rows[candidates[0]] if len(candidates)==1 else {}
            result={**base,'status':status,'candidate_pnus':json.dumps(candidates),'candidate_count':len(candidates)}
            for name in ('trait_asof','price','use_code','height_code','shape_code','road_code'):result[name]=a.get(name,'')
            if base['policy']=='observed_before_trade' and a:assert a['trait_asof']<=base['contract_date']
            results.append(result);counts[f"{r['contract_year']}:{base['policy']}"][status]+=1
        sources[str(year)]={'parcels':len(frame),'deduplicated_rows':duplicates,'cutoff':cutoffs[year],'unknown_zone_codes':dict(unknown),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        print('linked',year,len(pending[year]),flush=True)
    candidates=pd.DataFrame(results).fillna('').sort_values(['transaction_hash','policy'])
    assert len(candidates)==2*len(tx) and not candidates.duplicated(['transaction_hash','policy']).any()
    candidates.to_csv(OUT/'trait_candidates.csv.gz',index=False,compression='gzip')
    previous=pd.read_csv(OUT/'plan_comparison_candidates.csv.gz',dtype=str,keep_default_na=False)
    comparison=[]
    for policy in ('annual','observed_before_trade'):
        left=candidates[candidates.policy==policy].set_index('transaction_hash');right=previous[previous.policy==policy].set_index('transaction_hash')
        ids=left.index.intersection(right.index);a=left.loc[ids];b=right.loc[ids]
        both=(a.status=='unique_candidate')&(b.status=='unique_candidate')
        comparison.append({'policy':policy,'transaction_rows':len(ids),'trait_unique':int((a.status=='unique_candidate').sum()),'plan_unique':int((b.status=='unique_candidate').sum()),'both_unique':int(both.sum()),'same_pnu':int((both&(a.candidate_pnus==b.candidate_pnus)).sum()),'different_pnu':int((both&(a.candidate_pnus!=b.candidate_pnus)).sum()),'trait_only_unique':int(((a.status=='unique_candidate')&(b.status!='unique_candidate')).sum()),'plan_only_unique':int(((b.status=='unique_candidate')&(a.status!='unique_candidate')).sum())})
    report={'run_date':'2026-10-04','rule_version':'trait-only-v1','transaction_rows':len(tx),'source_join':sources,'counts':{k:dict(v) for k,v in counts.items()},'overlap_comparison_2023_2026':comparison,'accuracy':'unverified','dictionary_basis':'Unique observed code-label pairs from 2019-2021, checked against subsequent source pairs; not a legal historical dictionary certification.','limitations':['Annual is retrospective reference; before-trade uses source observation date, not historic publication/availability.','Trait zone1/zone2 is not complete land-use planning designations.','Unmatched or ambiguous transactions are not forced; no price is used in matching.'],'transaction_input_sha256':hashlib.sha256((OUT/'trait_transaction_snapshot.csv.gz').read_bytes()).hexdigest()}
    (LAB/'cheongju_trait_links_20261004.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(comparison),flush=True)

if __name__=='__main__':main()
