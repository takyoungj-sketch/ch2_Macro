"""Local SQLite normalized building/parcel observations, never a production writer."""
import hashlib
import json
import re
import sqlite3
from decimal import Decimal

from ledger_staging import attributes as land_attributes

DISTRICTS = {'43111', '43112', '43113', '43114'}
BUILDING_FIELDS = ('ledger_kind', 'main_purpose', 'gross_area', 'plat_area', 'title_land_area', 'approve_date')


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(encode(value).encode('utf-8')).hexdigest()


def building_attributes(row):
    result = {field: str(row.get(field) or '').strip() for field in BUILDING_FIELDS}
    for field in ('gross_area', 'plat_area', 'title_land_area'):
        if result[field]:
            value = Decimal(result[field])
            if not value.is_finite():
                raise ValueError('Nonfinite building area')
            result[field] = format(value.normalize(), 'f')
    return result


def validate_pnu(pnu):
    if not re.fullmatch(r'[0-9]{10}[12][0-9]{8}', pnu) or pnu[:5] not in DISTRICTS:
        raise ValueError('Invalid or out-of-scope PNU')


def connect(path):
    db = sqlite3.connect(path)
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS source_snapshot(id TEXT PRIMARY KEY,manifest TEXT NOT NULL,counts TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS building_entity(pk TEXT PRIMARY KEY);
    CREATE TABLE IF NOT EXISTS parcel_identity(pnu TEXT PRIMARY KEY);
    CREATE TABLE IF NOT EXISTS building_version(id INTEGER PRIMARY KEY,pk TEXT NOT NULL REFERENCES building_entity(pk),hash TEXT NOT NULL,payload TEXT NOT NULL,UNIQUE(pk,hash));
    CREATE TABLE IF NOT EXISTS parcel_version(id INTEGER PRIMARY KEY,pnu TEXT NOT NULL REFERENCES parcel_identity(pnu),hash TEXT NOT NULL,payload TEXT NOT NULL,UNIQUE(pnu,hash));
    CREATE TABLE IF NOT EXISTS building_observation(snapshot TEXT NOT NULL REFERENCES source_snapshot(id),pk TEXT NOT NULL REFERENCES building_entity(pk),version INTEGER NOT NULL REFERENCES building_version(id),PRIMARY KEY(snapshot,pk));
    CREATE TABLE IF NOT EXISTS parcel_observation(snapshot TEXT NOT NULL REFERENCES source_snapshot(id),pnu TEXT NOT NULL REFERENCES parcel_identity(pnu),version INTEGER NOT NULL REFERENCES parcel_version(id),PRIMARY KEY(snapshot,pnu));
    CREATE TABLE IF NOT EXISTS assessed_price_observation(snapshot TEXT NOT NULL,pnu TEXT NOT NULL,price_year INTEGER,raw_year TEXT NOT NULL,raw_price TEXT NOT NULL,status TEXT NOT NULL,PRIMARY KEY(snapshot,pnu),FOREIGN KEY(snapshot,pnu) REFERENCES parcel_observation(snapshot,pnu));
    CREATE TABLE IF NOT EXISTS address_relation_observation(snapshot TEXT NOT NULL,pk TEXT NOT NULL,pnu TEXT NOT NULL REFERENCES parcel_identity(pnu),relation_kind TEXT NOT NULL CHECK(relation_kind='title_address'),trait_present INTEGER NOT NULL CHECK(trait_present IN (0,1)),PRIMARY KEY(snapshot,pk),FOREIGN KEY(snapshot,pk) REFERENCES building_observation(snapshot,pk));
    CREATE TABLE IF NOT EXISTS current_building(pk TEXT PRIMARY KEY REFERENCES building_entity(pk),version INTEGER NOT NULL REFERENCES building_version(id),pnu TEXT NOT NULL REFERENCES parcel_identity(pnu),last_snapshot TEXT NOT NULL REFERENCES source_snapshot(id));
    CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    ''')
    return db


def ingest(db, snapshot, buildings, traits, manifest, fail_after=None):
    if not re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])', snapshot):
        raise ValueError('Invalid snapshot order')
    if set(manifest['source_districts']) != DISTRICTS:
        raise ValueError('Incomplete district manifest')
    for field in ('building_sha256', 'trait_sha256', 'scope_sha256'):
        if not re.fullmatch(r'[0-9a-f]{64}', manifest[field]):
            raise ValueError('Invalid manifest digest')
    b = {}
    for row in buildings:
        pk, pnu = str(row['mgmt_pk']).strip(), str(row['pnu']).strip()
        validate_pnu(pnu)
        if not pk or row['snapshot'] != snapshot or row['beopjungri_code'] != pnu[:10]:
            raise ValueError('Building identity conflict')
        value = {'pnu': pnu, 'attributes': building_attributes(row)}
        if pk in b:
            raise ValueError('Duplicate building PK')
        b[pk] = value
    if len(b) != manifest['expected_buildings'] or {v['pnu'][:5] for v in b.values()} != DISTRICTS:
        raise ValueError('Incomplete building scope')
    p = {}
    prices = {}
    for row in traits:
        pnu = row['pnu']
        validate_pnu(pnu)
        raw_year = row['year'].strip()
        price_year = None if raw_year in ('', '0') else int(raw_year)
        if row['bjd'] != pnu[:10] or (price_year is not None and price_year != manifest['trait_year']):
            raise ValueError('Trait identity/year conflict')
        if pnu in p:
            raise ValueError('Duplicate trait PNU')
        normalized = land_attributes(row)
        raw_price = normalized.pop('price')
        status = 'missing_or_nonpositive'
        if raw_price and set(raw_price) == {'*'}:
            status = 'source_overflow'
        elif raw_price and Decimal(raw_price) > 0:
            status = 'positive' if price_year is not None else 'unknown_price_year'
        p[pnu] = normalized
        prices[pnu] = {'price_year': price_year, 'raw_year': raw_year, 'raw_price': raw_price, 'status': status}
    if len(p) != manifest['expected_traits']:
        raise ValueError('Incomplete trait scope')
    full_manifest = {**manifest, 'normalization_version': 'building-relation-v1',
                     'normalized_content_sha256': digest({'buildings': b, 'traits': p, 'prices': prices})}
    manifest_text = encode(full_manifest)
    existing = db.execute('SELECT manifest,counts FROM source_snapshot WHERE id=?', (snapshot,)).fetchone()
    if existing:
        if existing[0] != manifest_text:
            raise ValueError('Same snapshot has different content/manifest')
        return {**json.loads(existing[1]), 'idempotent_replay': True}
    latest = db.execute('SELECT MAX(id) FROM source_snapshot').fetchone()[0]
    if latest and snapshot < latest:
        raise ValueError('New older snapshot cannot silently replace chronology')
    old = {pk: (h, pnu) for pk, h, pnu in db.execute('SELECT c.pk,v.hash,c.pnu FROM current_building c JOIN building_version v ON c.version=v.id')}
    counts = {'building_rows': len(b), 'trait_rows': len(p), 'new_buildings': 0, 'attribute_changed': 0,
              'attribute_unchanged': 0, 'address_changed': 0, 'missing_not_deleted': len(set(old)-set(b)),
              'relations_with_traits': 0, 'relations_without_traits': 0}
    with db:
        db.execute('INSERT INTO source_snapshot VALUES (?,?,?)', (snapshot, manifest_text, '{}'))
        for pnu, payload in p.items():
            db.execute('INSERT OR IGNORE INTO parcel_identity VALUES (?)', (pnu,))
            h = digest(payload)
            db.execute('INSERT OR IGNORE INTO parcel_version(pnu,hash,payload) VALUES (?,?,?)', (pnu, h, encode(payload)))
            version = db.execute('SELECT id FROM parcel_version WHERE pnu=? AND hash=?', (pnu, h)).fetchone()[0]
            db.execute('INSERT INTO parcel_observation VALUES (?,?,?)', (snapshot, pnu, version))
            price = prices[pnu]
            db.execute('INSERT INTO assessed_price_observation VALUES (?,?,?,?,?,?)',
                       (snapshot, pnu, price['price_year'], price['raw_year'], price['raw_price'], price['status']))
        for index, (pk, value) in enumerate(sorted(b.items())):
            pnu, payload = value['pnu'], value['attributes']
            h = digest(payload)
            if pk not in old:
                counts['new_buildings'] += 1
            else:
                counts['attribute_changed' if old[pk][0] != h else 'attribute_unchanged'] += 1
                counts['address_changed'] += int(old[pk][1] != pnu)
            db.execute('INSERT OR IGNORE INTO building_entity VALUES (?)', (pk,))
            db.execute('INSERT OR IGNORE INTO parcel_identity VALUES (?)', (pnu,))
            db.execute('INSERT OR IGNORE INTO building_version(pk,hash,payload) VALUES (?,?,?)', (pk, h, encode(payload)))
            version = db.execute('SELECT id FROM building_version WHERE pk=? AND hash=?', (pk, h)).fetchone()[0]
            db.execute('INSERT INTO building_observation VALUES (?,?,?)', (snapshot, pk, version))
            present = int(pnu in p)
            db.execute('INSERT INTO address_relation_observation VALUES (?,?,?,?,?)', (snapshot, pk, pnu, 'title_address', present))
            counts['relations_with_traits' if present else 'relations_without_traits'] += 1
            db.execute('INSERT INTO current_building VALUES (?,?,?,?) ON CONFLICT(pk) DO UPDATE SET version=excluded.version,pnu=excluded.pnu,last_snapshot=excluded.last_snapshot', (pk, version, pnu, snapshot))
            if fail_after and index+1 >= fail_after:
                raise RuntimeError('Injected failure')
        db.execute('UPDATE source_snapshot SET counts=? WHERE id=?', (encode(counts), snapshot))
        db.execute("INSERT INTO state VALUES ('head',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (snapshot,))
    return counts


def restore(db, snapshot):
    if not db.execute('SELECT 1 FROM source_snapshot WHERE id=?', (snapshot,)).fetchone():
        raise ValueError('Unknown snapshot')
    with db:
        db.execute('DELETE FROM current_building')
        db.execute('''INSERT INTO current_building SELECT b.pk,b.version,r.pnu,b.snapshot
          FROM building_observation b JOIN address_relation_observation r ON r.snapshot=b.snapshot AND r.pk=b.pk
          JOIN (SELECT pk,MAX(snapshot) snapshot FROM building_observation WHERE snapshot<=? GROUP BY pk) x
          ON x.pk=b.pk AND x.snapshot=b.snapshot''', (snapshot,))
        db.execute("UPDATE state SET value=? WHERE key='head'", (snapshot,))


def state_fingerprint(db):
    tables = ('source_snapshot', 'building_entity', 'parcel_identity', 'building_version', 'parcel_version',
              'building_observation', 'parcel_observation', 'assessed_price_observation', 'address_relation_observation', 'current_building', 'state')
    return digest({table: db.execute('SELECT * FROM '+table+' ORDER BY '+ ('key' if table == 'state' else '1,2' if table not in ('building_entity','parcel_identity') else '1')).fetchall() for table in tables})
