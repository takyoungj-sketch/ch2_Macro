"""Scan supplied originals for local review evidence; no database writes."""
import csv
import gzip
import hashlib
import json
import struct
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'pipeline'))
from parcel_master.paths import title_path,bldrgst_dir,SNAPSHOTS

OUT=ROOT/'data/research/cheongju_ledger'
LAB=ROOT/'docs/lab'


def pnu_from_fields(parts,start):
    sg,bd,gb,bun,ji=[parts[start+i].strip() for i in range(5)]
    bjd=bd if len(bd)==10 else sg+bd.zfill(5) if len(sg)==5 and bd.isdigit() else ''
    if not (len(bjd)==10 and bjd.isdigit() and gb in ('0','1') and bun.isdigit() and ji.isdigit() and len(bun)<=4 and len(ji)<=4):
        return None
    return bjd+('2' if gb=='1' else '1')+bun.zfill(4)+ji.zfill(4)


def scan_titles(path,targets):
    found=defaultdict(list); sha=hashlib.sha256(); n=0
    with path.open('rb') as stream:
        for n,line in enumerate(stream,1):
            sha.update(line)
            pk=line.split(b'|',1)[0].decode('ascii').strip()
            if pk in targets:
                parts=line.rstrip(b'\r\n').decode('utf-8-sig').split('|')
                if len(parts) not in (76,77): raise ValueError('Unexpected title schema')
                found[pk].append({'pnu':pnu_from_fields(parts,8),'raw_sigungu':parts[8],
                    'ledger_kind':parts[2],'ledger_type':parts[4],
                    'main_aux_code':parts[23],'main_aux_label':parts[24],
                    'lot_label':parts[5],'special_land_label':parts[13],'block':parts[14],'lot_block':parts[15],
                    'related_lot_count':parts[16], 'auxiliary_building_count':parts[47],
                    'raw_gross_area':parts[28],'raw_title_area':parts[25],'raw_column_count':len(parts)})
                found[pk][-1]['raw_identity_fields']=parts[8:13]
                if found[pk][-1]['pnu'] is None:
                    identity=parts[8:13]
                    found[pk][-1]['identity_exception']='unknown_land_type' if identity[2].strip() not in ('0','1') else 'missing_main_lot' if not identity[3].strip() else 'missing_sub_lot' if not identity[4].strip() else 'other_identity_conflict'
            if n%2000000==0: print(path.parent.name,'scanned',n,flush=True)
    return dict(found),{'filename':path.parent.name+'/'+path.name,'sha256':sha.hexdigest(),'rows':n,'target_pks_found':len(found),'duplicate_target_pks':sum(len(v)>1 for v in found.values())}


def scan_summary(path,targets):
    result=defaultdict(list); sha=hashlib.sha256(); n=0
    with path.open('rb') as stream:
        for n,line in enumerate(stream,1):
            sha.update(line)
            parts=line.rstrip(b'\r\n').split(b'|')
            if len(parts)<25: raise ValueError('Short summary record')
            identity=[v.decode('ascii').strip() for v in parts[10:15]]
            pnu=pnu_from_fields(identity,0)
            if pnu in targets:
                result[pnu].append({'first_field_identifier':parts[0].decode('utf-8'),
                                    'raw_land_area':parts[24].decode('utf-8')})
    return dict(result),{'filename':path.parent.name+'/'+path.name,'sha256':sha.hexdigest(),'rows':n,'target_pnus_found':len(result)}


def scan_traits(year,targets):
    folder=ROOT/'raw/raw addition/토지특성정보(브이월드)'
    paths=sorted(folder.glob(f'AL_D194_4311?_{year}*.zip'))
    if len(paths)!=4: raise ValueError('Missing four district trait sources')
    result=defaultdict(list); inventory=[]
    for path in paths:
        with zipfile.ZipFile(path) as archive:
            members=[n for n in archive.namelist() if n.lower().endswith('.dbf')]
            if len(members)!=1: raise ValueError('Ambiguous DBF member')
            with archive.open(members[0]) as stream:
                header=stream.read(32); count=struct.unpack('<I',header[4:8])[0]; hl,rl=struct.unpack('<HH',header[8:12])
                fields={}; offset=1
                for _ in range((hl-33)//32):
                    field=stream.read(32); name=field[:11].split(b'\0')[0].decode('ascii'); fields[name]=(offset,field[16]); offset+=field[16]
                stream.read(hl-32-32*len(fields)); sample=stream.read(rl)
                try: sample.decode('utf-8'); encoding='utf-8'
                except UnicodeDecodeError: sample.decode('cp949'); encoding='cp949'
                stream.seek(hl)
                for _ in range(count):
                    record=stream.read(rl)
                    if len(record)!=rl: raise ValueError('Truncated DBF')
                    if record[:1]==b'*': continue
                    off,size=fields['A1']; pnu=record[off:off+size].decode('ascii').strip()
                    if pnu in targets:
                        values={}
                        for name in ('A6','A8','A12','A25','A26'):
                            off,size=fields[name]; values[name]=record[off:off+size].decode(encoding).replace('\0','').strip()
                        result[pnu].append({'file':path.name,**values})
        inventory.append({'filename':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'rows':count})
    return dict(result),inventory


def main():
    with (OUT/'building_relation_review_queue.csv').open(encoding='utf-8-sig',newline='') as stream:
        queue=list(csv.DictReader(stream))
    pks={r['mgmt_pk'] for r in queue if r['mgmt_pk']}
    pnus={r['pnu'] for r in queue}|{r['previous_pnu'] for r in queue if r['previous_pnu']}
    titles={}; summaries={}; traits={}; inventories=[]
    for snapshot in sorted(SNAPSHOTS):
        titles[snapshot],meta=scan_titles(title_path(snapshot),pks); inventories.append({'snapshot':snapshot,'source':'title',**meta})
        path=bldrgst_dir()/f'국토교통부_건축물대장_총괄표제부+({SNAPSHOTS[snapshot]})'/'mart_djy_02.txt'
        summaries[snapshot],meta=scan_summary(path,pnus); inventories.append({'snapshot':snapshot,'source':'summary',**meta})
        year=int(snapshot[:4]); traits[year],meta=scan_traits(year,pnus); inventories.extend({'year':year,'source':'traits',**m} for m in meta)
        print('completed originals',snapshot,flush=True)
    reviewed=[]; counts=Counter(); categories=Counter()
    for row in queue:
        snapshot=row['snapshot']; current=titles[snapshot].get(row['mgmt_pk'],[]) if row['mgmt_pk'] else []
        evidence={'title_records':current,'summary_same_address_records':summaries[snapshot].get(row['pnu'],[]),
                  'raw_trait_records':traits[int(snapshot[:4])].get(row['pnu'],[])}
        status='source_observations_only'
        if row['reason']=='address_pnu_changed':
            older=max(s for s in SNAPSHOTS if s<snapshot)
            prior=titles[older].get(row['mgmt_pk'],[]); evidence['previous_title_records']=prior
            status='raw_address_change_confirmed' if len(current)==len(prior)==1 and current[0]['pnu']==row['pnu'] and prior[0]['pnu']==row['previous_pnu'] else 'raw_address_change_unresolved'
        elif row['reason']=='missing_title_observation_retained':
            latest=titles['2026-07'].get(row['mgmt_pk'],[]); evidence['latest_title_records']=latest
            status='absent_from_whole_latest_title_file' if not latest else 'present_in_latest_raw_file'
        elif row['reason']=='address_without_same_year_trait':
            status='raw_title_and_trait_absence_confirmed' if len(current)==1 and current[0]['pnu']==row['pnu'] and not evidence['raw_trait_records'] else 'raw_link_difference_requires_review'
        elif row['reason'].startswith('price_'):
            values=evidence['raw_trait_records']
            status='raw_overflow_confirmed' if len(values)==1 and values[0]['A25'] and set(values[0]['A25'])=={'*'} else 'raw_price_observation_retained'
        for value in current: categories[(value['ledger_kind'],value['main_aux_label'])]+=1
        reviewed.append({**row,'source_review_status':status,'evidence':evidence})
        counts[status]+=1
    with gzip.open(OUT/'building_relation_source_evidence.json.gz','wt',encoding='utf-8') as stream:
        json.dump(reviewed,stream,ensure_ascii=False)
    summary={'run_date':date.today().isoformat(),'review_rows':len(reviewed),'counts':dict(counts),
             'strict_identity_exceptions':dict(Counter(v['identity_exception'] for records in titles.values() for values in records.values() for v in values if 'identity_exception' in v)),
             'title_categories':[{'ledger_kind':k,'main_aux_label':m,'observations':n} for (k,m),n in categories.items()],
             'review_rows_with_same_address_summary':sum(bool(r['evidence']['summary_same_address_records']) for r in reviewed),
             'raw_inventory':inventories,
             'supplied_building_files':[str(p.relative_to(bldrgst_dir())) for p in sorted(bldrgst_dir().rglob('*')) if p.is_file()],
             'limitations':['Source replay confirms observations, not independent transaction-match accuracy or legal event causes.',
                            'Summary PNU equality is co-address evidence, not a certified title-parent relationship.',
                            'Related-lot count and auxiliary-building count are not identifier lists.',
                            'No supplied additional-parcel mapping or explicit parent/child relationship file was found in the current building source inventory.']}
    (LAB/'cheongju_relation_source_evidence.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='raw_inventory'},ensure_ascii=True),flush=True)


if __name__=='__main__': main()
