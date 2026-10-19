"""Frozen observer replay on saved Native trajectory; never an intervention result."""
import argparse
from collections import Counter
import gzip
import json
import os
from pathlib import Path
import sys
from contract import ROOT, check_package, read, require, require_sequence, sha
sys.path.insert(0, str(ROOT / 'vendor'))
from common import write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--representation', choices=['original', 'visible'], required=True)
    parser.add_argument('--poses', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'CPU replay only')
    p = check_package()
    receipt = read(args.poses / 'COMPLETE.json')
    require(receipt['status'] == 'complete' and receipt['protocol_sha256'] == sha(ROOT / 'configs/PROTOCOL.json'), 'pose batch complete/protocol')
    require_sequence(receipt['steps'])
    source = args.poses / 'source.pose.json'
    require(sha(source) == receipt['source_adult_pose_sha256'], 'source pose SHA')
    for row in receipt['steps']:
        require(sha(args.poses / f"step{row['index']:03d}" / 'adult.pose.json') == row['adult_pose_sha256'], 'target pose SHA')
    vendor = ROOT / 'vendor' / args.representation
    sys.path[:0] = [str(vendor / 'scripts'), str(vendor / 'extensions')]
    import scan_current_pose as scanner
    import timing_metrics as m
    from H3AutomaticWindowRouter.geometry import Geometry
    from H3AutomaticWindowRouter.automatic_window_policy import Policy
    from pose_all import acquire
    geometry = Geometry(**p['geometry'])
    args.output.mkdir(parents=True, exist_ok=False)
    decisions = []
    policy = Policy(.5)
    with open(p['host9']['cpu_lock'], 'a') as lock:
        acquire(lock)
        for i in range(20):
            target = args.poses / f'step{i:03d}' / 'adult.pose.json'
            obs = scanner.observe(source, target, i, geometry)
            decision = policy.update(i, obs['windows'])
            selected = decision['selected']
            record = dict(index=i, status='complete', observer_status=obs['status'], reasons=obs.get('reasons', []),
                          row_count=len(obs['windows']), baseline_counts=dict(Counter(r['baseline'] for r in obs['windows'])),
                          candidate_groups=len(decision['groups']), active=decision['active'], reason=decision['reason'],
                          selected=selected, physical_intervals=decision['physical_intervals'],
                          source_pose_sha256=sha(source), target_pose_sha256=sha(target),
                          scan_seconds=obs['scan_seconds'])
            full = args.output / f'step{i:03d}.json.gz'
            with gzip.open(full, 'wt', encoding='utf8') as stream:
                json.dump(m.clean({'observation': obs, 'decision': decision}), stream, allow_nan=False)
            record.update(full_evidence=full.name, full_evidence_sha256=sha(full))
            write(args.output / f'step{i:03d}_summary.json', record)
            decisions.append(record)
            print(json.dumps({k: record[k] for k in ['index', 'observer_status', 'candidate_groups', 'active', 'physical_intervals']}), flush=True)
    require_sequence(decisions)
    active = [r['index'] for r in decisions if r['active']]
    summary = dict(schema='r81-offline-observer-replay-v1', status='complete', representation=args.representation,
                   protocol_sha256=sha(ROOT / 'configs/PROTOCOL.json'), fixed_observation_denominator=20,
                   first_qualified_candidate_index=next((r['index'] for r in decisions if r['candidate_groups']), None),
                   first_persistent_ON_index=active[0] if active else None, ON_indices=active, steps=decisions,
                   interpretation='All measurements come from the saved Native trajectory. After a hypothetical first ON, later observations cannot predict the corrected trajectory. UNKNOWN means insufficient evidence, not synchronization. Candidate windows are exhaustive original16/32 stride4, never final-output selected.')
    write(args.output / 'SUMMARY.json', summary)


if __name__ == '__main__':
    main()
