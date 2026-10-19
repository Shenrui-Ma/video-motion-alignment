"""Verify the completed six-prediction report; never launches inference."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'extensions'))
from H3OneStepForkAudit.core import Source, POINTS, readout


def verify(root):
    root=Path(root)
    source=Source(root/'configs/source_manifest.json')
    audit=json.loads((root/'audit/fork/r13_s05_one_step_fork.json').read_text())
    f=audit['fork']
    assert audit['status']=='complete' and audit['completed_forward_calls']==6
    assert audit['completed_calls']==300 and audit['routed_calls']==0
    assert f['actual_nfe']==6 and f['sampler_callbacks']==0 and f['euler_updates']==0
    assert f['condition_materializations']==1 and f['all_replay_gates_passed'] is True
    expected=[(n,n+1,b) for n in POINTS for b in ['replay_full','fork_native']]
    assert [(r['source_euler_index'],r['eval_euler_index'],r['branch']) for r in f['predictions']]==expected
    assert [r['probe_nfe'] for r in f['predictions']]==list(range(6))
    assert [r['index'] for r in f['pdd']]==[7,7,11,11,15,15]
    assert [r['probe_nfe'] for r in f['pdd']]==list(range(6))
    assert f['condition']==source.condition and f['full_grid']==source.c['full_grid']
    assert f['source_manifest_sha256']==hashlib.sha256((root/'configs/source_manifest.json').read_bytes()).hexdigest()
    snapshot_root=root/'audit/fork/r13_s05_one_step_fork_snapshots'
    def check(row):
        p=snapshot_root/Path(row['file']).name
        assert hashlib.sha256(p.read_bytes()).hexdigest()==row['file_sha256']
        data=torch.load(p,map_location='cpu',weights_only=True)
        assert readout.tensor_signature(data['packed'])==row['packed_signature']
        assert [readout.tensor_signature(data[k]) for k in ['video','audio']]==row['normalized_stream_signatures']
        assert [readout.tensor_signature(data['video']),readout.tensor_signature(data['audio']*4)]==row['raw_stream_signatures']
        for k,v in data['metadata'].items():assert row[k]==v
        return data
    for pair in f['pairs']:
        n=pair['source_euler_index'];assert pair['eval_euler_index']==n+1
        assert pair['full_next_input_exact'] is True and pair['full_next_endpoint_exact'] is True
        for side in ['u_full','u_native']:check(pair[side])
        assert pair['u_full']['packed_signature']==source.branches[n+1,'native']['same_input']
    observations=[]
    for i,row in enumerate(f['predictions']):
        check(row)
        pair=f['pairs'][i//2]
        expected_input=pair['u_full' if row['branch']=='replay_full' else 'u_native']['packed_signature']
        assert row['input_signature']==expected_input
        if row['branch']=='replay_full':
            known=source.branches[row['eval_euler_index'],'native']
            assert row['raw_stream_signatures']==known['raw_stream_signatures']
            assert row['normalized_stream_signatures']==known['normalized_stream_signatures']
        observations.append({k:row[k] for k in ['source_euler_index','eval_euler_index','branch','observation']})
    result={'schema':'h3-r13-verified-report-v1','passed':True,'diagnostic_only':True,'new_method_claim':False,
        'NFE':6,'Euler_updates':0,'sampler_callbacks':0,'all_three_replay_pairs_bitwise':True,
        'observations':observations,'model_seconds':sum(r['model_seconds_synchronized'] for r in f['predictions']),
        'condition_hash_seconds':sum(r['condition_hash_seconds'] for r in f['predictions']),
        'archive_readout_seconds':sum(r['archive_readout_seconds'] for r in f['predictions']),
        'scope':'three preselected one-step counterfactuals on historical Full path; no complete new video'}
    (root/'analysis/verified_fork.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT)
    print(json.dumps(verify(p.parse_args().root),indent=2))
