"""Bounded source-only metadata/hash audit; no pose or model inference."""
import fcntl
import hashlib
import json
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOCK = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
REGISTRY = ROOT.parent / 'SCREENING_REGISTRY_20261017.json'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(2**20), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    with LOCK.open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('BUSY')
            return 75
        signal.alarm(120)
        started = time.perf_counter()
        registry_sha = sha(REGISTRY)
        assert registry_sha == '351d01d5e3f97e3717ca6349ad7ca2caa8683db699b9519e8bfec4cee74ad410'
        rows = []
        for asset_id, start in [('415', 624), ('1302', 108)]:
            source = ROOT / 'originals' / f'mixkit_{asset_id}_1080.mp4'
            clip = ROOT / 'inspection' / asset_id / f'clip_start{start:04d}_141f24.mp4'
            provenance = json.loads((ROOT / 'originals' / f'{asset_id}_provenance.json').read_text())
            assert sha(source) == provenance['sha256']
            probe = json.loads(subprocess.check_output([
                '/opt/homebrew/bin/ffprobe', '-v', 'error', '-threads', '4',
                '-count_frames', '-show_streams', '-show_format', '-of', 'json', str(clip)
            ], timeout=60))
            stream = probe['streams'][0]
            assert len(probe['streams']) == 1 and stream['codec_type'] == 'video'
            assert stream['r_frame_rate'] == stream['avg_frame_rate'] == '24/1'
            assert int(stream['nb_read_frames']) == int(stream['nb_frames']) == 141
            assert abs(float(stream['duration']) - 141 / 24) < 1e-6
            row = {
                'asset_id': asset_id, 'source_sha256': provenance['sha256'],
                'clip': str(clip), 'clip_sha256': sha(clip),
                'normalized_24fps_source_indices_inclusive': [start, start + 140],
                'source_grid_first_and_last_timestamp_s': [start / 24, (start + 140) / 24],
                'clip_first_and_last_timestamp_s': [0, 140 / 24],
                'clip_duration_s': 141 / 24, 'decoded_frame_count': 141,
                'fps': 24, 'width': stream['width'], 'height': stream['height'],
                'normalization': 'fps=24:round=near, trim normalized indices, reset PTS; temporal resampling may drop/duplicate frames; no optical-flow interpolation',
                'probe': probe,
            }
            rows.append(row)
        assert sha(REGISTRY) == registry_sha
        result = {'status': 'PASS', 'scope': 'source media only', 'cpu_threads_max': 4,
                  'seconds': time.perf_counter() - started,
                  'registry_readonly_sha256': registry_sha, 'rows': rows}
        destination = ROOT / 'SOURCE_MEDIA_AUDIT.json'
        assert not destination.exists()
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'status': 'PASS', 'seconds': result['seconds'],
                          'sha256': sha(destination),
                          'clips': [{k: row[k] for k in ('asset_id', 'clip_sha256', 'decoded_frame_count', 'fps', 'width', 'height')} for row in rows]}))
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
