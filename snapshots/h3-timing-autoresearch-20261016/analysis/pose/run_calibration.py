"""Reproduce all old Sam/VAE CPU pose timing measurements on .9."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')
POSE = ROOT / 'analysis/pose'
cases = {
    '05': ('05_real_megumi_v', ['50:65', '69:81', '80:92', '99:111']),
    '07': ('07_real_ary_v', ['54:69', '75:88', '98:111']),
}
summaries = []
for case, (source, windows) in cases.items():
    for threshold in (0.3, 0.5):
        command = [sys.executable, str(ROOT/'scripts/timing_metrics.py'),
                   '--source', str(POSE/'old_sam'/f'{source}.pose.json'),
                   '--edited', str(POSE/'old_sam'/f'{case}_sam_s1_baseline_00001_.pose.json'),
                   '--edited', str(POSE/'old_sam'/f'{case}_sam_s1_weight3_00001_.pose.json'),
                   '--edited', str(POSE/'vae_roundtrip'/f'{source}_reference_vae_reconstruction_00002_.pose.json'),
                   '--confidence', str(threshold), '--output-dir', str(POSE/'calibration')]
        for window in windows:
            command += ['--window', window]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        (POSE/'calibration'/f'case{case}_threshold{threshold}.stdout.jsonl').write_text(result.stdout)
        for line in result.stdout.splitlines():
            report = json.loads(line)
            summaries.append(report)
            primary = [x for x in report['local_results'] if x['feature'] in ('arm_direction', 'right_arm_direction')]
            print(json.dumps({'file': Path(report['report']).name, 'primary': primary}), flush=True)
(POSE/'calibration/summary.json').write_text(json.dumps(summaries, indent=2)+'\n')
