"""Inspect actual R112 correspondence indices on representative source frames."""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

SOURCE_SHA = '69e866b1939333f2156732a560aa241e04930d02d2043f65b56bcf81f30a0b2d'
WIDTH, HEIGHT, ROWS, COLS, VALID = 1312, 736, 23, 41, 43
FFMPEG = '/opt/homebrew/bin/ffmpeg'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def spans(count):
    result, cursor = [], 0
    for i in range(count):
        size = (1, 4, 4, 4, 4)[i % 5]
        result.append((cursor, cursor + size - 1))
        cursor += size
    return result


def representative_frames(count):
    # A display convention; these centers are not exact VAE receptive fields.
    return [(a + b) // 2 for a, b in spans(count)]


def token_center(index):
    if type(index) is not int or not 0 <= index < ROWS * COLS:
        raise ValueError('token outside spatial grid')
    row, col = divmod(index, COLS)
    return ((col + .5) * WIDTH / COLS, (row + .5) * HEIGHT / ROWS)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bank-root', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--operator', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert sha(args.source) == SOURCE_SHA, 'R112 source differs'
    spec = importlib.util.spec_from_file_location('r112_bank_reader', args.operator)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    banks, files = {}, {}
    # All 50 actual bank files must exist and verify before selecting display layers.
    collection = {}
    for block in range(50):
        directory = args.bank_root / f'block_{block:02d}'
        bank = module.FrozenBank.load(directory)
        g = bank.metadata['geometry']
        assert g == dict(batch=1, heads=56, total_bins=47, valid_bins=43,
                         frame_rows=943, head_dim=128)
        assert bank.metadata['block'] == block and bank.metadata['source_step'] == 5
        assert bank.metadata['spatial_grid'] == [ROWS, COLS]
        collection[str(block)] = bank.manifest['bank_sha256']
        for name in ('bank.json', 'indices.npz'):
            files[str(directory / name)] = sha(directory / name)
        if block in (0, 25, 49):
            banks[str(block)] = bank.forward.tolist()
    assert spans(VALID)[-1][1] == 144
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    frame_dir = output / 'source_frames'
    frame_dir.mkdir()
    indices = representative_frames(VALID)
    select = '+'.join(f'eq(n,{i})' for i in indices)
    subprocess.run([FFMPEG, '-v', 'error', '-threads', '2', '-i', str(args.source),
                    '-vf', f"select='{select}',scale=656:368:flags=lanczos",
                    '-fps_mode', 'vfr', '-q:v', '2', '-threads', '2',
                    str(frame_dir / '%03d.jpg')], check=True)
    frames = sorted(frame_dir.glob('*.jpg'))
    assert len(frames) == VALID
    # Decode dimensions independently to catch accidental FFmpeg scaling changes.
    from PIL import Image
    for frame in frames:
        with Image.open(frame) as im:
            assert im.size == (656, 368)
    data = {'banks': banks, 'spans': spans(VALID), 'frames': indices,
            'images': ['data:image/jpeg;base64,' + base64.b64encode(p.read_bytes()).decode()
                       for p in frames]}
    template = Path(__file__).with_name('viewer.html').read_text()
    # Ensure embedded JSON cannot terminate its enclosing script tag.
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    html = template.replace('@@DATA@@', payload)
    assert '@@' not in html
    target = output / 'index.html'
    target.write_text(html)
    receipt = {'schema': 'r112-actual-bank-display-v1', 'source_file': str(args.source),
               'source_sha256': SOURCE_SHA, 'operator_reader_sha256': sha(args.operator),
               'bank_files': files, 'collection_sha256': hashlib.sha256(module.canonical(collection)).hexdigest(),
               'display_blocks': [0, 25, 49], 'valid_bins': VALID,
               'representative_frames': indices, 'frame_spans': spans(VALID),
               'frame_files': {str(p): sha(p) for p in frames},
               'output': str(target), 'output_sha256': sha(target),
               'meaning': 'Actual stored token matches overlaid on representative RGB frames. RGB centers are a display convention, not an exact VAE receptive-field claim. Matching acceptance is not ground-truth correspondence.'}
    (output / 'DISPLAY_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: receipt[k] for k in ('output', 'output_sha256', 'collection_sha256')}))


if __name__ == '__main__':
    main()
