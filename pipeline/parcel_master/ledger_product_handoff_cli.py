"""Build, verify or inspect a local source-bound compatibility handoff."""
import argparse
import json
from pathlib import Path

from ledger_consumer_input_preview import ROOT
from ledger_operations import Operations
from ledger_product_handoff import build,load
from ledger_product_transition import inspect


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    actions=parser.add_subparsers(dest='action',required=True)
    create=actions.add_parser('build');create.add_argument('--batch-id',required=True)
    actions.add_parser('verify');actions.add_parser('gate');args=parser.parse_args()
    ops=Operations(args.root)
    try:
        if args.action=='build':result=build(ops,ROOT,args.batch_id)
        elif args.action=='gate':result=inspect(ROOT,operations=ops)
        else:
            receipt,_=load(ops,ROOT);result={'receipt':receipt,'verified':True,'production_apply':False}
        print(json.dumps(result,ensure_ascii=True))
    finally:ops.close()


if __name__=='__main__':main()
