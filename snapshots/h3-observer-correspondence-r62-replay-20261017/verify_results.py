"""Independent saved-state replay and hash check; each version uses a fresh process."""
import argparse
import gzip
import json
import os
import subprocess
import sys

import replay


def child(name, family):
    protocol = replay.verify()
    spec = protocol['trajectories'][name]
    scanner, policy, _, gates, _, _, evidence, layout = replay.load(spec['version'])
    geometry = scanner.Geometry.from_case(spec['case'])
    path = replay.HERE / 'results' / name / family / 'SUMMARY.json'
    summary = replay.read(path)
    assert len(summary['records']) == 20
    assert [r['index'] for r in summary['records']] == list(range(20))
    actual_controller = policy.Policy(.5)
    controllers = {v: policy.Policy(.5) for v in replay.VARIANTS}
    first = {v: None for v in replay.VARIANTS}
    hashes, updates, committed, priors = [], 0, 0, 0
    for record in summary['records']:
        i = record['index']
        assert record['state'] == spec['state_ledger'][i]['state']
        if record['state'] != 'observed_complete':
            assert record['policy_updated'] is False and record['variants'] is None and record['production_ON'] is None
            continue
        artifact = replay.HERE / record['artifact']
        assert replay.sha(artifact) == record['sha256']
        hashes.append({'path': record['artifact'], 'sha256': record['sha256']})
        with gzip.open(artifact, 'rt') as file:
            payload = json.load(file)
        assert payload['index'] == i and record['variants'] == payload['variants']
        actual = evidence.decision(actual_controller, i, payload['production_observation'])
        assert actual == payload['production_decision']
        actual_execution = replay.execution(actual, geometry, layout)
        assert actual_execution == payload['production_execution']
        assert actual['active'] == record['production_ON']
        committed += 1
        observation, checks = payload['observation'], payload['candidate_gates']
        assert set(checks) == {str(j) for j, row in enumerate(observation['windows']) if policy.candidate(row, .5) is not None}
        for check in checks.values():
            for gate in ('A', 'B'):
                assert check[gate]['pass'] == (not check[gate]['reasons'])
        for variant in replay.VARIANTS:
            rows = gates.filtered(observation['windows'], checks, variant)
            decision = controllers[variant].update(i, rows)
            assert decision == payload['decisions'][variant]
            execution = replay.execution(decision, geometry, layout)
            assert execution == record['variants'][variant]['execution']
            first[variant], causal = replay.divergence(first[variant], i, execution, actual_execution)
            assert causal == record['variants'][variant]['causal_prefix_before_this_step']
            assert first[variant] == record['variants'][variant]['first_execution_divergence_from_production']
            updates += 1
        if family in spec['prior_files']:
            replay.compare_prior(replay.HERE / spec['prior_files'][family][i], observation, payload['decisions']['original'], family)
            priors += 1
    assert updates == spec['observed_steps'] * 4
    assert committed == spec['observed_steps']
    assert first == summary['first_execution_divergence_from_production']
    for v in replay.VARIANTS:
        assert summary['ON_indices'][v] == [r['index'] for r in summary['records'] if r['variants'] and r['variants'][v]['ON']]
    output = {'trajectory': name, 'family': family, 'variant_updates': updates,
              'production_steps_verified': committed, 'prior_originals_verified': priors,
              'summary_sha256': replay.sha(path), 'artifacts': hashes,
              'all_failure_and_missing_states_kept': True, 'all_causal_markers_verified': True}
    replay.write(replay.HERE / f'VERIFIED_{name}_{family}.json', output)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--trajectory', choices=list(replay.SPECS))
    parser.add_argument('--family', choices=replay.FAMILIES)
    args = parser.parse_args()
    if args.trajectory and args.family:
        result = child(args.trajectory, args.family)
        print(json.dumps({k: v for k, v in result.items() if k != 'artifacts'}))
        return
    protocol = replay.verify()
    for b in protocol['bindings']:
        assert replay.sha(b['original']) == b['sha256'], b['original']
    results = []
    for name in replay.SPECS:
        for family in replay.FAMILIES:
            subprocess.run([sys.executable, __file__, '--trajectory', name, '--family', family],
                           check=True, env=dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1'), timeout=120)
            path = replay.HERE / f'VERIFIED_{name}_{family}.json'
            results.append({'path': path.name, 'sha256': replay.sha(path), 'record': replay.read(path)})
    updates = sum(r['record']['variant_updates'] for r in results)
    prior = sum(r['record']['prior_originals_verified'] for r in results)
    production = sum(r['record']['production_steps_verified'] for r in results)
    assert (updates, prior, production) == (432, 80, 108)
    replay.write(replay.HERE / 'VERIFIED_ALL.json', {'protocol_sha256': replay.sha(replay.HERE / 'PROTOCOL.json'),
        'verified_variant_updates': updates, 'prior_originals_verified': prior,
        'production_reconstructions': production, 'unique_committed_production_steps': 54,
        'source_trajectories': 3, 'results': results, 'all_original_bound_files_unchanged': True,
        'GPU_calls': 0, 'new_pose_calls': 0})
    print(json.dumps({'variant_updates': updates, 'prior_originals': prior,
                      'sha256': replay.sha(replay.HERE / 'VERIFIED_ALL.json')}))


if __name__ == '__main__':
    main()
