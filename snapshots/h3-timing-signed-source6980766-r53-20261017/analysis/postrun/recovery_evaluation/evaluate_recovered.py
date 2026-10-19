"""CPU evaluation of an explicitly recovered continuation, using frozen R53 metrics."""
import argparse
import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
POST = HERE.parent
ROOT = POST.parent.parent
OLD = Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')
LOCK = Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
EXPECTED = {
    'analysis/postrun/PROTOCOL.json': 'be7df1c21c4ca5edd6d137ad345ce537735a8c6ae9b344aee595e1690ff03833',
    'analysis/postrun/evaluate.py': '414f6a5b65eff6d6af7b79968780e6fa2a95ad0801409d8cb4c43b39c67915a8',
    'analysis/postrun/presentation.py': 'c368efc4772a1cc3bd57d8acc79ba13135de81b905626ed077d37c598c6177e2',
    'scripts/timing_metrics.py': 'eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e',
    'analysis/postrun/recovery_evaluation/POLICY_REVIEW_CRITERIA.json': '462c420169870b6771fc32c585af7f6f11af1abb41574d19e0a05b077fcd92dc',
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda: f.read(1048576), b''):
            h.update(part)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def write(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def verify_recovery(directory):
    final = read(directory / 'RECOVERY_FINAL.json')
    release = read(directory / 'RELEASED.json')
    require(final['status'] in ('cross_host_recovered_final_video', 'same_host_recovered_final_video')
            and final['original_run_completed'] is False,
            'explicit recovered continuation identity required')
    if final['status'] == 'same_host_recovered_final_video':
        require(final['outputs']['recovered_final'].get('cross_host') is False and 'same_host_comparison' in final, 'same-host recovery evidence missing')
    require(release['status'] == 'released' and release['RECOVERY_FINAL_sha256'] == sha(directory / 'RECOVERY_FINAL.json'),
            'recovery release is not bound to final output')
    child = release['child']
    own_release = release['release']
    require(child['returncode'] == 0 and own_release['schema'] == 'h3-own-decoder-release-v1'
            and own_release['child_identity'] == child['process']
            and own_release['original_generation_absent'] is True
            and (own_release['nvml_pid_absent'] is True or own_release['pid_reused'] is True),
            'recovery GPU child release missing')
    arithmetic = read(directory / 'FINAL_EULER.json')
    require(sha(directory / 'FINAL_EULER.json') == final['final_euler_sha256'], 'final arithmetic changed')
    if final['status'] == 'same_host_recovered_final_video':
        require(arithmetic.get('cross_host') is False, 'same-host arithmetic evidence missing')
    require(arithmetic['original_run_completed'] is False and arithmetic['step14_exact'] is True
            and arithmetic['final_CPU_GPU_exact'] is True, 'actual Euler arithmetic evidence failed')
    video = directory / 'recovered_final.mp4'
    require(sha(video) == final['outputs']['recovered_final']['file_sha256'], 'recovered video changed')
    require(final['outputs']['recovered_final']['status'] == 'complete', 'recovered video incomplete')
    return video, final


def pending_online(roots=None):
    roots = roots or [Path('/data5/researcher/h3_runs/timing_flexiact_auto_r50_20261017'),
                      Path('/data5/researcher/h3_runs/timing_flexiact_auto_r50_retry_20261017')]
    for root in roots:
        for request in (root / 'audit/observations').glob('step*/request.json'):
            d = request.parent
            if (d / 'native.json').exists() and not any((d / n).exists() for n in ('response.json', 'failure.json')):
                return str(d)
    return None


def table_rows(fixed, common, windows, thresholds):
    rows = []
    for window in windows:
        region = f'fixed_{window[0]}_{window[1]}'
        for feature in ('arm_direction', 'left_arm_direction', 'right_arm_direction'):
            for threshold in thresholds:
                c = str(threshold)
                shared = next((r for r in common[c]['rows'] if r['region'] == region and r['feature'] == feature), {})
                row = {'window_start': window[0], 'window_end': window[1], 'feature': feature, 'confidence': threshold,
                       'common_coverage': shared.get('common_valid_fraction'), 'common_support_status': shared.get('status')}
                for name in ('native', 'recovered_signed_auto'):
                    data = fixed[name][c]
                    item = next((r for r in data['diagnostics'] if r['window'] == window and r['feature'] == feature), {})
                    lag = item.get('reliable_lag_frames')
                    row[name + '_lag_frames'] = 'UNKNOWN' if lag is None else lag
                    row[name + '_status'] = item.get('status', data['status'])
                    row[name + '_flags'] = ';'.join(item.get('flags', []))
                    row[name + '_same_frame_coverage'] = item.get('same_frame', {}).get('coverage')
                    row[name + '_common_error'] = shared.get('runs', {}).get(name, {}).get('same_frame_error_on_common_support')
                rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--final-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'CPU-only environment required')
    for rel, digest in EXPECTED.items():
        require(sha(ROOT / rel) == digest, 'frozen evaluation dependency changed: ' + rel)
    video, final = verify_recovery(args.final_directory)
    protocol = read(POST / 'PROTOCOL.json')
    for path, digest in protocol['frozen_external'].items():
        require(sha(path) == digest, 'frozen runtime changed: ' + path)
    source = ROOT / 'configs/source.pose.json'
    native = POST / protocol['parents']['native']['pose']
    require(sha(source) == protocol['source_pose_sha256'], 'source pose changed')
    require(sha(native) == protocol['parents']['native']['pose_sha256'], 'Native pose changed')
    require(read(native)['video']['sha256'] == protocol['parents']['native']['video_sha256'], 'Native pose/video binding')
    sys.path.insert(0, str(POST))
    import evaluate
    sys.path.insert(0, str(ROOT / 'scripts'))
    import timing_metrics as metrics
    from scan_current_pose import valid_pose
    with LOCK.open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({'status': 'cpu_lock_busy'}))
            return 75
        pending = pending_online()
        if pending:
            print(json.dumps({'status': 'online_observer_priority', 'request': pending}))
            return 75
        require(not args.output.exists(), 'existing/partial evaluation requires review')
        args.output.mkdir(parents=True)
        started = time.monotonic()
        from presentation import render_layout
        source_video = Path(read(source)['video']['path'])
        require(sha(source_video) == read(source)['video']['sha256'], 'source video changed')
        native_video = Path(protocol['parents']['native']['video'])
        require(sha(native_video) == protocol['parents']['native']['video_sha256'], 'Native video changed')
        visuals = render_layout({'SOURCE': source_video, 'native': native_video, 'AUTO': video},
                                args.output / 'media', protocol, protocol['presentation'])
        command = [sys.executable, '-u', str(OLD / 'scripts/pose_probe.py'), '--video', str(video),
                   '--output-dir', str(args.output / 'pose'), '--threads', '4', '--stride', '1']
        for frame in protocol['fixed_visual_frames']:
            command += ['--overlay-frame', str(frame)]
        with (args.output / 'pose.log').open('x') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=600,
                                    env=dict(os.environ, OMP_NUM_THREADS='4', MKL_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4'))
        require(result.returncode == 0, 'pose execution failed; retain technical failure')
        pose = args.output / 'pose' / (video.stem + '.pose.json')
        raw = valid_pose(pose)
        require(raw['video']['sha256'] == sha(video), 'generated pose/video binding')
        provenance = evaluate.check_provenance(read(source)['provenance'], raw['provenance'],
                                              [read(native)['provenance']], read(source)['video']['sha256'])
        case = protocol['cases'][0]
        windows = case['windows'] + case['descriptive_windows']
        require(windows == [[0, 31], [32, 63], [64, 95], [96, 127], [125, 140], [0, 140]], 'predeclared windows changed')
        poses = {'native': native, 'recovered_signed_auto': pose}
        fixed = evaluate.fixed_metrics(source, poses, windows, protocol['thresholds'], metrics)
        write(args.output / 'FIXED_WINDOWS.json', {'windows': windows, 'results': fixed})
        regions = {f'fixed_{a}_{b}': list(range(a, b + 1)) for a, b in windows}
        common = {}
        for threshold in protocol['thresholds']:
            record = evaluate.common_regions(source, poses, regions, threshold, metrics)
            write(args.output / f'COMMON_SUPPORT_{threshold}.json', record)
            common[str(threshold)] = record
        table = table_rows(fixed, common, windows, protocol['thresholds'])
        with (args.output / 'TIMING_TABLE.csv').open('x') as f:
            writer = csv.DictWriter(f, fieldnames=list(table[0]))
            writer.writeheader()
            writer.writerows(table)
        summary = {'status': 'recovered_final_evaluated', 'original_run_completed': False,
                   'RECOVERY_FINAL_sha256': sha(args.final_directory / 'RECOVERY_FINAL.json'),
                   'RELEASED_sha256': sha(args.final_directory / 'RELEASED.json'),
                   'criteria_sha256': EXPECTED['analysis/postrun/recovery_evaluation/POLICY_REVIEW_CRITERIA.json'],
                   'source_pose_sha256': sha(source), 'native_pose_sha256': sha(native),
                   'generated_pose_sha256': sha(pose), 'video_sha256': sha(video),
                   'pose_provenance': provenance,
                   'decode_comparison': final.get('same_host_comparison', final.get('cross_host_comparison')),
                   'recovery_environment': 'same_host' if final['status'].startswith('same_host') else 'cross_host',
                   'windows': windows, 'thresholds': protocol['thresholds'],
                   'fixed_visual_frames': visuals['fixed_frames'], 'comparison_video_sha256': visuals['video_sha256'],
                   'CPU_seconds': time.monotonic() - started,
                   'quality_review': 'pending fixed frames and video; numerical rows retain UNKNOWN',
                   'scope': 'Independent recovered R53 development result versus R47 Native; original failed run remains failed.'}
        write(args.output / 'SUMMARY.json', summary)
        write(args.output / 'FILE_INVENTORY.json', {str(p.relative_to(args.output)): sha(p)
                                                  for p in sorted(args.output.rglob('*')) if p.is_file()})
        print(json.dumps({'status': summary['status'], 'CPU_seconds': summary['CPU_seconds'],
                          'summary_sha256': sha(args.output / 'SUMMARY.json')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
