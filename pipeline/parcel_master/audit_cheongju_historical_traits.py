"""Validate 2019-22 source DBFs, preserve normalized local attributes only.

No DB access; no extraction or modification of downloaded archives.
"""
import csv
import gzip
import hashlib
import json
import re
import struct
import zipfile
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'raw/raw addition/토지특성정보(브이월드)'
OUT = ROOT / 'data/research/cheongju_ledger'
OUT.mkdir(parents=True, exist_ok=True)
reports = []
for year in range(2019, 2023):
    files = sorted(RAW.glob(f'AL_4311?_D194_{year}*.zip'))
    districts = [re.search(r'AL_(\d{5})_', p.name).group(1) for p in files]
    if sorted(districts) != ['43111', '43112', '43113', '43114']:
        raise ValueError(f'{year}: require exactly one snapshot per district: {districts}')
    cache = OUT / f'traits_{year}.csv.gz'
    temporary = cache.with_suffix('.gz.pending')
    seen_year = set()
    with gzip.open(temporary, 'wt', encoding='utf-8', newline='') as output:
        writer = None
        for src in files:
            district = re.search(r'AL_(\d{5})_', src.name).group(1)
            seen = set()
            values = {key: Counter() for key in ('A8', 'A9', 'A26')}
            missing = Counter()
            code_without_label = Counter()
            counts = Counter()
            with zipfile.ZipFile(src) as archive:
                with archive.open(next(n for n in archive.namelist() if n.lower().endswith('.dbf'))) as stream:
                    header = stream.read(32)
                    n = struct.unpack('<I', header[4:8])[0]
                    hl, rl = struct.unpack('<HH', header[8:12])
                    fields = {}
                    offset = 1
                    for _ in range((hl - 33) // 32):
                        descriptor = stream.read(32)
                        name = descriptor[:11].split(b'\0')[0].decode('ascii')
                        fields[name] = (offset, descriptor[16])
                        offset += descriptor[16]
                    required = {f'A{i}' for i in range(1, 27)}
                    if not required.issubset(fields):
                        raise ValueError(f'{src.name}: unexpected schema')
                    stream.read(hl - 32 - 32 * len(fields))
                    sample = stream.read(rl)
                    try:
                        sample.decode('utf-8')
                        encoding = 'utf-8'
                    except UnicodeDecodeError:
                        sample.decode('cp949')
                        encoding = 'cp949'
                    stream.seek(hl)
                    for _ in range(n):
                        row = stream.read(rl)
                        if len(row) != rl:
                            raise ValueError('truncated DBF')
                        if row[:1] == b'*':
                            counts['deleted'] += 1
                            continue
                        row.decode(encoding)  # strict whole-record decoding
                        r = {key: row[a:a+l].decode(encoding).replace('\0', '').strip() for key, (a, l) in fields.items()}
                        pnu = r['A1']
                        counts['active_rows'] += 1
                        counts['invalid_pnu'] += not bool(re.fullmatch(r'\d{19}', pnu))
                        counts['wrong_district'] += not pnu.startswith(district)
                        counts['duplicate_pnu'] += pnu in seen
                        counts['cross_district_duplicate'] += pnu in seen_year
                        seen.add(pnu)
                        seen_year.add(pnu)
                        for key in values:
                            values[key][r[key] or '<EMPTY>'] += 1
                        for key in required:
                            if not r[key]:
                                missing[key] += 1
                        try:
                            price = Decimal(r['A25'])
                            positive = price.is_finite() and price > 0
                        except InvalidOperation:
                            positive = False
                        counts['nonpositive_or_missing_price'] += not positive
                        counts['year_with_positive_price'] += r['A8'] == str(year) and positive
                        for code, label in ((13,14),(15,16),(17,18),(19,20),(21,22),(23,24)):
                            if r[f'A{code}'].isdigit() and int(r[f'A{code}']) > 0 and not r[f'A{label}']:
                                code_without_label[f'A{code}/A{label}'] += 1
                        normalized = {'pnu':pnu,'bjd':r['A2'],'lot':r['A6'],'year':r['A8'],'month':r['A9'],
                                      'jimok_code':r['A10'],'jimok_label':r['A11'],'area':r['A12'],
                                      'zone1_code':r['A13'],'zone1_label':r['A14'],'zone2_code':r['A15'],'zone2_label':r['A16'],
                                      'use_code':r['A17'],'use_label':r['A18'],'height_code':r['A19'],'height_label':r['A20'],
                                      'shape_code':r['A21'],'shape_label':r['A22'],'road_code':r['A23'],'road_label':r['A24'],
                                      'price':r['A25'],'trait_asof':r['A26'],'trait_source':src.name}
                        if writer is None:
                            writer = csv.DictWriter(output, fieldnames=list(normalized))
                            writer.writeheader()
                        writer.writerow(normalized)
                    stream.read()  # consume EOF so archive integrity errors surface
            report = {'file':src.name,'year':year,'district':district,'zip_bytes':src.stat().st_size,
                      'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'encoding':encoding,'rows':n,
                      'unique_pnu':len(seen),'counts':dict(counts),'missing_fields':dict(missing),
                      'positive_code_without_label':dict(code_without_label),
                      'source_dates_and_years':{k:dict(v) for k,v in values.items()}}
            reports.append(report)
            print(src.name, n, 'positive_year_price',counts['year_with_positive_price'], flush=True)
    temporary.replace(cache)
report = {'run_date':'2026-10-04','files':reports,
          'limitations':['Source base dates are not legal effective dates or historical availability dates.',
                         'Price presence does not validate transaction-to-parcel matching.',
                         'Historical code labels require a verified dictionary; blank labels are preserved.'],
          'year_summary':{str(y):{'rows':sum(r['rows'] for r in reports if r['year']==y),
                                 'year_with_positive_price':sum(r['counts']['year_with_positive_price'] for r in reports if r['year']==y),
                                 'cache_bytes':(OUT/f'traits_{y}.csv.gz').stat().st_size} for y in range(2019,2023)}}
(ROOT/'docs/lab/cheongju_historical_traits_20261004.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report['year_summary']), flush=True)
