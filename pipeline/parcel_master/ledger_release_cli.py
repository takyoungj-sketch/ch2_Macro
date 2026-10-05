"""Inspect, restore or export an existing integrated research ledger release."""
import argparse
import gzip
import json
import sqlite3
from pathlib import Path

from integrated_ledger_v2 import CONTRACT, consumer, restore

RESEARCH = Path(__file__).resolve().parents[2] / 'data/research/cheongju_ledger'


def open_ledger(path, writable=False):
    path=path.resolve()
    if not path.is_relative_to(RESEARCH.resolve()) or not path.is_file():
        raise ValueError('Existing local research database required')
    db=sqlite3.connect(path.as_uri()+('?mode=rw' if writable else '?mode=ro'),uri=True)
    db.execute('PRAGMA foreign_keys=ON')
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'release','release_source','building_raw','price_observation'}<=tables:
        db.close();raise ValueError('Not an integrated ledger; frozen input databases are protected')
    return db


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,required=True)
    parser.add_argument('--restore',dest='release_id')
    parser.add_argument('--export',type=Path)
    args=parser.parse_args()
    if args.export and (not args.export.resolve().is_relative_to(RESEARCH.resolve()) or args.export.resolve()==args.db.resolve()):
        raise ValueError('Export must be a separate local research file')
    db=open_ledger(args.db,writable=bool(args.release_id))
    if args.release_id:restore(db,args.release_id)
    head=db.execute("SELECT value FROM state WHERE key='published_release'").fetchone()[0]
    if args.export:
        with gzip.open(args.export,'wt',encoding='utf-8') as f:
            f.write('[');first=True
            for pk, in db.execute('SELECT pk FROM current_building ORDER BY pk'):
                if not first:f.write(',')
                json.dump(consumer(db,pk),f,ensure_ascii=False);first=False
            f.write(']')
    print(json.dumps({'contract':CONTRACT,'published_release':head,
                      'releases':db.execute('SELECT id,ordinal FROM release ORDER BY ordinal').fetchall(),
                      'current_buildings':db.execute('SELECT count(*) FROM current_building').fetchone()[0],
                      'production_apply':False},ensure_ascii=True))
    db.close()


if __name__=='__main__':main()
