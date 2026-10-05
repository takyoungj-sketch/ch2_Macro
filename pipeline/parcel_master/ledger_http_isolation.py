"""Connection-local PostgreSQL fixtures; product tables are never written."""
import copy
import json
import re
from collections import Counter,defaultdict
from contextlib import contextmanager

from sqlalchemy import text,event
from sqlalchemy.orm import Session

COLLECTIVE_TABLES=('collective_building_stats','collective_building_annual_stats','collective_transactions',
    'collective_building_attributes','collective_building_assessed_land_price',
    'collective_commercial_cluster_stats','collective_commercial_transactions','commercial_clusters')
BUILT_TABLES=('built_transactions','built_transaction_enrichment')


def table_name(name):
    if name not in COLLECTIVE_TABLES+BUILT_TABLES:raise ValueError('Unapproved fixture table')
    return name


def annual_counts(transactions):
    counts=Counter((r['building_key'],r['asset_type'],r['contract_year']) for r in transactions)
    return [{'building_key':bk,'asset_type':asset,'contract_year':year,'count':count}
            for (bk,asset,year),count in sorted(counts.items())]


def fixture_rows(frozen,paired,branch,clusters):
    if branch not in ('legacy','compatible'):raise ValueError('Unknown input branch')
    c=frozen['collective']
    attributes=copy.deepcopy(c['attributes']);prices=copy.deepcopy(c['prices'])
    if branch=='compatible':
        replacements={(r['stats']['building_key'],r['stats']['asset_type'],r['compatible_attributes']['snapshot_ym']):r['compatible_attributes']
                      for r in paired['residential'] if r['compatible_attributes']}
        attributes=[replacements.get((r['building_key'],r['asset_type'],r['snapshot_ym']),r) for r in attributes]
        by_pair={(r['stats']['building_key'],r['stats']['asset_type']):r for r in paired['residential']}
        for row in prices:row['assessed_land_price']=by_pair[(row['building_key'],row['asset_type'])]['compatible_price']
    collective=dict(zip(COLLECTIVE_TABLES,(c['residential_stats'],annual_counts(c['residential_transactions']),
                     c['residential_transactions'],attributes,prices,c['commercial_stats'],c['commercial_transactions'],clusters)))
    if branch=='legacy':transactions=frozen['built']['transactions'];enrichment_key='enrichment'
    else:transactions=paired['built'];enrichment_key='compatible_enrichment'
    built={'built_transactions':[r['transaction'] for r in transactions],
           'built_transaction_enrichment':[r[enrichment_key] for r in transactions if r[enrichment_key]]}
    return collective,built


class TemporaryProductDB:
    def __init__(self,engine,fixtures):
        if engine.url.host not in ('localhost','127.0.0.1','::1'):raise ValueError('Local PostgreSQL required')
        self.engine=engine;self.fixtures=fixtures;self.conn=None;self.sql_counts=Counter();self.resolution={}

    def __enter__(self):
        try:
            self.conn=self.engine.connect().execution_options(isolation_level='REPEATABLE READ')
            self.conn.execute(text('SET LOCAL statement_timeout=\'90s\''))
            for name,rows in self.fixtures.items():
                table_name(name)
                # CTAS copies column types, not public defaults/sequences or constraints.
                self.conn.execute(text(f'CREATE TEMP TABLE {name} AS SELECT * FROM public.{name} WITH NO DATA'))
                for index in range(0,len(rows),500):
                    self.conn.execute(text(f'INSERT INTO pg_temp.{name} SELECT * FROM jsonb_populate_recordset(NULL::pg_temp.{name},CAST(:rows AS jsonb))'),
                                      {'rows':json.dumps(rows[index:index+500],ensure_ascii=False,allow_nan=False)})
                count=self.conn.execute(text(f'SELECT COUNT(*) FROM pg_temp.{name}')).scalar_one()
                if count!=len(rows):raise ValueError('Incomplete fixture '+name)
                self.conn.execute(text(f'ANALYZE pg_temp.{name}'))
            self.conn.commit()
            self.conn.execute(text('SET TRANSACTION READ ONLY'))
            self.conn.execute(text("SET LOCAL search_path=pg_temp,public"))
            self.conn.execute(text("SET LOCAL statement_timeout='90s'"))
            for name in self.fixtures:
                row=self.conn.execute(text('SELECT to_regclass(:name)::oid,to_regclass(:temp)::oid'),{'name':name,'temp':'pg_temp.'+name}).one()
                if row[0] is None or row[0]!=row[1]:raise ValueError('Public table would be used: '+name)
                self.resolution[name]=True
            event.listen(self.conn,'before_cursor_execute',self.trace)
            return self
        except BaseException:
            self.__exit__(None,None,None);raise

    def trace(self,conn,cursor,statement,parameters,context,executemany):
        import hashlib
        self.sql_counts[hashlib.sha256(statement.encode()).hexdigest()]+=1

    def dependency(self):
        if self.conn.execute(text('SHOW transaction_read_only')).scalar_one()!='on':raise ValueError('HTTP requests require read-only transaction')
        session=Session(bind=self.conn,join_transaction_mode='create_savepoint')
        try:yield session
        finally:session.close()

    def __exit__(self,*args):
        if self.conn is not None:
            self.conn.rollback();self.conn.close();self.conn=None
        # Physical connections must close: returning a connection with TEMP tables to a pool is unsafe.
        self.engine.dispose()


def pagination_check(items,total,key):
    identities=[(r[key],r.get('asset_type')) for r in items]
    if len(items)!=total or len(set(identities))!=total:raise ValueError('Pagination lost or duplicated rows')
    return True
