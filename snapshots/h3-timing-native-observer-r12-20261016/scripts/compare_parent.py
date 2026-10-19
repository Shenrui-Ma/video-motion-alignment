"""Variable branch inventory, current chosen archives, historical native-prefix pairing."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'extensions'))
from H3NativeObserverRouter.dependencies import readout


def validate_inventory(c):
    """Independently reconstruct the gate from native rows and prior actual choice."""
    assert c['policy'] in ('native_observer', 'off', 'fixed'), 'invalid policy'
    fixed = c['fixed_indices']
    assert fixed == sorted(set(fixed)) and all(type(i) is int and 6 <= i <= 19 for i in fixed)
    assert c['policy'] == 'fixed' or not fixed
    branches, steps = c['branches'], c['steps']
    assert [row['physical_index'] for row in steps] == list(range(20)), 'chosen step inventory mismatch'
    cursor, previous, active = 0, False, []
    for n, step in enumerate(steps):
        assert cursor < len(branches), 'missing native branch'
        native = branches[cursor]
        assert (native['physical_index'], native['branch']) == (n, 'native'), 'native branch order mismatch'
        rows = [native]
        proposed, reason = None, 'PREFIX_PASSIVE'
        if n >= 6:
            obs = native['observation']
            assert obs is not None and type(obs['accepted']) is bool, 'native observation missing'
            if not obs['accepted']:
                proposed, reason = False, 'OFF_UNKNOWN'
            else:
                lag = obs['best']['lag_frames']
                assert type(lag) is int and -24 <= lag <= 24
                if lag >= 4:proposed, reason = True, 'ON_DELAYED'
                elif -2 <= lag <= 2:proposed, reason = False, 'OFF_ALIGNED'
                elif lag == 3:proposed, reason = previous, 'HOLD_LAG3'
                else:proposed, reason = False, 'OFF_ADVANCED'
        chosen = False if n < 6 or c['policy'] == 'off' else n in fixed if c['policy'] == 'fixed' else proposed
        applied = 'PREFIX_NATIVE' if n < 6 else 'FIXED_MASK' if c['policy'] == 'fixed' else 'POLICY_OFF' if c['policy'] == 'off' else reason
        decision = step['decision']
        for key, value in {'policy':c['policy'], 'physical_index':n, 'previous_actual_full':previous,
                           'chosen_full':chosen, 'observer_proposed_full':proposed, 'observer_reason':reason,
                           'applied_reason':applied, 'observation_branch':'native' if n >= 6 else None,
                           'native_nfe_index':cursor}.items():
            assert decision[key] == value, 'decision mismatch: '+key
        if chosen:
            assert cursor+1 < len(branches), 'missing selected Full branch'
            full = branches[cursor+1]
            assert (full['physical_index'],full['branch']) == (n,'full'), 'Full branch order mismatch'
            assert full['same_input'] == native['same_input'], 'branches do not share input'
            rows.append(full);active.append(n)
        selected = rows[-1]
        assert step['selected_branch'] == selected['branch'], 'selected branch mismatch'
        assert step['chosen_file'] == selected['file'], 'chosen archive mismatch'
        assert step['chosen_raw_stream_signatures'] == selected['raw_stream_signatures'], 'chosen tensor binding mismatch'
        assert step['nfe_indices'] == list(range(cursor,cursor+len(rows))), 'step NFE mapping mismatch'
        assert step['callback_observed_once'] is True
        cursor += len(rows)
        if n >= 6:previous = chosen
    assert cursor == len(branches) == 20 + len(active), 'extra/missing branch inventory'
    assert c['full_physical_indices'] == active, 'active index audit mismatch'
    assert c['actual_full_count'] == len(active), 'Full count mismatch'
    assert c['actual_model_nfe'] == cursor and c['actual_euler_updates'] == 20
    assert [r['nfe_index'] for r in branches] == list(range(cursor)), 'NFE mapping mismatch'
    assert len({r['file'] for r in branches}) == cursor, 'duplicate branch archive'
    assert [r['physical_index'] for r in c['inputs']] == [6,10,14], 'raw input inventory mismatch'
    assert len({r['file'] for r in c['inputs']}) == 3, 'duplicate raw input archive'
    return active


def compare(root):
    root=Path(root)
    run='r12_s05_native_observer'
    parent=json.loads((root/'audit/parent_x0_manifest.json').read_text())
    current=json.loads((root/'audit/counterfactual'/f'{run}.json').read_text())
    c=current['counterfactual']
    assert current['status']=='complete'
    active=validate_inventory(c)
    expected_nfe=20+len(active)
    assert current['completed_forward_calls']==expected_nfe
    assert current['completed_calls']==50*expected_nfe and current['routed_calls']==50*len(active)
    assert current['calls_by_forward']==[50]*expected_nfe
    assert current['routed_by_forward']==[50 if r['branch']=='full' else 0 for r in c['branches']]
    assert [s['physical_index'] for s in c['steps']]==list(range(20))
    assert len(c['branches'])==expected_nfe and c['callback_count']==20
    assert c['initial_noise']==parent['noise']
    assert c['full_grid']==parent['sigmas_video']
    assert c['seed']==parent['seed']
    left=json.loads((root/'audit/parent_full_conditioning.json').read_text())['pair_snapshot']['actual']
    right=json.loads((root/'audit'/f'{run}_conditioning.json').read_text())['pair_snapshot']['actual']
    assert left==right,'actual conditioning/layout changed'
    captured={}
    for row in c['branches']:
        assert row['condition_sha256']==c['conditioning']['sha256']
        assert row['reference_sha256']==c['reference']['sha256']
        assert row['seed']==c['seed']
        assert row['sigma']==c['full_grid'][row['physical_index']]
        assert row['sigma_next']==c['full_grid'][row['physical_index']+1]
        assert all(row[k] is True for k in ('global_rng_unchanged','condition_unchanged','full_grid_unchanged'))
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
        if n >= 6:continue  # Historical pairing is only the common native prefix.
        actual=captured[(n,'native')]
        assert actual==[old['video'],old['audio']],f'R3 archived chosen endpoint mismatch step{n}'
        rows.append({'physical_index':n,'video_audio_sha256_equal':True})
    assert [row['physical_index'] for row in rows]==[5], 'expected historical native prefix capture5'
    final_path=root/'audit/counterfactual'/f'{run}_snapshots'/'sampler_final_raw.pt'
    final=torch.load(final_path,map_location='cpu',weights_only=True)
    final_sig=[readout.tensor_signature(final['video']),readout.tensor_signature(final['audio']*0.25)]
    independent=json.loads((root/'audit/x0'/run/'manifest.json').read_text())
    assert independent['status']=='complete' and independent['callback_count']==20
    assert independent['capture_steps_zero_based']==[5,6,7,8,9,10,15,19]
    for row in independent['captures']:
        n=row['step_zero_based'];branch='full' if n in active else 'native'
        assert captured[(n,branch)]==[row['video'],row['audio']], 'independent chosen readout mismatch'
    assert final_sig==[independent['final_sampler_result'][k] for k in ('video','audio')]
    snapshot_dir=root/'audit/counterfactual'/f'{run}_snapshots'
    expected_files={Path(row['file']).name for row in c['branches']+c['inputs']}|{'sampler_final_raw.pt'}
    assert {p.name for p in snapshot_dir.glob('*.pt')}==expected_files, 'unexpected archive files'
    for row in c['inputs']:
        path=root/'audit/counterfactual'/f'{run}_snapshots'/Path(row['file']).name
        assert hashlib.sha256(path.read_bytes()).hexdigest()==row['file_sha256']
        raw=torch.load(path,map_location='cpu',weights_only=True)
        assert readout.tensor_signature(raw['packed'])==row['packed_signature']
        assert raw['metadata']['full_grid']==c['full_grid']
        for key in ('physical_index', 'sigma', 'sigma_next', 'packed_signature', 'seed',
                    'condition_sha256', 'reference_sha256', 'coordinate_system'):
            assert raw['metadata'][key] == row[key], f'raw input metadata mismatch: {key}'
    report={'schema':'h3-r12-variable-inventory-prefix-check-v1','passed':True,
            'new_method_claim':False,'actual_full_indices':active,
            'available_parent_native_prefix_steps_verified':rows,
            'whole_trajectory_parent_match_expected':False,'parent_final_match_claim':False,
            'actual_conditions_noise_sigmas_seed_equal':True,
            'all20_chosen_saved':True,'all_computed_branches_saved':True,
            'independent_chosen_x0_and_final_match':True,
            'saved_raw_input_indices':[r['physical_index'] for r in c['inputs']],
            'CPU_condition_copy_hash_seconds':sum(r['condition_copy_hash_seconds'] for r in c['branches']),
            'CPU_archive_readout_seconds':sum(r['archive_and_readout_seconds'] for r in c['branches']),
            'synchronized_model_seconds':sum(r['model_seconds_synchronized'] for r in c['branches']),
            'NFE':expected_nfe,'Full_evaluations':len(active),'euler_updates':20,'callbacks':20,
            'efficiency_scope':'cost records only; no speed diagnosis'}
    destination=root/'analysis/parent_pair_check.json'
    destination.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT)
    compare(p.parse_args().root)
