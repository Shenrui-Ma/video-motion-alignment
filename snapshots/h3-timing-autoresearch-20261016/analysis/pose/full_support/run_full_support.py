"""Exploratory full-clip common-support screen; frozen timing endpoints unchanged."""
import argparse
import datetime
import hashlib
import html
import json
from pathlib import Path
import subprocess
import sys


RUNS = {
    'native': 's05_full_seed1_native_x0',
    'mass': 's05_full_seed1_mass_x0',
    'phase_zero': 's05_full_seed1_phase_zero_x0',
    'hard': 's05_full_seed1_hard_x0',
    'mass_late11': 's05_full_seed1_mass_late11_x0',
    'mass_late6': 's05_full_seed1_mass_late6_x0',
    'hard_late11': 's05_full_seed1_hard_late11_x0',
    'phase_plus12': 's05_full_seed1_phase_plus12_x0',
    'phase_minus12': 's05_full_seed1_phase_minus12_x0',
    'offset4': 's05_full_seed1_offset4_x0',
    'offsetm4': 's05_full_seed1_offsetm4_x0',
    'phase_minus12_late11': 's05_full_seed1_phase_minus12_late11_x0',
    'mass_6to14': 's05_full_seed1_mass_6to14_x0',
}
COLORS = ['#555555', '#0072B2', '#D55E00', '#009E73', '#CC79A7', '#E69F00', '#56B4E9', '#8C564B']


def svg_chart(report, destination):
    row = next(x for x in report['results'] if x['feature'] == 'arm_direction' and x['window'] == [0, 140])
    width, height, left, top, plotw, ploth = 1120, 520, 70, 75, 1000, 320
    title = f"Common-support arm-direction error; confidence {report['confidence_threshold']}"
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             f'<text x="{left}" y="28" font-family="sans-serif" font-size="20">{html.escape(title)}</text>',
             f'<text x="{left}" y="52" font-family="sans-serif" font-size="13">Exploratory; same-frame differences are not an action-omission or pure phase score. Coverage {row["common_valid_fraction"]:.1%}.</text>']
    for start, end, color in [(0, 47, '#eeeeee'), (47, 68, '#f5df9a'), (68, 141, '#f5f5f5')]:
        parts.append(f'<rect x="{left+start/140*plotw:.2f}" y="{top}" width="{min(end-start,140-start)/140*plotw:.2f}" height="{ploth}" fill="{color}"/>')
    for error in (0, .5, 1, 1.5, 2):
        y = top+ploth-error/2*ploth
        parts += [f'<line x1="{left}" y1="{y}" x2="{left+plotw}" y2="{y}" stroke="#cccccc"/>',
                  f'<text x="{left-12}" y="{y+5}" text-anchor="end" font-family="sans-serif" font-size="13">{error:g}</text>']
    for frame in (0, 24, 47, 68, 96, 112, 140):
        x = left+frame/140*plotw
        parts.append(f'<text x="{x}" y="{top+ploth+22}" text-anchor="middle" font-family="sans-serif" font-size="13">{frame}</text>')
    for i, (label, result) in enumerate(row['runs'].items()):
        color = COLORS[i % len(COLORS)]
        path, active = [], False
        for frame, value in enumerate(result['per_source_frame_error']):
            if value is None:
                active = False
                continue
            x, y = left+frame/140*plotw, top+ploth-value/2*ploth
            path.append(f'{"L" if active else "M"}{x:.2f},{y:.2f}')
            active = True
        parts.append(f'<path d="{" ".join(path)}" fill="none" stroke="{color}" stroke-width="2"/>')
        x, y = left+(i % 4)*260, 448+(i//4)*24
        parts += [f'<line x1="{x}" y1="{y-4}" x2="{x+20}" y2="{y-4}" stroke="{color}" stroke-width="3"/>',
                  f'<text x="{x+27}" y="{y}" font-family="sans-serif" font-size="13">{html.escape(label)}</text>']
    parts += ['<text x="570" y="434" text-anchor="middle" font-family="sans-serif" font-size="14">Source frame (0-based); missing measurements leave gaps</text>', '</svg>']
    destination.write_text('\n'.join(parts)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='/data5/researcher/h3_runs/timing_autoresearch_20261016')
    parser.add_argument('--tag', required=True, help='Unique output snapshot name; existing snapshots are never overwritten')
    args = parser.parse_args()
    root = Path(args.root)
    home = root/'analysis/pose/full_support'
    protocol = json.loads((home/'PROTOCOL.json').read_text())
    metrics = root/'scripts/timing_metrics.py'
    if hashlib.sha256(metrics.read_bytes()).hexdigest() != protocol['frozen_metrics_sha256']:
        raise ValueError('Frozen metrics changed')
    destination = home/args.tag
    destination.mkdir(exist_ok=False)
    (destination/'protocol.json').write_bytes((home/'PROTOCOL.json').read_bytes())
    paths, pending, failed = {}, [], {}
    for label, run_id in RUNS.items():
        failure_file = root/'analysis/pose/pilot'/f'{run_id}.failure.json'
        if failure_file.is_file():
            failed[label] = json.loads(failure_file.read_text())
            continue
        admission_file = root/'analysis/pose/pilot'/f'{run_id}.history_provenance.json'
        if not admission_file.is_file():
            pending.append(label)
            continue
        admission = json.loads(admission_file.read_text())
        filename = admission['history_output']['filename']
        pose = root/'analysis/pose/pilot'/(Path(filename).stem+'.pose.json')
        status = admission['history_status']
        if status['status_str'] != 'success' or not status['completed'] or not pose.is_file():
            pending.append(label)
            continue
        paths[label] = pose
    paths['x3'] = root/'analysis/pose/old_sam/05_sam_s1_weight3_00001_.pose.json'
    if 'native' not in paths:
        raise ValueError('Native formal pose is required')
    groups = {'all_available': paths}
    groups.update({f'native_vs_{label}': {'native': paths['native'], label: path}
                   for label, path in paths.items() if label != 'native'})
    summary = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'status': protocol['status'], 'pending_arms': pending, 'failed_unscored_arms': failed,
               'available_arms': list(paths), 'groups': {}}
    for group, runs in groups.items():
        summary['groups'][group] = {}
        for threshold in protocol['confidence_thresholds']:
            output = destination/f'{group}.threshold{threshold}.json'
            command = [sys.executable, str(root/'analysis/pose/compare_runs.py'), '--source',
                       str(root/'analysis/pose/old_sam/05_real_megumi_v.pose.json'),
                       '--confidence', str(threshold), '--output', str(output)]
            for label, path in runs.items():
                command += ['--run', f'{label}={path}']
            for window in [[0, 140], *protocol['segments'].values()]:
                command += ['--window', ':'.join(map(str, window))]
            done = subprocess.run(command, capture_output=True, text=True)
            (destination/f'{group}.threshold{threshold}.log').write_text(done.stdout+done.stderr)
            if done.returncode:
                raise RuntimeError(f'Comparison failed: {group}, threshold{threshold}')
            report = json.loads(output.read_text())
            rows = [row for row in report['results'] if row['feature'] == 'arm_direction']
            summary['groups'][group][str(threshold)] = [
                {key: value for key, value in row.items() if key != 'runs'} |
                {'errors': {label: run['same_frame_error_on_common_support'] for label, run in row['runs'].items()}}
                for row in rows]
            svg_chart(report, output.with_suffix('.svg'))
    (destination/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({'saved': str(destination), 'available_arms': list(paths), 'pending_arms': pending,
                      'failed_unscored_arms': failed,
                      'all_available': summary['groups']['all_available']}))


if __name__ == '__main__':
    main()
