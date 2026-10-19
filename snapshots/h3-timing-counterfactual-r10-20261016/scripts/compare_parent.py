"""CPU-only checks against eight archived R3 x0 endpoints and the final result."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'extensions'))
from H3CounterfactualRouter.dependencies import readout


def validate_inventory(c):
    expected = [(n, b) for n in range(20)
                for b in (('native', 'full') if 6 <= n < 15 else ('native',))]
    branches = c['branches']
    assert [(r['physical_index'], r['branch']) for r in branches] == expected, 'branch inventory/order mismatch'
    assert [r['nfe_index'] for r in branches] == list(range(29)), 'NFE mapping mismatch'
    assert len({r['file'] for r in branches}) == 29, 'duplicate branch archive'
    by_step = {n: [r for r in branches if r['physical_index'] == n] for n in range(20)}
    assert [s['physical_index'] for s in c['steps']] == list(range(20)), 'chosen step inventory mismatch'
    for step in c['steps']:
        rows = by_step[step['physical_index']]
        chosen = rows[-1]
        assert step['selected_branch'] == chosen['branch'], 'selected branch mismatch'
        assert step['chosen_file'] == chosen['file'], 'chosen archive mismatch'
        assert step['chosen_raw_stream_signatures'] == chosen['raw_stream_signatures'], 'chosen tensor binding mismatch'
        assert step['nfe_indices'] == [r['nfe_index'] for r in rows], 'step NFE mapping mismatch'
        assert step['callback_observed_once'] is True
    assert [r['physical_index'] for r in c['inputs']] == [6, 10, 14], 'raw input inventory mismatch'
    assert len({r['file'] for r in c['inputs']}) == 3, 'duplicate raw input archive'


def compare(root):
    root=Path(root)
    run='r10_s05_fixed_full_probe'
    parent=json.loads((root/'audit/parent_x0_manifest.json').read_text())
    current=json.loads((root/'audit/counterfactual'/f'{run}.json').read_text())
    c=current['counterfactual']
    assert current['status']=='complete' and current['completed_forward_calls']==29
    assert current['completed_calls']==1450 and current['routed_calls']==450
    assert [s['physical_index'] for s in c['steps']]==list(range(20))
    assert len(c['branches'])==29 and c['callback_count']==20
    validate_inventory(c)
    assert c['initial_noise']==parent['noise']
    assert c['full_grid']==parent['sigmas_video']
    assert c['seed']==parent['seed']
    left=json.loads((root/'audit/parent_full_conditioning.json').read_text())['pair_snapshot']['actual']
    right=json.loads((root/'audit'/f'{run}_conditioning.json').read_text())['pair_snapshot']['actual']
    assert left==right,'actual conditioning/layout changed'
    captured={}
    for row in c['branches']:
        name=Path(row['file']).name
        path=root/'audit/counterfactual'/f'{run}_snapshots'/name
        assert hashlib.sha256(path.read_bytes()).hexdigest()==row['file_sha256']
        data=torch.load(path,map_location='cpu',weights_only=True)
        for key in ('physical_index', 'branch', 'nfe_index', 'sigma', 'sigma_next',
                    'seed', 'condition_sha256', 'reference_sha256'):
            assert data['metadata'][key] == row[key], f'branch metadata mismatch: {key}'
        normalized=[readout.tensor_signature(data[k]) for k in ('video','audio')]
        assert normalized==row['normalized_stream_signatures']
        # Division by4 must retain reconstructible finite FP32 raw coordinates.
        raw=[readout.tensor_signature(data['video']),readout.tensor_signature(data['audio']*4)]
        assert raw==row['raw_stream_signatures']
        captured[(row['physical_index'],row['branch'])]=normalized
    rows=[]
    for old in parent['captures']:
        n=old['step_zero_based']
        branch='full' if 6<=n<15 else 'native'
        actual=captured[(n,branch)]
        assert actual==[old['video'],old['audio']],f'R3 archived chosen endpoint mismatch step{n}'
        rows.append({'physical_index':n,'video_audio_sha256_equal':True})
    final_path=root/'audit/counterfactual'/f'{run}_snapshots'/'sampler_final_raw.pt'
    final=torch.load(final_path,map_location='cpu',weights_only=True)
    final_sig=[readout.tensor_signature(final['video']),readout.tensor_signature(final['audio']*0.25)]
    assert final_sig==[parent['final_sampler_result'][k] for k in ('video','audio')]
    for row in c['inputs']:
        path=root/'audit/counterfactual'/f'{run}_snapshots'/Path(row['file']).name
        assert hashlib.sha256(path.read_bytes()).hexdigest()==row['file_sha256']
        raw=torch.load(path,map_location='cpu',weights_only=True)
        assert readout.tensor_signature(raw['packed'])==row['packed_signature']
        assert raw['metadata']['full_grid']==c['full_grid']
        for key in ('physical_index', 'sigma', 'sigma_next', 'packed_signature', 'seed',
                    'condition_sha256', 'reference_sha256', 'coordinate_system'):
            assert raw['metadata'][key] == row[key], f'raw input metadata mismatch: {key}'
    report={'schema':'h3-r10-parent-pair-check-v1','passed':True,'diagnostic_only':True,
            'new_method_claim':False,'available_parent_chosen_steps_verified':rows,
            'parent_final_video_audio_exact':True,'actual_conditions_noise_sigmas_seed_equal':True,
            'unarchived_parent_steps':sorted(set(range(20))-{r['physical_index'] for r in rows}),
            'all20_parent_endpoints_claim':False,'rgb141_compare':'requires separate postdecode comparison byroot',
            'saved_all20_chosen':True,'saved_nine_native_full_pairs':True,'saved_raw_input_indices':[r['physical_index'] for r in c['inputs']],
            'CPU_condition_copy_hash_seconds':sum(r['condition_copy_hash_seconds'] for r in c['branches']),
            'CPU_archive_readout_seconds':sum(r['archive_and_readout_seconds'] for r in c['branches']),
            'synchronized_model_seconds':sum(r['model_seconds_synchronized'] for r in c['branches']),
            'NFE':29,'euler_updates':20,'callbacks':20}
    destination=root/'analysis/parent_pair_check.json'
    destination.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT)
    compare(p.parse_args().root)
