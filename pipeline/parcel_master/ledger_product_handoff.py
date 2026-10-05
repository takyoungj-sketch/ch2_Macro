"""Source-publication-bound compatibility supply, for local shadow consumers only."""
import copy
import gzip
import json
import sqlite3
from pathlib import Path

from integrated_ledger_v2 import CONTRACT,digest
from ledger_operations import child,identifier,read_json
from ledger_supply_bundle import sha,load_verified_supply
from ledger_supply_artifacts import write_gzip_atomic,write_json_atomic
from ledger_release_cli import open_ledger
from cheongju_numeric_supply_shadow import strict_pnu,projected_attributes,compatibility_attributes,equal_value,FIELDS,value_contract
from extend_cheongju_product_fields import product_row,EXTENSION
from compare_cheongju_integrated_product_supply import compare_price
from ledger_http_isolation import fixture_rows


def project(db,frozen,paired,baseline_sha):
    """Recompute existing matched title fields and prices from the selected DB."""
    head=db.execute("SELECT value FROM state WHERE key='published_release'").fetchone()[0]
    manifest=json.loads(db.execute('SELECT manifest FROM release WHERE id=?',(head,)).fetchone()[0])
    if manifest.get('field_extension')!=EXTENSION:raise ValueError('Original product fields required')
    expected=frozen['collective']['residential_stats']
    if [r['stats'] for r in paired['residential']]!=expected:raise ValueError('Mixed residential baseline')
    if [(r['transaction'],r['legacy_enrichment']) for r in paired['built']]!=[(r['transaction'],r['enrichment']) for r in frozen['built']['transactions']]:raise ValueError('Mixed built baseline')
    if any(paired[k]!=frozen['collective'][k] for k in ('commercial_stats','commercial_transactions')):raise ValueError('Mixed commercial baseline')
    attrs={}
    for r in frozen['collective']['attributes']:
        key=(r['building_key'],r['asset_type'])
        if key not in attrs or r['snapshot_ym']>attrs[key]['snapshot_ym']:attrs[key]=r
    prices={(r['building_key'],r['asset_type']):r for r in frozen['collective']['prices']}
    requested={strict_pnu(r['beopjungri_code'],r['lot_number']) for r in expected};requested.discard(None)
    db.execute('PRAGMA temp_store=MEMORY');db.execute('CREATE TEMP TABLE handoff_parcel(pnu TEXT PRIMARY KEY)')
    db.executemany('INSERT INTO handoff_parcel VALUES(?)',[(p,) for p in sorted(requested)])
    titles={p:[] for p in requested}
    for pnu,pk,raw,h in db.execute('''WITH selected AS MATERIALIZED (
       SELECT o.pnu,o.pk,o.raw_hash FROM building_observation o JOIN handoff_parcel p ON p.pnu=o.pnu
       WHERE o.release_id=? AND o.identity_status='canonical_address')
       SELECT s.pnu,s.pk,r.raw,r.hash FROM selected s CROSS JOIN building_raw r ON r.pk=s.pk AND r.hash=s.raw_hash ORDER BY s.pk''',(head,)):
        value=json.loads(raw)
        if digest(value)!=h or value.get('product_fields_policy')!=EXTENSION:raise ValueError('Original title payload changed')
        titles[pnu].append({'pk':pk,'raw_hash':h,'row':product_row(value['product_fields'],manifest['title_snapshot'])})
    residential=[];source_attrs=source_prices=0
    for prior in paired['residential']:
        stats=prior['stats'];key=(stats['building_key'],stats['asset_type']);old=attrs.get(key);old_price=prices.get(key)
        if old!=prior['legacy_attributes']:raise ValueError('Mixed legacy attribute binding')
        pnu=strict_pnu(stats['beopjungri_code'],stats['lot_number'])
        selected=[r for r in titles.get(pnu,[]) if r['row']['ledger_kind']=='집합']
        candidate=projected_attributes([r['row'] for r in selected],key[1]) if selected and key[1]!='presale' else None
        comparable=bool(old and old['match_rule']=='title_pnu' and old['snapshot_ym']==manifest['title_snapshot'].replace('-','') and candidate)
        equal=comparable and all(equal_value(old.get(f),candidate[f]) for f in FIELDS)
        status='title_numeric_equal' if equal else 'not_equal_or_not_comparable'
        effective,fed=compatibility_attributes(old,candidate,status,prior['review_hold'])
        if effective!=prior['compatible_attributes']:raise ValueError('Selected publication changes compatibility attributes')
        source_attrs+=fed
        price=None
        if old_price:
            row=db.execute('SELECT price_year,raw_price,status FROM price_observation WHERE release_id=? AND pnu=?',(head,old_price['representative_pnu'])).fetchone()
            price=dict(zip(('price_year','raw_price','status'),row)) if row else None
        price_equal=compare_price(old_price,price)=='same_year_equal'
        old_value=old_price['assessed_land_price'] if old_price else None
        if not equal_value(old_value,prior['legacy_price']):raise ValueError('Mixed price baseline')
        effective_price=price['raw_price'] if price_equal else old_value;source_prices+=price_equal
        if not equal_value(effective_price,prior['compatible_price']):raise ValueError('Selected publication changes compatibility price')
        def contract(value,kind,fed,refs,base):
            source={'baseline_sha256':baseline_sha,'kind':kind,'retained_legacy_binding':True}
            if fed:source.update({'release_id':head,'source':manifest['sources'],'observation_refs':refs})
            return value_contract(value,source,base,'legacy_match_equal_value_source_replay' if fed else 'frozen_existing_product_input',head if fed else None)
        residential.append({'stats':stats,'compatible_attributes':effective,'compatible_price':effective_price,
            'review_hold':prior['review_hold'],'new_representative_pnu':None,
            'attributes':contract(effective,'attributes',fed,[{'pk':r['pk'],'raw_hash':r['raw_hash']} for r in selected] if fed else [],old['snapshot_ym'] if old else None),
            'price':contract(effective_price,'price',price_equal,[{'pnu':old_price['representative_pnu'],'price_year':price['price_year']}] if price_equal else [],{'price_year':old_price['assessed_land_price_year']} if old_price else None)})
    built=[]
    for row in paired['built']:
        if row['legacy_enrichment']!=row['compatible_enrichment']:raise ValueError('Unexpected built substitution')
        built.append({'transaction':row['transaction'],'compatible_enrichment':copy.deepcopy(row['legacy_enrichment']),
                      'new_building_pk':None,'source_mode':'frozen_existing_product_input'})
    return {'contract':CONTRACT,'published_release':head,'baseline_sha256':baseline_sha,'residential':residential,'built':built,
            'commercial_stats':frozen['collective']['commercial_stats'],'commercial_transactions':frozen['collective']['commercial_transactions'],
            'production_apply':False}, {'title_source_keys':source_attrs,'price_source_keys':source_prices,'residential_keys':len(residential),
            'built_transactions':len(built),'commercial_keys':len(frozen['collective']['commercial_stats'])}


def tables(ops):
    ops.db.executescript('''CREATE TABLE IF NOT EXISTS product_handoff(id TEXT PRIMARY KEY,receipt_path TEXT NOT NULL,receipt_sha TEXT NOT NULL);
       CREATE TABLE IF NOT EXISTS product_control(id INTEGER PRIMARY KEY CHECK(id=1),active_id TEXT REFERENCES product_handoff(id));
       INSERT OR IGNORE INTO product_control VALUES(1,NULL);''')


def evidence(root):
    # Full existing numeric/mart/ASGI/SQL evidence verification remains separate.
    from ledger_product_transition import inspect
    return inspect(root)


def build(ops,root,batch,fail_at=None):
    identifier(batch);tables(ops);before,active=ops.active()
    if active is None:raise ValueError('Published source required')
    stage=ops.verify_stage(before['active_id']);audit=evidence(root)
    frozen,paired,manifest_hash=load_verified_supply(root)
    folder=child(ops.root,'handoffs/'+batch)
    if folder.exists():raise ValueError('Handoff id already exists; verify or use another id')
    folder.mkdir(parents=True)
    db=open_ledger(active['path'])
    try:payload,counts=project(db,frozen,paired,paired['baseline_sha256'])
    finally:db.close()
    if payload['published_release']!=active['release']:raise ValueError('Selected source release differs')
    # Schema/reference metadata stays with prior acceptance. All actual data
    # fixtures must be byte-equivalent under canonical JSON, including types.
    prior_fixture=fixture_rows(frozen,paired,'compatible',[])
    next_fixture=fixture_rows(frozen,payload,'compatible',[])
    if digest(prior_fixture)!=digest(next_fixture):raise ValueError('HTTP/SQL fixture input changed')
    path=folder/'product.json.gz';write_gzip_atomic(path,payload)
    receipt={'handoff':'source-bound-compatibility-v1','source_state':before,'source_database_sha256':active['sha256'],
       'source_stage_sha256':sha(ops.root/'candidates'/before['active_id']/'stage.json'),
       'source_scope_sha256':stage['scope_sha256'],'consumer_contract_sha256':audit['consumer_contract_sha256'],
       'acceptance_sha256':audit['acceptance_sha256'],'supply_manifest_sha256':manifest_hash,
       'artifact_sha256':sha(path),'content_sha256':digest(payload),'counts':counts,'production_apply':False,
       'http_sql_fixture_sha256':digest(next_fixture),'http_sql_fixture_equal_to_accepted_supply':True,
       'adapter_sha256':sha(Path(__file__)),'source_mode':'historical_shadow','scope':'existing_equal_value_bindings_only'}
    receipt_path=folder/'receipt.json';write_json_atomic(receipt_path,receipt)
    if evidence(root)!=audit:raise ValueError('Product evidence changed during handoff')
    ops.db.execute('BEGIN IMMEDIATE')
    try:
        if ops.active()[0]!=before or ops.active()[1]['sha256']!=active['sha256'] or sha(ops.root/'candidates'/before['active_id']/'stage.json')!=receipt['source_stage_sha256']:
            raise ValueError('Source changed during handoff')
        ops.verify_stage(before['active_id'])
        ops.db.execute('INSERT INTO product_handoff VALUES(?,?,?)',(batch,str(receipt_path.relative_to(ops.root)),sha(receipt_path)))
        ops.db.execute('UPDATE product_control SET active_id=? WHERE id=1',(batch,))
        if fail_at=='pointer':raise RuntimeError('Injected product handoff publication failure')
        ops.db.commit()
    except BaseException:ops.db.rollback();raise
    return receipt


def load(ops,root):
    row=ops.db.execute('''SELECT h.receipt_path,h.receipt_sha FROM product_control c JOIN product_handoff h ON h.id=c.active_id WHERE c.id=1''').fetchone()
    if row is None:raise ValueError('No selected product handoff')
    path=child(ops.root,row[0])
    if sha(path)!=row[1]:raise ValueError('Handoff receipt changed')
    receipt=read_json(path);state,active=ops.active();audit=evidence(root)
    if receipt['source_state']!=state or not active or receipt['source_database_sha256']!=active['sha256']:raise ValueError('Product handoff belongs to another source selection')
    ops.verify_stage(state['active_id'])
    if receipt['source_stage_sha256']!=sha(ops.root/'candidates'/state['active_id']/'stage.json'):raise ValueError('Source stage changed')
    for key in ('consumer_contract_sha256','acceptance_sha256','supply_manifest_sha256'):
        audit_key='source_manifest_sha256' if key=='supply_manifest_sha256' else key
        if receipt[key]!=audit[audit_key]:raise ValueError('Mixed product evidence generation')
    if receipt['adapter_sha256']!=sha(Path(__file__)) or receipt['production_apply'] is not False:raise ValueError('Adapter or permission changed')
    artifact=path.parent/'product.json.gz'
    if sha(artifact)!=receipt['artifact_sha256']:raise ValueError('Product artifact changed')
    with gzip.open(artifact,'rt',encoding='utf-8') as f:payload=json.load(f)
    if digest(payload)!=receipt['content_sha256'] or payload['published_release']!=active['release'] or payload['production_apply'] is not False:raise ValueError('Product content changed')
    frozen,paired,_=load_verified_supply(root)
    fixture=fixture_rows(frozen,payload,'compatible',[])
    if receipt['http_sql_fixture_equal_to_accepted_supply'] is not True or digest(fixture)!=receipt['http_sql_fixture_sha256'] or digest(fixture)!=digest(fixture_rows(frozen,paired,'compatible',[])):
        raise ValueError('HTTP/SQL fixture input changed')
    if ops.active()[0]!=state or evidence(root)!=audit:raise ValueError('Source or product evidence changed during read')
    return receipt,payload
