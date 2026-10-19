"""Render root-prespecified same-time checkpoints from the completed triptych."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    contract = json.loads((root / 'configs/contract.json').read_text())
    pair = next(x for x in contract['pairs'] if x['pair_key'] == args.pair)
    definitions = json.loads((root / 'ROOT_SOURCE_CHECKPOINTS.json').read_text())
    action = pair['motion_source_id']
    if action not in definitions['sources']:
        print(json.dumps({'pair': args.pair, 'status': 'no_prespecified_source_checkpoints'}))
        return
    from PIL import Image, ImageDraw, ImageFont
    checkpoints = definitions['sources'][action]['checkpoints']
    video = root / 'showcase' / (args.pair + '_full_valid.mp4')
    declaration = json.loads((root / 'showcase' / (args.pair + '_PRESENTATION.json')).read_text())
    record = next(x for x in declaration['videos'] if x['physical_frame_interval'] == [0, 146])
    digest = hashlib.sha256(video.read_bytes()).hexdigest()
    assert digest == record['video']['sha256']
    rows = []
    fonts = [Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'), Path('/System/Library/Fonts/PingFang.ttc')]
    font_path = next(path for path in fonts if path.is_file())
    font = ImageFont.truetype(str(font_path), 20)
    for checkpoint in checkpoints:
        n = checkpoint['prepared_index']
        assert 0 <= n < 147 and n == checkpoint['original_index'] * 3
        data = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-threads', '1', '-i', str(video), '-vf', 'select=eq(n\\,' + str(n) + '),scale=1920:-1', '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-threads', '1', '-'], capture_output=True, check=True, timeout=60).stdout
        frame = Image.open(io.BytesIO(data)).convert('RGB')
        row = Image.new('RGB', (frame.width, frame.height + 28), 'black')
        row.paste(frame, (0, 0))
        ImageDraw.Draw(row).text((12, frame.height + 3), 't = ' + format(checkpoint['time_s'], '.3f') + ' s', font=font, fill='white')
        rows.append(row)
    canvas = Image.new('RGB', (rows[0].width, sum(x.height for x in rows)), 'black')
    y = 0
    for row in rows:
        canvas.paste(row, (0, y))
        y += row.height
    out = root / 'showcase' / (args.pair + '_fixed_checkpoints.jpg')
    if out.exists():
        raise FileExistsError(out)
    canvas.save(out, quality=94, subsampling=0)
    receipt = {'pair': args.pair, 'motion_source_id': action, 'video_sha256': digest, 'checkpoint_definition_sha256': hashlib.sha256((root / 'ROOT_SOURCE_CHECKPOINTS.json').read_bytes()).hexdigest(), 'checkpoints': checkpoints, 'figure_sha256': hashlib.sha256(out.read_bytes()).hexdigest(), 'scope': definitions['scope']}
    out.with_suffix('.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'figure': str(out), 'checkpoints': len(rows)}))


if __name__ == '__main__':
    main()
