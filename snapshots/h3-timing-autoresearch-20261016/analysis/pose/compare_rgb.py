"""CPU-only decoded-frame equality audit for passive replay controls."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--reference', required=True)
    p.add_argument('--candidate', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    cv2.setNumThreads(1)
    captures = [cv2.VideoCapture(path, cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS, 1])
                for path in (args.reference, args.candidate)]
    if not all(c.isOpened() for c in captures):
        raise ValueError('Could not decode both MP4 inputs')
    videos = []
    for path, cap in zip((args.reference, args.candidate), captures):
        videos.append({'path': str(Path(path).resolve()), 'sha256': file_hash(path),
                       'fps': cap.get(cv2.CAP_PROP_FPS),
                       'container_frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                       'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                       'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))})
    frames = []
    mismatch_length = False
    while True:
        decoded = [cap.read() for cap in captures]
        if not any(ok for ok, _ in decoded):
            break
        if not all(ok for ok, _ in decoded):
            mismatch_length = True
            break
        a, b = [cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) for _, frame in decoded]
        same_shape = a.shape == b.shape
        if same_shape:
            delta = np.abs(a.astype(np.int16)-b.astype(np.int16))
            identical = not delta.any()
            max_diff, mean_diff = int(delta.max()), float(delta.mean())
            differing_values = int(np.count_nonzero(delta))
        else:
            identical, max_diff, mean_diff, differing_values = False, None, None, None
        frames.append({'frame': len(frames), 'reference_rgb_sha256': hashlib.sha256(a.tobytes()).hexdigest(),
                       'candidate_rgb_sha256': hashlib.sha256(b.tobytes()).hexdigest(),
                       'reference_pts_ms': captures[0].get(cv2.CAP_PROP_POS_MSEC),
                       'candidate_pts_ms': captures[1].get(cv2.CAP_PROP_POS_MSEC),
                       'same_shape': same_shape, 'identical_rgb': identical,
                       'max_abs_rgb_difference': max_diff, 'mean_abs_rgb_difference': mean_diff,
                       'differing_channel_values': differing_values})
    for cap in captures:
        cap.release()
    full_counts = all(len(frames) == v['container_frame_count'] for v in videos)
    identical_geometry = all(videos[0][k] == videos[1][k] for k in ('fps', 'width', 'height'))
    pts_equal = all(abs(row['reference_pts_ms']-row['candidate_pts_ms']) < 1e-6 for row in frames)
    result = {'reference': videos[0], 'candidate': videos[1], 'decoded_paired_frames': len(frames),
              'mismatched_decode_length': mismatch_length, 'complete_container_counts': full_counts,
              'identical_geometry_and_fps': identical_geometry, 'identical_decoder_pts': pts_equal,
              'identical_rgb_frames': sum(row['identical_rgb'] for row in frames),
              'all_decoded_rgb_and_timing_identical': bool(frames and not mismatch_length and full_counts and
                  identical_geometry and pts_equal and all(row['identical_rgb'] for row in frames)),
              'max_abs_rgb_difference': max((row['max_abs_rgb_difference'] or 0 for row in frames), default=None),
              'frames': frames, 'decoder': f'OpenCV {cv2.__version__}, FFmpeg1thread, cvtColor BGR2RGB',
              'script_sha256': file_hash(__file__),
              'scope': 'final decoded MP4 equality for this exact paired run; no audio or cross-seed generalization claim'}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'frames'}))


if __name__ == '__main__':
    main()
