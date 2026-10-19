from pathlib import Path
import hashlib
import json
import subprocess

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
PARENT = Path('/Users/researcher/DevProjects/h3-timing-flexiact-prompt-pair-r72-20261018')
SOURCE = PARENT / 'inputs/source_fitness_original.mp4'
PREPARED = PARENT / 'inputs/source_fitness_video.mp4'
TARGET = PARENT / 'inputs/target_game_man_5.jpeg'
GENERATED = PARENT / 'audit/consumer/incoming/fitness__game_man_5/p1.mp4'
GATE = PARENT / 'audit/consumer/incoming/fitness__game_man_5/PAIR_RUNTIME_GATE.json'
FFMPEG = '/opt/homebrew/bin/ffmpeg'
FFPROBE = '/opt/homebrew/bin/ffprobe'
W, H = 384, 256


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frames(path, count):
    command = [FFMPEG, '-v', 'error', '-nostdin', '-threads', '1', '-i', str(path),
               '-vf', f'scale={W}:{H}:flags=area', '-frames:v', str(count),
               '-fps_mode', 'passthrough', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-']
    data = subprocess.check_output(command)
    size = W * H * 3
    assert len(data) == count * size
    return [Image.frombytes('RGB', (W, H), data[i * size:(i + 1) * size])
            for i in range(count)]


def probe(path):
    command = [FFPROBE, '-v', 'error', '-select_streams', 'v:0', '-show_entries',
               'stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time',
               '-of', 'json', str(path)]
    value = json.loads(subprocess.check_output(command))
    return {'stream': value['streams'][0],
            'pts': [float(f['best_effort_timestamp_time']) for f in value['frames']]}


def main():
    gate = json.loads(GATE.read_text())
    assert gate['passed'] and gate['runs']['p1']['routed_blocks'] == 0
    assert digest(GENERATED) == gate['runs']['p1']['video']['sha256']
    original, prepared, generated = map(probe, [SOURCE, PREPARED, GENERATED])
    assert len(original['pts']) == 49 and original['stream']['avg_frame_rate'] == '8/1'
    assert len(generated['pts']) == 158 and generated['stream']['avg_frame_rate'] == '24/1'
    assert prepared['pts'] == generated['pts']
    assert all(abs(t - i / 24) < 1e-6 for i, t in enumerate(generated['pts']))
    source_frames, generated_frames = frames(SOURCE, 49), frames(GENERATED, 147)
    font = ImageFont.truetype('/System/Library/Fonts/Monaco.ttf', 17)
    page_receipts = []
    for page in range(7):
        image = Image.new('RGB', (W * 4, 50 + (H + 30) * 7), 'black')
        draw = ImageDraw.Draw(image)
        draw.text((8, 9), 'SOURCE 8fps | P1 Native at 24fps: all 147 valid frames', fill='white', font=font)
        rows = []
        for row in range(7):
            source_index = page * 7 + row
            y = 50 + row * (H + 30)
            image.paste(source_frames[source_index], (0, y + 30))
            draw.text((8, y + 5), f'SOURCE {source_index:02d} | {source_index / 8:.3f}s', fill='white', font=font)
            indexes = []
            for offset in range(3):
                index = source_index * 3 + offset
                x = W * (offset + 1)
                image.paste(generated_frames[index], (x, y + 30))
                draw.text((x + 8, y + 5), f'P1 {index:03d} | {index / 24:.3f}s', fill='white', font=font)
                indexes.append(index)
            rows.append({'source_frame': source_index, 'source_time': source_index / 8,
                         'P1_frames': indexes, 'P1_times': [i / 24 for i in indexes]})
        path = OUT / f'all_valid_page_{page + 1:02d}.jpg'
        image.save(path, quality=94, subsampling=0)
        page_receipts.append({'file': str(path), 'sha256': digest(path), 'rows': rows})
    manifest = {'schema': 'fitness-P1-all-valid-frames-review-v1',
                'gate': {'file': str(GATE), 'sha256': digest(GATE), 'passed': True},
                'inputs': [{'file': str(p), 'sha256': digest(p)} for p in [SOURCE, PREPARED, TARGET, GENERATED]],
                'source': original, 'prepared': prepared, 'P1': generated,
                'reviewed_generated_frames': list(range(147)),
                'source_temporal_resolution_seconds': 0.125,
                'note': 'Each row shows one original source frame and its three corresponding generated times. Source has no observation between consecutive 8fps frames. No timing precision below that source interval is claimed.',
                'pages': page_receipts}
    (OUT / 'MEDIA_EVIDENCE.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'pages': len(page_receipts), 'P1_frames': 147, 'source_frames': 49, 'dir': str(OUT)}))


if __name__ == '__main__':
    main()
