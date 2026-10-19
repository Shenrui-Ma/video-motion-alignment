"""Read-only filesystem capacity check before the root starts inference."""
import argparse
import json
import shutil
import time
from pathlib import Path
from r117_contract import ROOT, read, require


def check(root=ROOT, usage=shutil.disk_usage):
    root=Path(root);policy=read(root/'configs/storage_policy.json');space=usage(root)
    result={'observed_unix':time.time(),'root':str(root),'free_bytes':space.free,'total_bytes':space.total,
            'required_free_bytes':policy['startup_required_free_bytes'],'estimated_output_bytes':policy['estimated_output_bytes'],
            'estimate_status':'approximate frame-scaled prior observation; not measured R117 output',
            'passed':space.free>=policy['startup_required_free_bytes']}
    require(result['passed'],'insufficient filesystem headroom for registered batch')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=ROOT);args=parser.parse_args()
    print(json.dumps(check(args.root),indent=2))
