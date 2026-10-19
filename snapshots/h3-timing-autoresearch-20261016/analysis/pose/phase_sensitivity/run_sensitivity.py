"""Run preregistered +/-36 secondary phase sensitivity; never replace primary outputs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--root', default='/data5/researcher/h3_runs/timing_autoresearch_20261016')
    args = parser.parse_args()
    root = Path(args.root)
    protocol_path = root/'analysis/pose/phase_sensitivity/PROTOCOL.json'
    protocol = json.loads(protocol_path.read_text())
    if args.run_id not in protocol['run_ids']:
        raise ValueError('This run is not in the registered phase-sensitivity set')
    observer = root/'scripts/timing_metrics.py'
    if hashlib.sha256(observer.read_bytes()).hexdigest() != protocol['frozen_metrics_sha256']:
        raise ValueError('Frozen observer source changed')
    provenance = json.loads((root/'analysis/pose/pilot'/f'{args.run_id}.history_provenance.json').read_text())
    if provenance['history_status']['status_str'] != 'success' or not provenance['history_status']['completed']:
        raise ValueError('No successful formal history')
    stem = Path(provenance['history_output']['filename']).stem
    pose = root/'analysis/pose/pilot'/f'{stem}.pose.json'
    target = root/'analysis/pose/phase_sensitivity'/args.run_id
    target.mkdir(parents=True, exist_ok=True)
    (target/'protocol.json').write_bytes(protocol_path.read_bytes())
    (target/'primary_provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    for threshold in protocol['secondary']['confidence_thresholds']:
        command = [sys.executable, str(observer), '--source',
                   str(root/'analysis/pose/old_sam/05_real_megumi_v.pose.json'),
                   '--edited', str(pose), '--confidence', str(threshold), '--max-lag', '36',
                   '--window', '50:65', '--output-dir', str(target)]
        result = subprocess.run(command, capture_output=True, text=True)
        (target/f'threshold{threshold}.log').write_text(result.stdout+result.stderr)
        if result.returncode:
            raise RuntimeError(f'Sensitivity measurement failed, threshold{threshold}; logs retained')
        print(result.stdout, end='', flush=True)


if __name__ == '__main__':
    main()
