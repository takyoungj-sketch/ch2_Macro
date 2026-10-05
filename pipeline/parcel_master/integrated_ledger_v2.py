"""One local ledger release: sources, immutable observations and atomic publication.

Publication is local source availability, never permission to enrich a product.
No production connection, automatic object membership, or regression adoption.
"""
import hashlib
import json
import re
import sqlite3

from ledger_identity_v2 import VERSION, identify
from building_relation_staging import building_attributes
from ledger_staging import attributes
from ledger_consumer_input_preview import price_input

CONTRACT = 'ledger-source-consumer-v2.2'
NAMESPACE = 'bldrgst-bulk-local-frozen-v1'


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def connect(path):
    db = sqlite3.connect(path)
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS source(id TEXT PRIMARY KEY,kind TEXT NOT NULL,manifest TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS release(id TEXT PRIMARY KEY,ordinal INTEGER NOT NULL UNIQUE,manifest TEXT NOT NULL,content_hash TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS release_source(release_id TEXT REFERENCES release(id),kind TEXT,source_id TEXT REFERENCES source(id),PRIMARY KEY(release_id,kind));
    CREATE TABLE IF NOT EXISTS building(pk TEXT PRIMARY KEY,namespace TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS building_raw(pk TEXT REFERENCES building(pk),hash TEXT,raw TEXT NOT NULL,PRIMARY KEY(pk,hash));
    CREATE TABLE IF NOT EXISTS building_attribute(pk TEXT REFERENCES building(pk),hash TEXT,payload TEXT NOT NULL,PRIMARY KEY(pk,hash));
    CREATE TABLE IF NOT EXISTS building_observation(release_id TEXT REFERENCES release(id),pk TEXT,raw_hash TEXT,attribute_hash TEXT,pnu TEXT,identity_status TEXT NOT NULL,
      PRIMARY KEY(release_id,pk),FOREIGN KEY(pk,raw_hash) REFERENCES building_raw(pk,hash),FOREIGN KEY(pk,attribute_hash) REFERENCES building_attribute(pk,hash),
      CHECK((identity_status='canonical_address' AND pnu IS NOT NULL) OR (identity_status<>'canonical_address' AND pnu IS NULL)));
    CREATE TABLE IF NOT EXISTS parcel(pnu TEXT PRIMARY KEY CHECK(length(pnu)=19 AND substr(pnu,12,4)<>'0000'));
    CREATE TABLE IF NOT EXISTS parcel_version(pnu TEXT REFERENCES parcel(pnu),hash TEXT,payload TEXT NOT NULL,PRIMARY KEY(pnu,hash));
    CREATE TABLE IF NOT EXISTS parcel_observation(release_id TEXT REFERENCES release(id),pnu TEXT,version_hash TEXT,raw TEXT NOT NULL,original_dbf TEXT,
      PRIMARY KEY(release_id,pnu),FOREIGN KEY(pnu,version_hash) REFERENCES parcel_version(pnu,hash));
    CREATE TABLE IF NOT EXISTS price_observation(release_id TEXT,pnu TEXT,price_year INTEGER,raw_year TEXT NOT NULL,raw_price TEXT NOT NULL,status TEXT NOT NULL,
      PRIMARY KEY(release_id,pnu),FOREIGN KEY(release_id,pnu) REFERENCES parcel_observation(release_id,pnu));
    CREATE TABLE IF NOT EXISTS address_relation(release_id TEXT,pk TEXT,pnu TEXT REFERENCES parcel(pnu),kind TEXT NOT NULL CHECK(kind='title_address'),
      PRIMARY KEY(release_id,pk),FOREIGN KEY(release_id,pk) REFERENCES building_observation(release_id,pk));
    CREATE TABLE IF NOT EXISTS current_building(pk TEXT PRIMARY KEY,last_seen_release TEXT,FOREIGN KEY(last_seen_release,pk) REFERENCES building_observation(release_id,pk));
    CREATE TABLE IF NOT EXISTS current_parcel(pnu TEXT PRIMARY KEY,last_seen_release TEXT,FOREIGN KEY(last_seen_release,pnu) REFERENCES parcel_observation(release_id,pnu));
    CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS building_pnu ON building_observation(release_id,pnu);
    ''')
    return db


def fingerprint(db):
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    h = hashlib.sha256()
    for table in tables:
        keys = sorted((r[5], r[1]) for r in db.execute('PRAGMA table_info('+table+')') if r[5])
        order = ','.join(name for _, name in keys)
        h.update(encode(table).encode()); h.update(b'\n')
        for row in db.execute('SELECT * FROM '+table+' ORDER BY '+order):
            h.update(encode(row).encode()); h.update(b'\n')
    return h.hexdigest()


def validate_pnu(pnu):
    if not isinstance(pnu, str) or not re.fullmatch(r'4311[1-4][0-9]{5}[12][0-9]{8}', pnu):
        raise ValueError('Invalid/out-of-scope parcel PNU')
    if int(pnu[5:10]) == 0 or int(pnu[11:15]) == 0:
        raise ValueError('Noncanonical zero identity component')


def _publish(db, release_id):
    selected = db.execute('SELECT ordinal FROM release WHERE id=?', (release_id,)).fetchone()
    if not selected: raise ValueError('Unknown release')
    for entity, field in [('building', 'pk'), ('parcel', 'pnu')]:
        db.execute('DELETE FROM current_'+entity)
        db.execute(f'''INSERT INTO current_{entity} SELECT o.{field},o.release_id FROM {entity}_observation o
          JOIN release r ON r.id=o.release_id JOIN
          (SELECT o.{field},MAX(r.ordinal) n FROM {entity}_observation o JOIN release r ON r.id=o.release_id
            WHERE r.ordinal<=? GROUP BY o.{field}) x ON x.{field}=o.{field} AND x.n=r.ordinal''', selected)
    db.execute("INSERT INTO state VALUES('published_release',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (release_id,))


def restore(db, release_id):
    with db: _publish(db, release_id)


def ingest(db, release_id, ordinal, buildings, traits, manifest, fail_at=None):
    if not release_id or isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 1:
        raise ValueError('Explicit release id/positive ordering required')
    if manifest['identity_rule'] != VERSION or manifest['pk_namespace'] != NAMESPACE:
        raise ValueError('Rule/PK namespace conflict')
    if not re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])', manifest['title_snapshot']):
        raise ValueError('Invalid title snapshot')
    if len(buildings) != manifest['expected_buildings'] or len(traits) != manifest['expected_traits']:
        raise ValueError('Incomplete release scope')
    if set(manifest['districts']) != {'43111', '43112', '43113', '43114'}:
        raise ValueError('Incomplete district declaration')
    for kind in ('title', 'traits', 'processed_building'):
        source = manifest['sources'][kind]
        if not re.fullmatch(r'[0-9a-f]{64}', source['sha256']): raise ValueError('Invalid source hash')
        if 'collected_at' not in source or 'base_date' not in source: raise ValueError('Explicit source timing required (null permitted)')
    b = {}; p = {}
    for pk, row in buildings.items():
        if not isinstance(pk, str) or not pk.strip(): raise ValueError('Missing ledger PK')
        for payload in (row['raw'], row['attributes']):
            if 'mgmt_pk' in payload and payload['mgmt_pk'] != pk:
                raise ValueError('Building source PK conflict')
        if 'snapshot' in row['attributes'] and row['attributes']['snapshot'] != manifest['title_snapshot']:
            raise ValueError('Building processed snapshot conflict')
        identity = identify(row['raw']['raw_identity_fields'])
        attr = building_attributes(row['attributes'])
        # Independent raw/processed overlap must agree; numeric formatting may differ.
        for source_field, attr_field in [('raw_gross_area','gross_area'), ('raw_title_area','title_land_area')]:
            if source_field in row['raw']:
                comparable = building_attributes({attr_field: row['raw'][source_field]})[attr_field]
                # Existing positive-area extraction intentionally converts source
                # zero to missing. Preserve both; do not restore zero as measured area.
                if comparable != attr[attr_field] and not (comparable == '0' and attr[attr_field] == ''):
                    raise ValueError('Raw/processed building attribute conflict')
        b[pk] = {'raw': row['raw'], 'attributes': attr, 'identity': identity}
    for pnu, row in traits.items():
        validate_pnu(pnu); raw = row['raw']
        if raw['pnu'] != pnu or raw['bjd'] != pnu[:10]: raise ValueError('Trait identity conflict')
        raw_year = raw['year'].strip()
        if raw_year not in ('', '0') and (not re.fullmatch(r'[0-9]{4}', raw_year) or int(raw_year) != manifest['trait_year']):
            raise ValueError('Trait year conflict')
        payload = attributes(raw); raw_price = payload.pop('price')
        year = None if raw_year in ('', '0') else int(raw_year)
        price = price_input('canonical_address', pnu, (year, raw_year, raw_price, 'preserved_source'))
        original = row.get('original_dbf')
        if original:
            fields = original['raw_fields']
            if fields.get('A1') != pnu or fields.get('A2') != pnu[:10] or original['raw_record_hash'] != digest(fields):
                raise ValueError('Original DBF identity/hash conflict')
        p[pnu] = {'raw': raw, 'payload': payload, 'original': original,
                  'year': year, 'raw_year': raw_year, 'raw_price': raw_price, 'price_status': price['status']}
    content = digest({'buildings': b, 'traits': p})
    previous = db.execute('SELECT ordinal,manifest,content_hash FROM release WHERE id=?', (release_id,)).fetchone()
    if previous:
        if previous != (ordinal, encode(manifest), content): raise ValueError('Release replay changed')
        return False
    latest = db.execute('SELECT id,ordinal FROM release ORDER BY ordinal DESC LIMIT 1').fetchone()
    if latest and ordinal <= latest[1]: raise ValueError('New release order must increase')
    head = db.execute("SELECT value FROM state WHERE key='published_release'").fetchone()
    if latest and (not head or head[0] != latest[0]): raise ValueError('Restore latest release before appending')
    with db:
        db.execute('INSERT INTO release VALUES(?,?,?,?)', (release_id, ordinal, encode(manifest), content))
        for kind, source in sorted(manifest['sources'].items()):
            source_id = digest({'kind': kind, **source})
            db.execute('INSERT OR IGNORE INTO source VALUES(?,?,?)', (source_id, kind, encode(source)))
            db.execute('INSERT INTO release_source VALUES(?,?,?)', (release_id, kind, source_id))
        if fail_at == 'sources': raise RuntimeError('Injected sources failure')
        for pnu, row in sorted(p.items()):
            h = digest(row['payload'])
            db.execute('INSERT OR IGNORE INTO parcel VALUES(?)', (pnu,))
            db.execute('INSERT OR IGNORE INTO parcel_version VALUES(?,?,?)', (pnu, h, encode(row['payload'])))
            db.execute('INSERT INTO parcel_observation VALUES(?,?,?,?,?)', (release_id, pnu, h, encode(row['raw']), encode(row['original']) if row['original'] else None))
            db.execute('INSERT INTO price_observation VALUES(?,?,?,?,?,?)', (release_id,pnu,row['year'],row['raw_year'],row['raw_price'],row['price_status']))
        if fail_at == 'traits': raise RuntimeError('Injected traits failure')
        for pk, row in sorted(b.items()):
            rh, ah = digest(row['raw']), digest(row['attributes']); identity = row['identity']
            db.execute('INSERT OR IGNORE INTO building VALUES(?,?)', (pk, NAMESPACE))
            db.execute('INSERT OR IGNORE INTO building_raw VALUES(?,?,?)', (pk, rh, encode(row['raw'])))
            db.execute('INSERT OR IGNORE INTO building_attribute VALUES(?,?,?)', (pk, ah, encode(row['attributes'])))
            db.execute('INSERT INTO building_observation VALUES(?,?,?,?,?,?)', (release_id,pk,rh,ah,identity['pnu'],identity['status']))
            if identity['pnu']:
                db.execute('INSERT OR IGNORE INTO parcel VALUES(?)', (identity['pnu'],))
                db.execute('INSERT INTO address_relation VALUES(?,?,?,?)', (release_id,pk,identity['pnu'],'title_address'))
        if fail_at == 'buildings': raise RuntimeError('Injected buildings failure')
        _publish(db, release_id)
        if fail_at == 'published': raise RuntimeError('Injected publication failure')
    return True


def consumer(db, pk):
    head = db.execute("SELECT value FROM state WHERE key='published_release'").fetchone()
    if not head: raise ValueError('No published release')
    release_id = head[0]
    selected = json.loads(db.execute('SELECT manifest FROM release WHERE id=?', (release_id,)).fetchone()[0])
    row = db.execute('''SELECT o.release_id,o.raw_hash,o.attribute_hash,o.pnu,o.identity_status,v.raw,a.payload
       FROM current_building c JOIN building_observation o ON o.release_id=c.last_seen_release AND o.pk=c.pk
       JOIN building_raw v ON v.pk=o.pk AND v.hash=o.raw_hash JOIN building_attribute a ON a.pk=o.pk AND a.hash=o.attribute_hash
       WHERE c.pk=?''', (pk,)).fetchone()
    if not row: return None
    seen, rh, ah, pnu, status, raw, attrs = row
    last_manifest = json.loads(db.execute('SELECT manifest FROM release WHERE id=?', (seen,)).fetchone()[0])
    observed = seen == release_id
    eligible = observed and status == 'canonical_address'
    land = db.execute('SELECT raw,original_dbf FROM parcel_observation WHERE release_id=? AND pnu=?', (release_id,pnu)).fetchone() if eligible else None
    price = db.execute('SELECT price_year,raw_year,raw_price,status FROM price_observation WHERE release_id=? AND pnu=?', (release_id,pnu)).fetchone() if eligible else None
    parcel_seen = db.execute('SELECT last_seen_release FROM current_parcel WHERE pnu=?', (pnu,)).fetchone() if pnu else None
    price_value = price_input(status if eligible else 'blocked', pnu if eligible else None, price)
    if not observed:
        price_value = {'status':'last_seen_not_observed','value_krw_per_m2':None,'price_year':None}
    def value(payload, source, base_date, trust, last_seen, candidate_allowed):
        return {'value': payload, 'source': source, 'base_date': base_date, 'trust_state': trust,
                'last_seen': last_seen, 'permissions': {'source_display': payload is not None,
                'candidate_research': candidate_allowed, 'product_enrichment': False,
                'quantity_aggregation': False, 'regression': False}}
    raw_decoded, attrs_decoded = json.loads(raw), json.loads(attrs)
    quality = {field: 'source_zero_processed_missing' for source_field, field in
               [('raw_gross_area','gross_area'), ('raw_title_area','title_land_area')]
               if source_field in raw_decoded and building_attributes({field: raw_decoded[source_field]})[field] == '0' and attrs_decoded[field] == ''}
    return {'contract': CONTRACT, 'published_release': release_id, 'pk_namespace': NAMESPACE,
            'management_pk': pk, 'selected_source_snapshot': selected['title_snapshot'],
            'last_seen_source_snapshot': last_manifest['title_snapshot'], 'last_seen_release': seen,
            'observed_in_selected_release': observed, 'identity_status': status, 'address_pnu': pnu,
            'raw_version_hash': rh, 'attribute_version_hash': ah,
            'building': value({'raw': raw_decoded, 'attributes': attrs_decoded, 'attribute_quality': quality}, last_manifest['sources'],
                last_manifest['sources']['title']['base_date'], status if observed else 'last_seen_not_observed', seen, eligible),
            'traits': value({'raw': json.loads(land[0]), 'original_dbf': json.loads(land[1]) if land[1] else None} if land else None,
                selected['sources']['traits'], {'row_observed_at':json.loads(land[0]).get('trait_asof'),
                 'base_year':json.loads(land[0]).get('year'), 'source_cutoff':selected['sources']['traits']['base_date']} if land else None,
                'observed' if land else 'last_seen_not_observed' if not observed else 'identity_blocked' if not eligible else 'not_observed_in_selected_release', parcel_seen[0] if parcel_seen else None, bool(land)),
            'price': value(price_value,
                selected['sources']['traits'], {'price_year': price[0]} if price else None,
                price_value['status'], parcel_seen[0] if parcel_seen else None,
                bool(price and price[3] == 'positive_known_year')),
            'membership_verified': False, 'production_apply': False}
