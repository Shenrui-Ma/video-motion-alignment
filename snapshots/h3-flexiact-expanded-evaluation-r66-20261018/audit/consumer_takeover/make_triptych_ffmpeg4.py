"""Administrative FFmpeg 4 compatibility; retains frozen display filters and inputs."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import make_triptych as frozen
from common import PAIR_KEYS, cpu_lock, read, require, save


def compatible(cmd):
    cmd = list(cmd)
    index = cmd.index('-fps_mode')
    require(cmd[index + 1] == 'vfr', 'unexpected display time policy')
    cmd[index] = '-vsync'
    return cmd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', required=True, choices=PAIR_KEYS)
    args = parser.parse_args()
    original = frozen.build
    frozen.build = lambda *a, **kw: compatible(original(*a, **kw))
    with cpu_lock():
        output = frozen.run(args.pair)
        rows = []
        for entry in read(output / (args.pair + '_PRESENTATION.json'))['videos']:
            video = entry['video']['file']
            result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_frames', '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', video], check=True, capture_output=True, text=True, timeout=120)
            pts = [float(f['best_effort_timestamp_time']) for f in json.loads(result.stdout)['frames']]
            count = entry['physical_frame_interval'][1] + 1
            require(len(pts) == count, 'display frame count changed')
            require(all(abs(t - i / 24) < 0.00001 for i, t in enumerate(pts)), 'display physical PTS changed')
            rows.append({'video': entry['video'], 'frames': len(pts), 'PTS_24fps_exact_within_10us': True})
        save(output / (args.pair + '_FFMPEG4_COMPAT.json'), {'compatibility': '-fps_mode vfr mapped to FFmpeg 4 -vsync vfr', 'frozen_filters_unchanged': True, 'videos': rows})


if __name__ == '__main__':
    main()
