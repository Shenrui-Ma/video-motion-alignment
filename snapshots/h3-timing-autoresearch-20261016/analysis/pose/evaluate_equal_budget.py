"""Frozen common-support schedule comparison; no image inference or threshold fitting."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')
HOME = ROOT/'analysis/pose'
RUNS = {'native': 's05_full_seed1_native_x0', 'mass': 's05_full_seed1_mass_x0',
        'mass_late6': 's05_full_seed1_mass_late6_x0', 'mass_late11': 's05_full_seed1_mass_late11_x0',
        'mass_6to14': 's05_full_seed1_mass_6to14_x0'}


def main():
    protocol_path = HOME/'mass_equal_call_budget_protocol_copy.json'
    protocol = json.loads(protocol_path.read_text())
    digest = hashlib.sha256((ROOT/'scripts/timing_metrics.py').read_bytes()).hexdigest()
    assert digest == protocol['evaluation']['frozen_metrics_sha256']
    inventories, poses, phases = {}, {}, {}
    for label, run in RUNS.items():
        admission = json.loads((HOME/'pilot'/f'{run}.history_provenance.json').read_text())
        assert admission['history_status']['completed'] and admission['history_status']['status_str'] == 'success'
        if label == 'mass_6to14':
            assert admission['config_sha256'] == protocol['graph_sha256']
        stem = Path(admission['history_output']['filename']).stem
        poses[label] = HOME/'pilot'/f'{stem}.pose.json'
        inventories[label] = {'admission': admission, 'pose_sha256': hashlib.sha256(poses[label].read_bytes()).hexdigest()}
        phases[label] = {}
        for threshold in (.3, .5):
            raw = json.loads((HOME/'pilot'/f'{stem}.threshold{threshold}.timing.json').read_text())
            phases[label][str(threshold)] = [row for row in raw['diagnostics'] if row['feature'] == 'arm_direction']
    dest = HOME/'equal_budget/full_schedule_comparison'
    dest.mkdir(parents=True, exist_ok=False)
    (dest/'protocol.json').write_bytes(protocol_path.read_bytes())
    result = {'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'inventory': inventories, 'frozen_direction_diagnostics': phases,
              'integrity_and_visual_gates': 'Separate parent input/operator/tensor gates and fixed55/86 visual review required.',
              'interpretation': protocol['interpretation'], 'thresholds': {}}
    for threshold in (.3, .5):
        key = str(threshold)
        primary = {label: next(row for row in phases[label][key] if row['window'] == [50, 65]) for label in RUNS}
        lag = {label: row.get('reliable_lag_frames') for label, row in primary.items()}
        result['thresholds'][key] = {'primary_lags': lag,
                                     'native_minus_early9_lag': None if lag['native'] is None or lag['mass_6to14'] is None
                                     else lag['native']-lag['mass_6to14']}
        cmd = [sys.executable, str(HOME/'compare_runs.py'), '--source', str(HOME/'old_sam/05_real_megumi_v.pose.json'),
               '--confidence', key, '--output', str(dest/f'common_support.threshold{threshold}.json')]
        for label, path in poses.items():
            cmd += ['--run', f'{label}={path}']
        for window in ('50:65', '69:81', '80:92', '99:111', '0:140', '0:46', '47:67', '68:140', '112:140'):
            cmd += ['--window', window]
        check = subprocess.run(cmd, capture_output=True, text=True)
        (dest/f'threshold{threshold}.log').write_text(check.stdout+check.stderr)
        if check.returncode:
            raise RuntimeError('Common-support failed; original log retained')
    (dest/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'saved': str(dest), 'thresholds': result['thresholds']}))


if __name__ == '__main__':
    main()
