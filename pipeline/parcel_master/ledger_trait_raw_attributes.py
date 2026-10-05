"""Read all DBF attributes for selected input parcels; do not read/edit geometry."""
import gzip
import hashlib
import json
import struct
import zipfile
from collections import Counter
from datetime import date

from ledger_consumer_input_preview import ROOT,OUT,LAB
from building_source_staging_v2 import digest


def scan(path, targets):
    found={}
    with zipfile.ZipFile(path) as archive:
        members=[n for n in archive.namelist() if n.lower().endswith('.dbf')]
        if len(members)!=1: raise ValueError('Ambiguous DBF')
        with archive.open(members[0]) as stream:
            header=stream.read(32); count=struct.unpack('<I',header[4:8])[0]
            hl,rl=struct.unpack('<HH',header[8:12]); fields={}; offset=1
            for _ in range((hl-33)//32):
                field=stream.read(32); name=field[:11].split(b'\0')[0].decode('ascii')
                fields[name]=(offset,field[16]); offset+=field[16]
            if not {'A1','A2'}<=set(fields): raise ValueError('Missing identity fields')
            stream.seek(hl); sample=stream.read(rl)
            try: sample.decode('utf-8'); encoding='utf-8'
            except UnicodeDecodeError: sample.decode('cp949'); encoding='cp949'
            stream.seek(hl)
            for _ in range(count):
                record=stream.read(rl)
                if len(record)!=rl: raise ValueError('Truncated DBF')
                if record[:1]==b'*': continue
                off,size=fields['A1']; pnu=record[off:off+size].decode('ascii').replace('\0','').strip()
                if pnu not in targets: continue
                raw={name:record[off:off+size].decode(encoding).replace('\0','').strip() for name,(off,size) in fields.items()}
                if pnu in found or raw['A2']!=pnu[:10]: raise ValueError('Duplicate or conflicting DBF identity')
                found[pnu]=raw
    return found,{'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                  'dbf_member':members[0],'rows':count,'fields':list(fields),'encoding':encoding}


def main():
    path=OUT/'ledger_consumer_input_traits_v2.json.gz'; before=hashlib.sha256(path.read_bytes()).hexdigest()
    with gzip.open(path,'rt',encoding='utf-8') as stream: rows=json.load(stream)
    old=json.loads((LAB/'cheongju_relation_source_evidence.json').read_text(encoding='utf-8'))
    expected={r['filename']:r for r in old['raw_inventory'] if r['source']=='traits'}
    batches=[]; inventories=[]; all_fields=set(); checks={}
    for snapshot in sorted({r['title_snapshot'] for r in rows}):
        selected=[r for r in rows if r['title_snapshot']==snapshot]
        targets={r['address_pnu'] for r in selected if r['traits']['status']=='observed'}
        paths=sorted((ROOT/'raw/raw addition/토지특성정보(브이월드)').glob(f'AL_D194_4311?_{snapshot[:4]}*.zip'))
        if len(paths)!=4: raise ValueError('Incomplete source districts')
        records={}; provenance={}
        for source in paths:
            found,meta=scan(source,targets)
            if meta['sha256']!=expected[source.name]['sha256'] or meta['rows']!=expected[source.name]['rows']:
                raise ValueError('Original differs from frozen source evidence')
            if set(records)&set(found): raise ValueError('Cross-file duplicate PNU')
            records.update(found); provenance.update({p:meta for p in found})
            inventories.append({'snapshot':snapshot,**meta}); all_fields.update(meta['fields'])
        if set(records)!=targets: raise ValueError('Retained input not found in original DBF')
        label_blanks=Counter()
        for row in selected:
            if row['traits']['status']!='observed':
                row['traits']['original_dbf']=None; continue
            pnu=row['address_pnu']; raw=records[pnu]; meta=provenance[pnu]
            row['traits']['original_dbf']={'payload_version':'traits-raw-dbf-v1','raw_fields':raw,'raw_record_hash':digest(raw),
                'source_zip_sha256':meta['sha256'],'source_file':meta['file'],'dbf_member':meta['dbf_member'],'encoding':meta['encoding']}
            for name in ('A18','A20','A22','A24'):
                if name in raw and not raw[name]: label_blanks[name]+=1
        batches.append({'snapshot':snapshot,'original_attribute_input_rows':sum(r['traits']['status']=='observed' for r in selected),
                        'distinct_original_pnus':len(records),'blank_additional_label_fields_in_title_inputs':dict(label_blanks)})
        print('original DBF fields attached',snapshot,len(records),flush=True)
    checks['all_selected_trait_records_found_in_originals']=True
    checks['all_dbf_fields_preserved']=all(set(r['traits']['original_dbf']['raw_fields'])==set(next(m['fields'] for m in inventories if m['file']==r['traits']['original_dbf']['source_file'])) for r in rows if r['traits']['status']=='observed')
    checks['blocked_or_missing_inputs_have_no_raw_trait']=all(r['traits']['original_dbf'] is None for r in rows if r['traits']['status']!='observed')
    checks['prior_extended_preview_unchanged']=hashlib.sha256(path.read_bytes()).hexdigest()==before
    if not all(checks.values()): raise AssertionError(checks)
    with gzip.open(OUT/'ledger_consumer_input_traits_full_dbf.json.gz','wt',encoding='utf-8') as stream:
        json.dump(rows,stream,ensure_ascii=False)
    report={'run_date':date.today().isoformat(),'dbf_attribute_fields':sorted(all_fields,key=lambda n:int(n[1:]) if n[1:].isdigit() else n),
            'batches':batches,'raw_source_inventory':inventories,'checks':checks,
            'limitations':['All original DBF attribute columns for selected observed parcels; SHP geometry excluded.',
                           'Raw additional fields are preserved, not mapped into new regression variables or certified code meanings.',
                           'Neither product matching nor historical information availability is certified.']}
    (LAB/'ledger_consumer_input_traits_full_dbf.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='raw_source_inventory'},ensure_ascii=True),flush=True)


if __name__=='__main__': main()
