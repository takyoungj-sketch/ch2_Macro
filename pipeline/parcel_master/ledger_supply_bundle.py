"""Verify a completed research supply bundle before any consumer opens its inputs."""
import gzip
import hashlib
import json
from pathlib import Path

from integrated_ledger_v2 import digest


def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def verify_manifest(root):
    root=Path(root)
    path=root/'docs/lab/cheongju_product_supply_pipeline.json'
    report=json.loads(path.read_text(encoding='utf-8'))
    expected={'cheongju_product_numeric_baseline.json','cheongju_product_field_extension.json',
              'cheongju_numeric_supply_shadow.json','cheongju_supply_regression_replay.json'}
    scripts={'freeze_cheongju_product_numeric.py','extend_cheongju_product_fields.py',
             'cheongju_numeric_supply_shadow.py','replay_cheongju_supply_regressions.py',
             'run_cheongju_product_supply.py','ledger_supply_artifacts.py'}
    if report.get('production_apply') is not False or set(report['report_sha256'])!=expected or set(report['script_sha256'])!=scripts:
        raise ValueError('Unexpected supply manifest scope')
    if set(report['checks'])!=expected or any(v is not True for v in report['checks'].values()):
        raise ValueError('Supply did not complete successfully')
    for folder,mapping in [('docs/lab',report['report_sha256']),('pipeline/parcel_master',report['script_sha256'])]:
        for name,expected_hash in mapping.items():
            if sha(root/folder/name)!=expected_hash:raise ValueError('Supply bundle changed: '+name)
    return report,sha(path)


def load_verified_supply(root):
    root=Path(root);manifest,manifest_hash=verify_manifest(root)
    lab=root/'docs/lab';out=root/'data/research/cheongju_ledger'
    baseline=json.loads((lab/'cheongju_product_numeric_baseline.json').read_text(encoding='utf-8'))
    shadow=json.loads((lab/'cheongju_numeric_supply_shadow.json').read_text(encoding='utf-8'))
    payloads=[]
    for name,meta,content_key in [('product_numeric_baseline_20261005.json.gz',baseline,'content_sha256'),
                                   ('product_numeric_supply_shadow.json.gz',shadow,'paired_content_sha256')]:
        path=out/name
        if sha(path)!=meta['gzip_sha256']:raise ValueError('Supply gzip changed: '+name)
        with gzip.open(path,'rt',encoding='utf-8') as source:payload=json.load(source)
        if digest(payload)!=meta[content_key]:raise ValueError('Supply content changed: '+name)
        payloads.append(payload)
    frozen,paired=payloads
    if manifest['baseline_sha256']!=baseline['content_sha256'] or paired['baseline_sha256']!=baseline['content_sha256']:
        raise ValueError('Mixed baseline generations')
    if paired['published_release']!=manifest['extension']['selected_release']:
        raise ValueError('Mixed source publications')
    return frozen,paired,manifest_hash


class FrozenListLookup:
    """Offline adapter for precisely four SELECT shapes used by list attachment.

    This supplies frozen lookup rows, not a PostgreSQL or HTTP integration test.
    Unknown queries fail rather than returning an invented empty result.
    """
    def __init__(self,attributes,prices):
        self.attributes=attributes;self.prices=prices;self.rows=[];self.scalar_value=None

    def execute(self,statement,params=None):
        sql=' '.join(str(statement).split());params=params or {}
        self.rows=[];self.scalar_value=None
        if sql=='SELECT to_regclass(:t)':
            if params['t'] not in ('public.collective_building_attributes','public.collective_building_assessed_land_price'):
                raise ValueError('Unsupported frozen table lookup')
            self.scalar_value=params['t']
        elif sql=='SELECT MAX(snapshot_ym) FROM collective_building_attributes':
            self.scalar_value=max((r['snapshot_ym'] for r in self.attributes),default=None)
        elif sql==('SELECT building_key, asset_type, households, builder_norm, builder_raw, builder_is_joint, '
                   'attr_quality_flags, match_tier, match_rule FROM collective_building_attributes '
                   'WHERE snapshot_ym = :snap AND building_key = ANY(:keys)'):
            self.rows=[r for r in self.attributes if r['snapshot_ym']==params['snap'] and r['building_key'] in params['keys']]
        elif sql==('SELECT DISTINCT ON (building_key, asset_type) building_key, asset_type, assessed_land_price, '
                   'assessed_land_price_year FROM collective_building_assessed_land_price WHERE building_key = ANY(:keys) '
                   'ORDER BY building_key, asset_type, assessed_land_price_year DESC NULLS LAST'):
            grouped={}
            for row in self.prices:
                if row['building_key'] not in params['keys']:continue
                key=(row['building_key'],row['asset_type'])
                prior=grouped.get(key)
                if prior is None or (row['assessed_land_price_year'] or -1)>(prior['assessed_land_price_year'] or -1):grouped[key]=row
            self.rows=[grouped[k] for k in sorted(grouped)]
        else:raise ValueError('Unsupported frozen SELECT: '+sql)
        return self

    def scalar(self):return self.scalar_value
    def mappings(self):return self
    def all(self):return self.rows
