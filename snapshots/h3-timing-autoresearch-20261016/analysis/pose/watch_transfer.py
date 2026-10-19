"""Wait for complete pilot videos, then run serial CPU pose diagnostics.

This is an analysis consumer only; it never queues inference or controls services.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='/data5/researcher/h3_runs/timing_autoresearch_20261016_transfer0')
    parser.add_argument('--tool-root', default='/data5/researcher/h3_runs/timing_autoresearch_20261016', help='Read-only frozen pose/metric tools; output remains in --root')
    parser.add_argument('--run-id', action='append', default=[])
    parser.add_argument('--prompt-id', help='optional exact ComfyUI prompt UUID, useful for retried run IDs')
    parser.add_argument('--port', type=int, default=8460)
    parser.add_argument('--history-only', action='store_true', help='Consume exact controller-saved histories without contacting a ComfyUI port')
    parser.add_argument('--source', help='source pose JSON; defaults to old source05')
    parser.add_argument('--window', action='append', default=[])
    parser.add_argument('--timeout-minutes', type=int, default=180)
    args = parser.parse_args()
    root = Path(args.root)
    tool_root = Path(args.tool_root)
    analysis = root/'analysis/pose/pilot'
    analysis.mkdir(parents=True, exist_ok=True)
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    os.environ['OPENBLAS_NUM_THREADS'] = '1'
    import cv2
    cv2.setNumThreads(1)
    started = time.monotonic()
    requested = args.run_id or ['s05_seed1_native']
    if any('bench' in name.lower() for name in requested):
        raise ValueError('Benchmark jobs must not enter formal pose evaluation')
    completed = []
    def record_failure(run_id, prompt_id, kind, detail):
        record = {'run_id': run_id, 'prompt_id': prompt_id, 'status': kind, 'detail': detail,
                  'included_in_formal_run_inventory': True}
        (analysis/(run_id+'.failure.json')).write_text(json.dumps(record, indent=2)+'\n')
        print(json.dumps(record), flush=True)
        completed.append(run_id)

    while time.monotonic()-started < args.timeout_minutes*60:
        history = {}
        history_error = None
        if args.history_only:
            history_error = 'Waiting for exact controller-saved histories'
        else:
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/history', timeout=10) as response:
                    history = json.load(response)
            except Exception as error:
                history_error = str(error)
        # A sealed service may exit before the next polling interval. Read only
        # exact requested run histories persisted by the controller, not MP4 globs.
        for run_id in requested:
            saved = root/'logs'/f'{run_id}_history.json'
            if saved.is_file():
                try:
                    entry = json.loads(saved.read_text())
                    history[entry['prompt'][1]] = entry
                except (json.JSONDecodeError, KeyError, IndexError):
                    pass  # A controller write may still be in progress.
        if not history:
            print(json.dumps({'history_unavailable': history_error or 'No completed history yet'}), flush=True)
            time.sleep(60)
            continue
        for prompt_id, entry in history.items():
            if args.prompt_id and prompt_id != args.prompt_id:
                continue
            graph = entry['prompt'][2]
            routers = [node for node in graph.values()
                       if node['class_type'] in ('H3TemporalRouter', 'H3PhaseRoPE')]
            if len(routers) != 1:
                continue
            run_id = routers[0]['inputs']['run_id']
            if run_id not in requested or run_id in completed:
                continue
            status = entry.get('status', {})
            if status.get('status_str') == 'error':
                record_failure(run_id, prompt_id, 'generation_failed', status)
                continue
            if status.get('status_str') != 'success' or not status.get('completed'):
                continue
            config_path = root/'configs'/f'{run_id}.json'
            if not config_path.is_file():
                record_failure(run_id, prompt_id, 'job_config_missing', str(config_path))
                continue
            config_data = config_path.read_bytes()
            config = json.loads(config_data)
            references = [node['inputs'] for node in config.values() if node['class_type'] == 'H3EventAuditReference']
            creators = [node['inputs'] for node in config.values() if node['class_type'] == 'CreateVideo']
            if len(references) != 1 or len(creators) != 1:
                record_failure(run_id, prompt_id, 'job_config_geometry_ambiguous', str(config_path))
                continue
            expected = {name: references[0][name] for name in ('width', 'height')}
            expected['frames'] = references[0]['length']
            expected['fps'] = creators[0]['fps']
            (analysis/(run_id+'.config_snapshot.json')).write_bytes(config_data)
            save_nodes = [key for key, node in graph.items() if node['class_type'] == 'SaveVideo']
            files = [item for key in save_nodes for item in entry.get('outputs', {}).get(key, {}).get('images', [])
                     if item.get('type') == 'output' and item.get('filename', '').endswith('.mp4')]
            if len(files) != 1:
                record_failure(run_id, prompt_id, 'history_output_invalid', files)
                continue
            item = files[0]
            video = root/'output'/item.get('subfolder', '')/item['filename']
            if not video.is_file():
                record_failure(run_id, prompt_id, 'history_output_missing', str(video))
                continue
            stat = video.stat()
            fingerprint = (stat.st_size, stat.st_mtime_ns)
            capture = cv2.VideoCapture(str(video))
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = capture.get(cv2.CAP_PROP_FPS)
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            capture.release()
            record = {'run_id': run_id, 'prompt_id': prompt_id, 'history_status': status,
                      'history_output': item, 'file': str(video), 'frames': frame_count,
                      'fps': fps, 'width': width, 'height': height,
                      'expected_geometry_from_config': expected, 'config_path': str(config_path),
                      'config_sha256': hashlib.sha256(config_data).hexdigest(),
                      'included_in_formal_run_inventory': True}
            (analysis/(run_id+'.history_provenance.json')).write_text(json.dumps(record, indent=2)+'\n')
            if (frame_count != expected['frames'] or abs(fps-expected['fps']) > 1e-6 or
                    (width, height) != (expected['width'], expected['height'])):
                record_failure(run_id, prompt_id, 'formal_output_geometry_failed', record)
                continue
            command = [sys.executable, str(tool_root/'scripts/pose_probe.py'), '--video', str(video),
                       '--output-dir', str(analysis), '--overlay-frame', '55', '--overlay-frame', '63',
                       '--overlay-frame', '86', '--overlay-frame', '105']
            with (analysis/(video.stem+'.extract.log')).open('w') as log:
                extract = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
            if extract.returncode:
                record_failure(run_id, prompt_id, 'pose_extraction_failed', {'returncode': extract.returncode})
                continue
            if (video.stat().st_size, video.stat().st_mtime_ns) != fingerprint:
                raise RuntimeError('Input MP4 changed during extraction; do not use this measurement')
            for threshold in (0.3, 0.5):
                command = [sys.executable, str(tool_root/'scripts/timing_metrics.py'),
                           '--source', args.source or str(root/'analysis/pose/old_sam/05_real_megumi_v.pose.json'),
                           '--edited', str(analysis/(video.stem+'.pose.json')),
                           '--confidence', str(threshold), '--output-dir', str(analysis)]
                for window in args.window or ['50:65', '69:81', '80:92', '99:111']:
                    command += ['--window', window]
                result = subprocess.run(command, capture_output=True, text=True)
                if result.returncode:
                    record_failure(run_id, prompt_id, 'pose_measurement_failed',
                                   {'threshold': threshold, 'stderr': result.stderr, 'video_retained': str(video)})
                    break
                (analysis/(video.stem+f'.threshold{threshold}.stdout.jsonl')).write_text(result.stdout)
                for line in result.stdout.splitlines():
                    summary = json.loads(line)
                    print(json.dumps({'report': summary['report'], 'primary': [
                        row for row in summary['local_results'] if row['feature'] in ('arm_direction', 'right_arm_direction')]}), flush=True)
            if run_id not in completed:
                completed.append(run_id)
        (analysis/'watcher_completed.json').write_text(json.dumps({'completed': completed, 'requested_run_ids': requested}, indent=2)+'\n')
        if set(completed) == set(requested):
            return
        time.sleep(60)
    print(json.dumps({'status': 'wait_timeout', 'completed': completed, 'requested_run_ids': requested}), flush=True)


if __name__ == '__main__':
    main()
