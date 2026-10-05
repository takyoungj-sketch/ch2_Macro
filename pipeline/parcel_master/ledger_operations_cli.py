"""Intake, stage, publish or restore one separate local source operations lane."""
import argparse
import json
from pathlib import Path

from ledger_operations import Operations
from ledger_release_cli import RESEARCH


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=RESEARCH/'operations_local')
    sub=parser.add_subparsers(dest='action',required=True)
    export=sub.add_parser('export-historical')
    export.add_argument('--source',type=Path,required=True);export.add_argument('--release',required=True);export.add_argument('--batch-id',required=True)
    stage=sub.add_parser('stage');stage.add_argument('--package',type=Path,required=True)
    publish=sub.add_parser('publish');publish.add_argument('--batch-id',required=True);publish.add_argument('--impact-sha256',required=True);publish.add_argument('--expected-revision',type=int,required=True)
    restore=sub.add_parser('restore');restore.add_argument('--batch-id',required=True);restore.add_argument('--expected-revision',type=int,required=True)
    sub.add_parser('status');args=parser.parse_args();ops=Operations(args.root)
    try:
        if args.action=='export-historical':result={'package_path':str(ops.export_package(args.source,args.release,args.batch_id))}
        elif args.action=='stage':result=ops.stage(args.package)
        elif args.action=='publish':result={'newly_published':ops.publish(args.batch_id,args.impact_sha256,args.expected_revision),'state':ops.state()}
        elif args.action=='restore':result={'pointer_changed':ops.restore(args.batch_id,args.expected_revision),'state':ops.state()}
        else:
            state,active=ops.active();result={'state':state,'active_database':str(active['path']) if active else None,
                                           'active_release':active['release'] if active else None,'snapshot':active['snapshot'] if active else None}
        print(json.dumps(result,ensure_ascii=True))
    finally:ops.close()


if __name__=='__main__':main()
