"""Reuse actual-observation extraction; add the verified recovery boundary."""
import argparse, importlib.util
from common import *

def build(path):
    pin=read(ROOT/'configs/SHARED_HELPERS.json')['prepare_progress.py'];require(sha(pin['file'])==pin['sha256'],'progress helper changed')
    spec=importlib.util.spec_from_file_location('r133_progress',pin['file']);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    audit=read(path);cost=verify_counts(audit);result=module.build(Path(path),False)
    result.update(schema='r138-recovered-actual-control-progress-v1',actual_cost=cost,
        recovery_break_after_step_1based=9,failed_attempts=config()['failed_attempts'],
        generation_note='R133 completed logical indices 0..8; R138 continues 9..19 from exact state9. R133 failed ordinary index9 counts as one additional actual prediction; R138 attempt1 adds zero predictions.')
    for row in result['rows']:row['execution_generation']='R133' if row['physical_index_0based']<9 else 'R138'
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    require(not a.output.exists(),'refuse to overwrite progress artifact');save(a.output,build(a.input));print(json.dumps(bound(a.output)))
