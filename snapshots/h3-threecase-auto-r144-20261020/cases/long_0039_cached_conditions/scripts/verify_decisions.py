"""Reproduce R59 arm decisions and branch counts from one finished audit.

This component checks decision/transaction records. The producer completion
gate must additionally verify actual PT bytes, ownership, Comfy history,
observer request/response artifacts and final outputs. It does not certify
those omitted checks or authorize scoring on its own.
"""
import argparse
import json
import sys
from pathlib import Path
from execution_contract import ROOT, require, read, verify_candidate

sys.path.insert(0, str(ROOT / 'extensions'))
from H3AutomaticWindowRouter.selector import Controller
from H3AutomaticWindowRouter.geometry import Geometry


def check(audit, case):
    arm = case['arm']
    require(arm in ('visible_only', 'visible_fallback', 'weak_only'), 'Native reused from R57; only15 new jobs supported')
    controller = Controller(Geometry.from_case(case), arm=arm)
    counter = audit['counterfactual']
    mask = counter['full_physical_indices']
    require(audit['status'] == 'complete' and counter['policy'] == arm, 'unfinished/wrong arm audit')
    require(counter['weak_schedule'] == {'indices': list(range(6, 15)), 'alpha': .25, 'all_bins': 27}, 'weak schedule differs')
    require(counter['observer_descriptor_version'] == 'r56-arm-bone-unit-v1', 'observer descriptor changed')
    require(mask == sorted(set(mask)) and all(type(index) is int and 1 <= index <= 19 for index in mask), 'invalid active steps')
    nfe = 20 + len(mask)
    require(counter['actual_model_nfe'] == nfe and counter['actual_euler_updates'] == counter['callback_count'] == 20, 'NFE/Euler count differs')
    require(audit['completed_forward_calls'] == nfe and audit['completed_calls'] == 50 * nfe and audit['routed_calls'] == 50 * len(mask), 'actual block counters differ')
    require(audit['calls_by_forward'] == [50] * nfe, 'incomplete blocks in a forward')
    require(len(counter['steps']) == 20 and len(counter['branches']) == nfe, 'incomplete step/branch history')
    measurements = counter['measurements']
    require(len(measurements) == (20 if controller.needs_observation else 0), 'arm observation count differs')
    observed = {row['physical_index']: row for row in measurements}
    require(sorted(observed) == (list(range(20)) if controller.needs_observation else []), 'duplicate/missing observer index')
    branches = {(row['physical_index'], row['branch']): row for row in counter['branches']}
    expected_keys = [(index, name) for index in range(20) for name in (('native', 'full') if index in mask else ('native',))]
    require(list(branches) == expected_keys and len(branches) == nfe, 'actual forward execution order differs')
    require([row['nfe_index'] for row in counter['branches']] == list(range(nfe)), 'NFE indices differ')
    require(len(audit['forward_summaries']) == nfe, 'missing attention forward summaries')
    for index, step in enumerate(counter['steps']):
        require(step['physical_index'] == index and step['callback_observed_once'] is True, 'callback transaction order differs')
        expected = controller.select(index, observed.get(index))
        require(all(step['decision'].get(key) == value for key, value in expected.items()), 'candidate policy does not reproduce decision')
        require(expected['chosen_full'] == (index in mask), 'selected mask differs')
        native = branches[index, 'native']
        chosen_name = 'full' if expected['chosen_full'] else 'native'
        chosen = branches[index, chosen_name]
        require(step['selected_branch'] == chosen_name and step['chosen_file'] == chosen['file'] and step['chosen_raw_stream_signatures'] == chosen['raw_stream_signatures'], 'Euler selected endpoint record differs')
        require(step['decision']['native_nfe_index'] == native['nfe_index'], 'decision refers to another Native forward')
        require(step['nfe_indices'] == [branches[key]['nfe_index'] for key in expected_keys if key[0] == index], 'callback branches differ')
        for name in ('native', 'full') if expected['chosen_full'] else ('native',):
            row = branches[index, name]
            require(row['seed'] == case['seed'] and row['physical_index'] == index and row['branch'] == name, 'branch identity differs')
            require(all(row[key] is True for key in ('global_rng_unchanged', 'condition_unchanged', 'full_grid_unchanged')), 'branch state changed')
            require(row['same_input'] == native['same_input'] and row['condition_sha256'] == native['condition_sha256'] and row['reference_sha256'] == native['reference_sha256'] and row['sigma'] == native['sigma'] and row['sigma_next'] == native['sigma_next'], 'Native/Full used different states')
            summary = audit['forward_summaries'][row['nfe_index']]
            require(summary['physical_index'] == index and summary['branch'] == name and summary['nfe_index'] == row['nfe_index'], 'attention summary points to another branch')
            require(summary['route_alpha'] == (expected['route_alpha'] if name == 'full' else 0.0), 'actual attention strength differs')
            require(summary['latent_bins'] == (expected['latent_bins'] if name == 'full' else []), 'actual attention time support differs')
            if name == 'full':
                require(summary['control_state'] == expected['control_state'], 'actual intervention type differs')
    if arm == 'weak_only':
        require(mask == list(range(6, 15)) and nfe == 29, 'fixed weak schedule was not executed')
    gates = counter['pair_gates']
    initial = [row for row in gates if row['gate'] == 'initial_binding']
    require(len(initial) == 1 and initial[0]['pass'] is True and initial[0]['seed'] == case['seed'] and initial[0]['actual_noise_and_producer_clean_inputs_exact'] is True, 'initial actual pairing absent')
    require(initial[0]['archived_embedding_tensor']['actual_tensor_equal'] is True, 'actual P1 embedding pairing absent')
    prefix = [row for row in gates if row['gate'] == 'native_prefix']
    require([(row['physical_index'], row['branch']) for row in prefix] == expected_keys, 'historical prefix records incomplete')
    first = mask[0] if mask else None
    for row in prefix:
        eligible = row['branch'] == 'native' and (first is None or row['physical_index'] <= first)
        require(row['status'] == ('pass' if eligible else 'not_applicable'), 'historical trajectory comparison outside common prefix')
        if eligible:
            require(row['tensor_equal'] is True, 'actual eligible historical Native tensor mismatch')
    return {'status': 'DECISIONS_AND_TRANSACTION_RECORDS_PASS', 'run_id': case['run_id'], 'arm': arm,
            'updates': 20, 'NFE': nfe, 'observations': len(measurements), 'active_indices': mask,
            'first_intervention': first, 'runtime_payloads_verified': False, 'GPU_launch_authorized': False,
            'remaining_verification': ['actual observer and endpoint files', 'PT signatures and final all-OFF equality', 'Comfy job/history and service generation', 'final video and score geometry']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    protocol = verify_candidate()
    cases = [case for case in protocol['cases'] if case['run_id'] == args.run]
    require(len(cases) == 1, 'unknown fixed run')
    print(json.dumps(check(read(args.audit), cases[0]), indent=2))
