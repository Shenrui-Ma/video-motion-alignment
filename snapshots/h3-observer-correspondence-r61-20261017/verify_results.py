"""Reconcile every fixed cell and replay saved decisions with the frozen policy."""
from collections import Counter
import gzip
import json
from pathlib import Path

import gates
import study


def main():
    protocol = study.verify()
    _, policy, _, _, _ = study.load()
    tasks = {t['id']: t for t in protocol['tasks']}
    bindings = {b['path']: b for b in protocol['bindings']}
    for binding in protocol['bindings']:
        assert study.sha(binding['original']) == binding['sha256'], binding['original']
    groups = {'known_shift': 25, 'fixed_cycle': 5, 'additional_ordered_pairs': 15}
    result = {'schema': 'r61-audited-correspondence-summary-v1',
              'protocol_sha256': study.sha(study.HERE / 'PROTOCOL.json'),
              'independent_source_videos': 5,
              'families': {}, 'artifact_bindings': [], 'all_originals_unchanged': True,
              'all_prior_decisions_equal': True, 'verified_cells': 0, 'verified_policy_updates': 0,
              'GPU_calls': 0, 'new_pose_calls': 0, 'generated_video_result': False}
    prior_count = 0
    for family in study.FAMILIES:
        family_result = {}
        for group, expected in groups.items():
            summary_path = study.HERE / 'results' / family / group / 'SUMMARY.json'
            summary = study.read(summary_path)
            result['artifact_bindings'].append({'path': str(summary_path.relative_to(study.HERE)), 'sha256': study.sha(summary_path)})
            assert summary['input_pairs'] == len(summary['records']) == expected
            assert summary['protocol_sha256'] == result['protocol_sha256']
            assert {r['task_id'] for r in summary['records']} == {t['id'] for t in tasks.values() if t['group'] == group}
            output = {v: {'ON': 0, 'ON_ids': [], 'zero_ON_ids': [], 'nonzero_ON': 0,
                          'known_nonzero_denominator': 20 if group == 'known_shift' else None,
                          'original_ON_lost': [], 'new_ON': [], 'wrong_qualified_rows': 0 if group == 'known_shift' else None,
                          'original_qualified_rows': 0, 'retained_qualified_rows': 0,
                          'row_rejection_reasons': {}, 'remaining_cross_source': [],
                          'known_shift_row_rejections': []} for v in study.VARIANTS}
            reason_counts = {v: Counter() for v in study.VARIANTS}
            for record in summary['records']:
                artifact_path = study.HERE / record['artifact']
                assert study.sha(artifact_path) == record['sha256']
                result['artifact_bindings'].append({'path': record['artifact'], 'sha256': record['sha256']})
                with gzip.open(artifact_path, 'rt') as f:
                    artifact = json.load(f)
                task = tasks[record['task_id']]
                assert artifact['task'] == task
                observation = artifact['observation']
                assert observation['source_pose_sha256'] == bindings[task['source']]['sha256']
                assert observation['edited_pose_sha256'] == bindings[task['target']]['sha256']
                assert observation['physical_index'] == 0
                assert observation['observation_domain']['valid_frames_inclusive'] == [0, task['valid_frames'] - 1]
                assert record['variants'] == artifact['variants']
                rows, checks = observation['windows'], artifact['candidate_gates']
                original_candidates = {str(i): row for i, row in enumerate(rows) if policy.candidate(row, .5) is not None}
                assert set(checks) == set(original_candidates)
                for check in checks.values():
                    for gate in ('A', 'B'):
                        assert check[gate]['pass'] == (not check[gate]['reasons'])
                for variant in study.VARIANTS:
                    controller = policy.Policy(.5)
                    filtered = gates.filtered(rows, checks, variant)
                    decisions = [controller.update(i, filtered) for i in (0, 1)]
                    assert decisions == artifact['decisions'][variant], (task['id'], family, variant)
                    assert not decisions[0]['active']
                    result['verified_policy_updates'] += 2
                    result['verified_cells'] += 1
                    details = artifact['variants'][variant]
                    assert details['ON'] == decisions[1]['active']
                    assert details['selected'] == decisions[1]['selected']
                    qualified = [row for row in filtered if policy.candidate(row, .5) is not None]
                    assert details['qualified_rows'] == len(qualified)
                    state = output[variant]
                    state['original_qualified_rows'] += len(original_candidates)
                    state['retained_qualified_rows'] += len(qualified)
                    if details['ON']:
                        state['ON'] += 1
                        state['ON_ids'].append(task['id'])
                        if task['truth_lag'] == 0:
                            state['zero_ON_ids'].append(task['id'])
                        elif task['truth_lag'] is not None:
                            state['nonzero_ON'] += 1
                    if artifact['variants']['original']['ON'] and not details['ON']:
                        state['original_ON_lost'].append(task['id'])
                    if not artifact['variants']['original']['ON'] and details['ON']:
                        state['new_ON'].append(task['id'])
                    if task['truth_lag'] is not None:
                        wrong = sum(any(lag != task['truth_lag'] for lag in policy.candidate(row, .5)['lags'].values()) for row in qualified)
                        assert wrong == details['wrong_qualified_rows']
                        state['wrong_qualified_rows'] += wrong
                    for i, check in checks.items():
                        names = [g for g in ('A', 'B') if g in variant and not check[g]['pass']]
                        if not names:
                            continue
                        reasons = {g + ':' + reason.split(':', 1)[-1] for g in names for reason in check[g]['reasons']}
                        reason_counts[variant].update(reasons)
                        if task['truth_lag'] is not None:
                            state['known_shift_row_rejections'].append({'task_id': task['id'],
                                'window': rows[int(i)]['window'], 'feature': rows[int(i)]['feature'],
                                'reasons': sorted(reasons)})
                    if group != 'known_shift' and details['ON']:
                        selected_rows = []
                        for selected in details['selected']:
                            i = next(i for i, row in enumerate(rows)
                                     if row['window'] == selected['window'] and row['feature'] == selected['feature'])
                            selected_rows.append({'row_index': i, 'selection': selected,
                                                  'A': checks[str(i)]['A'], 'B': checks[str(i)]['B']})
                        state['remaining_cross_source'].append({'task_id': task['id'], 'artifact': record['artifact'],
                                                                'selected_rows': selected_rows})
                assert study.prior_equal(task, family, observation, artifact['decisions']['original']) == artifact['original_prior_verified']
                prior_count += artifact['original_prior_verified'] is True
            for variant, state in output.items():
                state['row_rejection_reasons'] = dict(reason_counts[variant])
                assert state['ON'] == summary['ON_counts'][variant]
            family_result[group] = output
        original_known = family_result['known_shift']['original']
        for variant in ('A', 'B', 'AB'):
            known = family_result['known_shift'][variant]
            cycle = family_result['fixed_cycle'][variant]
            known['preserves_all_original_known_ON'] = not known['original_ON_lost']
            known['preregistered_progression_rule_met'] = (
                not known['zero_ON_ids'] and known['wrong_qualified_rows'] == 0
                and known['nonzero_ON'] == original_known['nonzero_ON']
                and cycle['ON'] < family_result['fixed_cycle']['original']['ON'])
        result['families'][family] = family_result
    assert result['verified_cells'] == 360
    assert result['verified_policy_updates'] == 720
    assert prior_count == 60
    result['prior_observations_and_original_policy_verified'] = prior_count
    study.write(study.HERE / 'VERIFIED_RESULTS.json', result)
    compact = {family: {group: {v: {'ON': d['ON'], 'retained_rows': d['retained_qualified_rows'],
                   'lost_original_ON': len(d['original_ON_lost']), 'wrong_qualified_rows': d['wrong_qualified_rows']}
                   for v, d in groups_.items()} for group, groups_ in family_result.items()}
               for family, family_result in result['families'].items()}
    print(json.dumps(compact, indent=2))
    print(json.dumps({'verified_cells': 360, 'verified_policy_updates': 720,
                      'exact_prior_reproductions': 60, 'sha256': study.sha(study.HERE / 'VERIFIED_RESULTS.json')}))


if __name__ == '__main__':
    main()
