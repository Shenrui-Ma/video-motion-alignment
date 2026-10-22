"""Release actual Native/ON valid-prefix crops without retiming."""
import argparse
import subprocess
import time
from common import *
from bindings import official, validate_source_row, validate_full, validate_edited, crop_filter
from collect_pair import validate_gate

def prepare(source, ffmpeg, ffprobe):
    started = time.monotonic()
    expected = entry(source); count = expected['input_protocol']['effective_frame_count']; total = expected['input_protocol']['h3_frame_count']
    intake = ROOT / 'incoming' / source; collection = read(intake / 'COLLECTION.json')
    for name, digest in collection['files'].items():
        require(sha(intake / name) == digest, 'intake changed: ' + name)
    gate_path = intake / 'PAIR_RUNTIME_GATE.json'; gate = validate_gate(read(gate_path), source)
    row = source_row(source); validate_source_row(row, expected, ffprobe, ffmpeg)
    out = ROOT / 'prepared' / source
    require(not (out / 'METRIC_INPUTS.json').exists(), 'existing pair preparation must be preserved')
    for method in METHODS:
        run = gate['runs'][method]; video = intake / (method + '.mp4')
        require(sha(video) == run['video']['sha256'], 'actual output SHA differs')
        history = intake / (method + '_history.json'); job = read(intake / (method + '_job.json')); h = read(history); graph = read(intake / (method + '_graph.json'))
        require(h['status']['completed'] is True and h['status']['status_str'] == job['status'] == 'success' and h['prompt'][2] == graph and job['graph_sha256'] == sha(intake / (method + '_graph.json')), 'actual history/job/graph differs')
        require(graph['5']['inputs']['prompt'] == expected['edit_prompt'] and graph['5']['inputs']['length'] == total, 'actual official task/length differs')
        validate_full(official.media_info(video, ffprobe), total)
        target = out / (method + '_score.mp4')
        command = [ffmpeg, '-v', 'error', '-nostdin', '-n', '-threads', '2', '-i', str(video), '-map', '0:v:0', '-an', '-vf', crop_filter(count), '-vsync', '0', '-c:v', 'libx264', '-preset', 'fast', '-crf', '0', '-pix_fmt', 'yuv420p', '-threads', '2', str(target)]
        subprocess.run(command, check=True, timeout=180)
        row['edited'][method] = {'score_video': bound(target), 'full_video': bound(video), 'generation_record': bound(history), 'release_record': bound(gate_path)}
        validate_edited(row['edited'][method], count, ffprobe, ffmpeg, total)
    row['producer_runtime_gate'] = bound(gate_path)
    save(out / 'METRIC_INPUTS.json', row)
    save(out / 'READY.json', {'passed': True, 'source': source, 'fixed_denominator': 4, 'valid_frames': count, 'total_frames': total, 'metric_inputs': bound(out / 'METRIC_INPUTS.json'), 'time_samples': 'i/24 seconds; no interpolation or alignment; crop16,8,1280,720', 'wall_seconds': time.monotonic() - started, 'tracker_started': False})
    return out / 'READY.json'

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--source', choices=PAIRS, required=True); p.add_argument('--ffmpeg', default='ffmpeg'); p.add_argument('--ffprobe', default='ffprobe')
    a = p.parse_args(); verify_runtime()
    with cpu_lock():
        print(prepare(a.source, a.ffmpeg, a.ffprobe))
