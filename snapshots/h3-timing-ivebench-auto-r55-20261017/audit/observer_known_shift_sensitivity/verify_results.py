"""Verify saved diagnostic artifacts without rerunning the scanner."""
from collections import Counter
import gzip
import json
from pathlib import Path
import diagnose as d


def main():
    d.verify_sources()
    scanner, policy = d.load_modules()
    protocol = json.loads((d.HERE / 'source_snapshot/configs/protocol.json').read_text())
    cases = {c['source_id']: c for c in protocol['cases']}
    validated, by_version = [], {}
    for version in ('r55_original', 'r56_arm_only'):
        report = json.loads((d.HERE / version / 'SUMMARY.json').read_text())
        expected = [(c, shift) for c in cases for shift in d.SHIFTS]
        assert [(r['source_id'], r['known_lag_frames']) for r in report['records']] == expected
        for record in report['records']:
            case = cases[record['source_id']]
            source = d.HERE / 'source_snapshot' / case['source_pose_path']
            original = json.loads(source.read_text())
            target = d.HERE / record['target_file']
            assert d.sha(target) == record['target_sha256']
            actual = json.loads(target.read_text())
            assert actual == d.shifted(original, case['valid_frame_count'], record['known_lag_frames'])
            scanner.valid_pose(target, scanner.Geometry.from_case(case))
            full = d.HERE / record['scan_file']
            assert d.sha(full) == record['scan_sha256']
            with gzip.open(full, 'rt') as f:
                result = json.load(f)
            observation = result['observation']
            assert observation['source_pose_sha256'] == d.sha(source) == record['source_pose_sha256']
            assert observation['edited_pose_sha256'] == d.sha(target)
            expected_summary, expected_policy = d.summary(observation, policy, record['known_lag_frames'])
            assert expected_policy == result['policy']
            assert all(record[k] == value for k, value in expected_summary.items())
            assert not record['first_possible_ON']
            # These are observed outcome checks, not construction assumptions.
            assert all(x['lags'] == [record['known_lag_frames']] * 2 for x in record['reliable_lag_pairs'])
            if record['known_lag_frames'] == 0:
                assert not record['second_identical_observation_possible_ON']
            validated.append({'version': version, 'source_id': record['source_id'], 'shift': record['known_lag_frames']})
        nonzero = [r for r in report['records'] if r['known_lag_frames']]
        zero = [r for r in report['records'] if not r['known_lag_frames']]
        by_version[version] = {
            'fixed_sources': 5, 'nonzero_shift_cells': 20,
            'nonzero_with_exact_lag': sum(r['exact_groundtruth_rows'] > 0 for r in nonzero),
            'nonzero_possible_ON_after_second_repeat': sum(r['second_identical_observation_possible_ON'] for r in nonzero),
            'nonzero_UNKNOWN_cells': sum(r['reliable_rows'] == 0 for r in nonzero),
            'zero_shift_cells': 5, 'zero_with_reliable_zero': sum(r['exact_groundtruth_rows'] > 0 for r in zero),
            'zero_UNKNOWN_cells': sum(r['reliable_rows'] == 0 for r in zero),
            'zero_possible_ON': sum(r['second_identical_observation_possible_ON'] for r in zero),
            'reliably_reported_wrong_lag_cells': sum(any(p['lags'] != [r['known_lag_frames']]*2 for p in r['reliable_lag_pairs']) for r in report['records']),
        }
    d.save(d.HERE / 'VERIFIED.json', {'passed': True, 'verified_cells': len(validated),
             'transformation_and_source_SHA': True, 'all_target_geometry_validated': True,
             'saved_policy_and_summary_recomputed': True, 'scanner_rerun': False,
             'count_note': 'Twenty nonzero synthetic transformations are grouped within five source cases, not twenty independent videos.',
             'by_version': by_version, 'cells': validated})
    print(json.dumps(by_version, indent=2))


if __name__ == '__main__':
    main()
