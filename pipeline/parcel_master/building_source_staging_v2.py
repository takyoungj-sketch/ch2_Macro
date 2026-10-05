"""Source-preserving local prototype. No production database connections."""
import hashlib
import json
import re
import sqlite3


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(encode(value).encode('utf-8')).hexdigest()


def identity(fields):
    if len(fields) != 5:
        raise ValueError('Expected five raw identity fields')
    sg, bd, gb, bun, ji = [str(v).strip() for v in fields]
    if not re.fullmatch(r'4311[1-4]', sg):
        return None, 'invalid_district'
    if re.fullmatch(r'[0-9]{1,5}', bd):
        bjd = sg + bd.zfill(5)
    elif re.fullmatch(r'[0-9]{10}', bd) and bd.startswith(sg):
        bjd = bd
    else:
        return None, 'invalid_bjd'
    if gb not in ('0', '1'):
        return None, 'unknown_land_type'
    if not re.fullmatch(r'[0-9]{1,4}', bun):
        return None, 'invalid_main_lot'
    if not re.fullmatch(r'[0-9]{1,4}', ji):
        return None, 'invalid_sub_lot'
    return bjd + ('2' if gb == '1' else '1') + bun.zfill(4) + ji.zfill(4), 'canonical_address'


def connect(path):
    db = sqlite3.connect(path)
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS source_batch(snapshot TEXT PRIMARY KEY,manifest TEXT NOT NULL,content_hash TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS building_entity(pk TEXT PRIMARY KEY);
    CREATE TABLE IF NOT EXISTS source_version(id INTEGER PRIMARY KEY,pk TEXT NOT NULL REFERENCES building_entity(pk),raw_hash TEXT NOT NULL,raw_payload TEXT NOT NULL,UNIQUE(pk,raw_hash));
    CREATE TABLE IF NOT EXISTS title_observation(snapshot TEXT NOT NULL REFERENCES source_batch(snapshot),pk TEXT NOT NULL REFERENCES building_entity(pk),version INTEGER NOT NULL REFERENCES source_version(id),identity_status TEXT NOT NULL,PRIMARY KEY(snapshot,pk));
    CREATE TABLE IF NOT EXISTS canonical_address_relation(snapshot TEXT NOT NULL,pk TEXT NOT NULL,pnu TEXT NOT NULL CHECK(length(pnu)=19),relation_kind TEXT NOT NULL CHECK(relation_kind='title_address'),PRIMARY KEY(snapshot,pk),FOREIGN KEY(snapshot,pk) REFERENCES title_observation(snapshot,pk));
    ''')
    return db


def ingest(db, snapshot, records, manifest, fail_after=None):
    if not re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])', snapshot):
        raise ValueError('Invalid snapshot')
    if not re.fullmatch(r'[0-9a-f]{64}', manifest['source_sha256']):
        raise ValueError('Invalid source hash')
    if manifest['expected_records'] != len(records) or any(not pk.strip() for pk in records):
        raise ValueError('Invalid scope')
    # Raw strings, names, role codes and counts survive unchanged in each version.
    prepared = []
    for pk, raw in sorted(records.items()):
        pnu, status = identity(raw['raw_identity_fields'])
        if pnu != raw['pnu']:
            raise ValueError('Source replay identity conflict')
        prepared.append((pk, raw, pnu, status))
    content_hash = digest(records)
    previous = db.execute('SELECT manifest,content_hash FROM source_batch WHERE snapshot=?', (snapshot,)).fetchone()
    if previous:
        if previous != (encode(manifest), content_hash):
            raise ValueError('Snapshot replay differs')
        return False
    with db:
        db.execute('INSERT INTO source_batch VALUES(?,?,?)', (snapshot, encode(manifest), content_hash))
        for n, (pk, raw, pnu, status) in enumerate(prepared, 1):
            db.execute('INSERT OR IGNORE INTO building_entity VALUES(?)', (pk,))
            h = digest(raw)
            db.execute('INSERT OR IGNORE INTO source_version(pk,raw_hash,raw_payload) VALUES(?,?,?)', (pk, h, encode(raw)))
            version = db.execute('SELECT id FROM source_version WHERE pk=? AND raw_hash=?', (pk, h)).fetchone()[0]
            db.execute('INSERT INTO title_observation VALUES(?,?,?,?)', (snapshot, pk, version, status))
            if pnu:
                db.execute('INSERT INTO canonical_address_relation VALUES(?,?,?,?)', (snapshot, pk, pnu, 'title_address'))
            if fail_after == n:
                raise RuntimeError('Injected atomicity failure')
    return True


def fingerprint(db):
    tables = ('source_batch', 'building_entity', 'source_version', 'title_observation', 'canonical_address_relation')
    return digest({t: sorted(db.execute('SELECT * FROM '+t).fetchall()) for t in tables})
