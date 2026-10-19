"""Lossless IVEBench scoring views, with explicit original physical sample maps."""
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
import shutil
import subprocess

WIDTH, HEIGHT, FPS = 1280, 720, 24
FRAME_BYTES = WIDTH * HEIGHT * 3 // 2


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def tools():
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    require(ffmpeg and ffprobe, 'existing ffmpeg and ffprobe required')
    version = subprocess.check_output([ffmpeg, '-version'], text=True, timeout=10).splitlines()[0]
    return ffmpeg, ffprobe, version


def probe(path, ffprobe):
    return json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-select_streams', 'v:0',
        '-show_streams', '-show_frames', '-show_entries',
        'stream=width,height,r_frame_rate,avg_frame_rate,time_base:frame=best_effort_timestamp_time',
        '-of', 'json', str(path)], text=True, timeout=60))


def check_video_grid(value, count, width, height):
    require(len(value['streams']) == 1, 'one video stream required')
    stream = value['streams'][0]
    require((stream['width'], stream['height']) == (width, height), 'score dimensions differ')
    require(Fraction(stream['r_frame_rate']) == Fraction(FPS) and
            Fraction(stream['avg_frame_rate']) == Fraction(FPS), 'score fps differs')
    times = [float(x['best_effort_timestamp_time']) for x in value['frames']]
    require(len(times) == count and all(math.isfinite(t) and abs(t - i / FPS) < 1e-6
                                      for i, t in enumerate(times)), 'score frame/time grid differs')
    return times


def raw_hashes(raw):
    require(len(raw) % FRAME_BYTES == 0, 'incomplete decoded frame')
    return [hashlib.md5(raw[i:i + FRAME_BYTES]).hexdigest() for i in range(0, len(raw), FRAME_BYTES)]


def decode(ffmpeg, path, transform=None):
    command = [ffmpeg, '-v', 'error', '-threads', '2', '-filter_threads', '2', '-i', str(path), '-an']
    if transform:
        command += ['-vf', transform]
    command += ['-vsync', '0', '-pix_fmt', 'yuv420p', '-threads', '2', '-f', 'rawvideo', '-']
    return subprocess.run(command, check=True, capture_output=True, timeout=120).stdout, command


def encode(ffmpeg, raw, destination):
    destination = Path(destination)
    require(not destination.exists(), 'existing release requires review')
    command = [ffmpeg, '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'yuv420p',
               '-s:v', f'{WIDTH}x{HEIGHT}', '-r', str(FPS), '-i', 'pipe:0', '-an',
               '-c:v', 'libx264', '-crf', '0', '-preset', 'fast', '-threads', '2',
               '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(destination)]
    subprocess.run(command, input=raw, check=True, capture_output=True, timeout=120)
    return command


def source_view(prepared, original, provenance, destination):
    p = json.loads(Path(provenance).read_text())
    count = p['effective_frame_count']
    require(sha(original) == p['source_sha256'] and sha(prepared) == p['video_sha256'],
            'original/prepared source differs')
    mapping = p['input_to_original_frame']
    require(len(mapping) == 90 and p['decoded_pixel_mapping_exact'] is True,
            'original input mapping record differs')
    require(p['input_frame_md5'] == [p['original_transformed_frame_md5'][i] for i in mapping],
            'recorded original-to-prepared decoded pixels differ')
    record = edited_view(prepared, count, destination)
    record.update(kind='source_score', original=str(original), original_sha256=sha(original),
                  input_provenance=str(provenance), input_provenance_sha256=sha(provenance),
                  input_to_original_frame=mapping, selected_original_indices=mapping[:count])
    # Original transformed hashes include the recorded padding. Verify the exact
    # prepared90 bytes against that producer record before publishing the crop.
    ffmpeg, _, _ = tools()
    raw, _ = decode(ffmpeg, prepared)
    size = 1312 * 736 * 3 // 2
    actual = [hashlib.md5(raw[i:i + size]).hexdigest() for i in range(0, len(raw), size)]
    require(actual == p['input_frame_md5'], 'actual prepared decoded pixels differ from provenance')
    save(Path(destination).with_suffix('.mapping.json'), record)
    return record


def edited_view(full_video, count, destination):
    ffmpeg, ffprobe, version = tools()
    require(type(count) is int and 1 <= count <= 90, 'edited valid prefix differs')
    check_video_grid(probe(full_video, ffprobe), 90, 1312, 736)
    raw, decode_command = decode(ffmpeg, full_video, 'crop=1280:720:16:8,setsar=1')
    all_hashes = raw_hashes(raw)
    require(len(all_hashes) == 90, 'full generated frame count differs')
    selected = raw[:count * FRAME_BYTES]
    encode_command = encode(ffmpeg, selected, destination)
    actual_raw, _ = decode(ffmpeg, destination)
    require(raw_hashes(actual_raw) == all_hashes[:count], 'generated crop decoded pixel mismatch')
    times = check_video_grid(probe(destination, ffprobe), count, WIDTH, HEIGHT)
    record = {'kind': 'edited_score', 'source': str(full_video), 'source_sha256': sha(full_video),
              'destination': str(destination), 'destination_sha256': sha(destination),
              'crop_xywh': [16, 8, 1280, 720], 'input_indices': list(range(count)),
              'physical_seconds': times, 'terminal_padding_excluded': True,
              'decoded_pixel_mapping_exact': True, 'full_cropped_frame_md5': all_hashes,
              'score_frame_md5': all_hashes[:count], 'ffmpeg': ffmpeg, 'ffmpeg_version': version,
              'decode_command': decode_command, 'encode_command': encode_command}
    save(Path(destination).with_suffix('.mapping.json'), record)
    return record


def reuse_source(prepared, original, provenance, published, destination):
    """Reuse published score bytes and recheck their exact current prepared crop."""
    p = json.loads(Path(provenance).read_text())
    require(sha(prepared) == p['video_sha256'] and sha(original) == p['source_sha256'],
            'reused source original/prepared differs')
    record = json.loads(Path(published).with_suffix('.mapping.json').read_text())
    require(record['kind'] == 'source_score' and record['input_provenance_sha256'] == sha(provenance)
            and record['source_sha256'] == sha(prepared) and record['original_sha256'] == sha(original)
            and record['destination_sha256'] == sha(published), 'published source binding differs')
    ffmpeg, ffprobe, _ = tools()
    count = p['effective_frame_count']
    check_video_grid(probe(prepared, ffprobe), 90, 1312, 736)
    expected_raw, _ = decode(ffmpeg, prepared, 'crop=1280:720:16:8,setsar=1')
    actual_raw, _ = decode(ffmpeg, published)
    require(raw_hashes(actual_raw) == raw_hashes(expected_raw)[:count] == record['score_frame_md5'],
            'reused source decoded pixels differ')
    check_video_grid(probe(published, ffprobe), count, WIDTH, HEIGHT)
    require(not Path(destination).exists(), 'existing reused release requires review')
    shutil.copyfile(published, destination)
    require(sha(destination) == sha(published), 'reused source copy differs')
    record.update(source=str(prepared), original=str(original), input_provenance=str(provenance),
                  destination=str(destination), reused_source=str(published), reused_same_bytes=True)
    save(Path(destination).with_suffix('.mapping.json'), record)
    return record
