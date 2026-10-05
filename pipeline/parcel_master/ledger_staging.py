"""Local SQLite prototype, never connected to production PostgreSQL."""
import hashlib
import json
import sqlite3
from datetime import date
from decimal import Decimal

DISTRICTS={'43111','43112','43113','43114'}
ATTRIBUTES=('bjd','lot','jimok_code','area','zone1_code','zone2_code','use_code','height_code','shape_code','road_code','price')

def attributes(row):
    values={key:row.get(key,'') for key in ATTRIBUTES}
    for key in ('area','price'):
        # DBF asterisks denote numeric overflow, not a value to impute.
        if values[key] and set(values[key])!={'*'}:
            number=Decimal(values[key])
            if not number.is_finite():raise ValueError('Nonfinite attribute')
            values[key]=format(number.normalize(),'f')
    for key in ATTRIBUTES:
        if key.endswith('_code') and values[key].isdigit():values[key]=str(int(values[key]))
    return values

def connect(path):
    db=sqlite3.connect(path)
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY, manifest TEXT NOT NULL, counts TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS versions(id INTEGER PRIMARY KEY, pnu TEXT NOT NULL, hash TEXT NOT NULL, payload TEXT NOT NULL, created_snapshot TEXT NOT NULL REFERENCES snapshots(id));
    CREATE TABLE IF NOT EXISTS membership(snapshot TEXT NOT NULL REFERENCES snapshots(id), pnu TEXT NOT NULL, version INTEGER NOT NULL REFERENCES versions(id), PRIMARY KEY(snapshot,pnu));
    CREATE TABLE IF NOT EXISTS current_values(pnu TEXT PRIMARY KEY, version INTEGER NOT NULL REFERENCES versions(id), last_snapshot TEXT NOT NULL REFERENCES snapshots(id));
    CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    ''')
    return db

def ingest(db,snapshot,rows,manifest,fail_after=None):
    if set(manifest['source_districts'])!=DISTRICTS:raise ValueError('Incomplete source district coverage')
    source_hash=manifest.get('sha256','')
    if len(source_hash)!=64 or any(c not in '0123456789abcdef' for c in source_hash):raise ValueError('Invalid source digest')
    unique={}
    for row in rows:
        pnu=row['pnu']
        if len(pnu)!=19 or not pnu.isdigit() or pnu[:5] not in DISTRICTS:raise ValueError('Invalid PNU')
        date.fromisoformat(row['trait_asof'][:10])
        normalized=attributes(row)
        if pnu in unique and unique[pnu]!=normalized:raise ValueError('Conflicting duplicate')
        unique[pnu]=normalized
    if len(unique)!=manifest['expected_unique_pnu']:raise ValueError('Source row count mismatch')
    if {p[:5] for p in unique}!=DISTRICTS:raise ValueError('Missing district in input')
    content=hashlib.sha256()
    for pnu in sorted(unique):
        content.update((pnu+json.dumps(unique[pnu],sort_keys=True,ensure_ascii=False)).encode())
    manifest={**manifest,'normalized_content_sha256':content.hexdigest(),'normalization_version':'pilot-v1'}
    encoded=json.dumps(manifest,sort_keys=True,ensure_ascii=False)
    prior=db.execute('SELECT manifest,counts FROM snapshots WHERE id=?',(snapshot,)).fetchone()
    if prior:
        if prior[0]!=encoded:raise ValueError('Existing snapshot manifest differs')
        return {**json.loads(prior[1]),'idempotent_replay':True}
    head=db.execute("SELECT value FROM state WHERE key='head'").fetchone()
    if head and snapshot<head[0]:raise ValueError('Older batch cannot silently replace current state')
    existing={p:(v,h) for p,v,h in db.execute('SELECT c.pnu,c.version,v.hash FROM current_values c JOIN versions v ON v.id=c.version')}
    counts={'new':0,'changed':0,'unchanged':0,'missing_not_deleted':len(set(existing)-set(unique)),'rows':len(unique)}
    with db:
        db.execute('INSERT INTO snapshots VALUES (?,?,?)',(snapshot,encoded,'{}'))
        for i,(pnu,payload) in enumerate(unique.items()):
            text=json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':'));digest=hashlib.sha256(text.encode()).hexdigest()
            old=existing.get(pnu)
            if old and old[1]==digest:version=old[0];counts['unchanged']+=1
            else:
                counts['changed' if old else 'new']+=1
                version=db.execute('INSERT INTO versions(pnu,hash,payload,created_snapshot) VALUES (?,?,?,?)',(pnu,digest,text,snapshot)).lastrowid
            db.execute('INSERT INTO membership VALUES (?,?,?)',(snapshot,pnu,version))
            db.execute('INSERT INTO current_values VALUES (?,?,?) ON CONFLICT(pnu) DO UPDATE SET version=excluded.version,last_snapshot=excluded.last_snapshot',(pnu,version,snapshot))
            if fail_after is not None and i+1>=fail_after:raise RuntimeError('Injected batch failure')
        db.execute('UPDATE snapshots SET counts=? WHERE id=?',(json.dumps(counts),snapshot))
        db.execute("INSERT INTO state VALUES ('head',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(snapshot,))
    return counts

def restore(db,snapshot):
    """Rebuild current from all observations up to the selected stored snapshot.

    Only the local pilot's ISO-ordered snapshot IDs are accepted. Old versions
    and membership remain immutable; missing PNUs retain their last observation.
    """
    if not db.execute('SELECT 1 FROM snapshots WHERE id=?',(snapshot,)).fetchone():raise ValueError('Unknown snapshot')
    with db:
        db.execute('DELETE FROM current_values')
        db.execute('''INSERT INTO current_values SELECT m.pnu,m.version,m.snapshot FROM membership m JOIN
          (SELECT pnu,MAX(snapshot) AS snapshot FROM membership WHERE snapshot<=? GROUP BY pnu) x
          ON m.pnu=x.pnu AND m.snapshot=x.snapshot''',(snapshot,))
        db.execute("INSERT INTO state VALUES ('head',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(snapshot,))
