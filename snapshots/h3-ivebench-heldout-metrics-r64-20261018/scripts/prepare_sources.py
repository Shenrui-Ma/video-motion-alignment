"""Produce exact valid-prefix source crops on CPU, independently of generated results."""
import argparse
import subprocess
from common import *
from bindings import official, crop_filter, validate_source_row

def prepare(source, ffmpeg, ffprobe):
    expected = entry(source)
    count = expected['input_protocol']['effective_frame_count']
    out = ROOT / 'prepared' / source
    out.mkdir(exist_ok=True)
    manifest = out / 'SOURCE_INPUTS.json'
    require(not manifest.exists(), 'existing source preparation; preserve it')
    video = ROOT / 'inputs' / (source + '_video.mp4')
    target = out / 'source_score.mp4'
    command = [ffmpeg, '-v', 'error', '-nostdin', '-n', '-threads', '2', '-i', str(video), '-map', '0:v:0', '-an', '-vf', crop_filter(count), '-vsync', '0', '-c:v', 'libx264', '-preset', 'fast', '-crf', '0', '-pix_fmt', 'yuv420p', '-threads', '2', str(target)]
    subprocess.run(command, check=True, timeout=180)
    row = {'pair_id': source, 'selection_sha256': sha(SELECTION),
           'source_original': bound(ROOT / 'inputs' / (source + '_original.mp4')),
           'source_prepared_video': bound(video),
           'source_preparation_record': bound(ROOT / 'inputs' / (source + '_provenance.json')),
           'source_score_video': bound(target), 'score_frame_indices': list(range(count)),
           'input_to_original_frame': expected['input_protocol']['input_to_original_frame'], 'edited': {}}
    validate_source_row(row, expected, ffprobe, ffmpeg)
    save(manifest, row)
    save(out / 'SOURCE_PREPARATION.json', {'passed': True, 'source': source, 'total_frames': expected['input_protocol']['h3_frame_count'], 'valid_frames': count, 'fixed_denominator': 4, 'manifest': bound(manifest), 'command': command, 'tracker_started': False})
    return manifest

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', choices=PAIRS, action='append')
    p.add_argument('--ffmpeg', default='ffmpeg'); p.add_argument('--ffprobe', default='ffprobe')
    a = p.parse_args(); verify_runtime()
    with cpu_lock():
        for source in a.source or PAIRS:
            print(prepare(source, a.ffmpeg, a.ffprobe))
