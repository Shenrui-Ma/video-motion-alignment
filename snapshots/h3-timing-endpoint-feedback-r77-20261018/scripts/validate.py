"""CPU contract validation only; this command never starts model inference."""
import ast
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    for record in json.loads((ROOT/'configs/PARENT_FILES.json').read_text()):
        assert sha(ROOT/record['file'])==record['sha256'], record['file']
    for record in json.loads((ROOT/'audit/source_code/MANIFEST.json').read_text()):
        assert sha(ROOT/'audit/source_code'/record['file'])==record['sha256'], record['file']
    for path in list((ROOT/'scripts').glob('*.py'))+list((ROOT/'tests').glob('*.py')):
        ast.parse(path.read_text())
    import torch
    from endpoint import Config
    science=json.loads((ROOT/'configs/SCIENCE.json').read_text())
    graph=json.loads((ROOT/'configs/R65_PARENT_GRAPH.json').read_text())
    assert graph['5']['inputs']['prompt']==science['case']['prompt']
    grid=tuple(torch.tensor([float(x) for x in graph['9']['inputs']['sigmas'].split(',')],dtype=torch.float32).tolist())
    assert tuple(science['sigmas_video_float32'])==grid
    comparable=[]
    for arm in 'ABC':
        row=json.loads((ROOT/'configs'/f'ARM_{arm}.json').read_text())
        assert row['science_sha256']==sha(ROOT/'configs/SCIENCE.json')
        assert row['parent_graph_sha256']==sha(ROOT/'configs/R65_PARENT_GRAPH.json')
        assert row['arm']==arm and tuple(row['sigmas'])==grid
        Config(row['run_id'],arm,str(ROOT/'audit/VALIDATION_UNUSED'),grid)
        comparable.append({k:v for k,v in row.items() if k not in ('run_id','arm','lambda_rule')})
    assert comparable[0]==comparable[1]==comparable[2]
    assert science['original_output_or_final_phi_used_for_proposal'] is False
    assert not torch.cuda.is_initialized()
    print(json.dumps({'passed':True,'CPU_only':True,'CUDA_initialized':False,'arms_share_input_contract':True,
                      'GPU_launch_ready':False,'pending':science['required_fresh_gates']},indent=2))


if __name__=='__main__':main()
