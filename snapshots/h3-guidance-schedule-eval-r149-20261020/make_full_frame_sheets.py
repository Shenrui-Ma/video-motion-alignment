"""Make all-valid-frame new-column contact sheets from validated presentation JPEGs."""
import argparse
from PIL import Image, ImageDraw, ImageFont
from common import ROOT, FONT, read, bound, write, verify_record, require


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--schedule', required=True)
    a = p.parse_args()
    folder = ROOT / 'review' / a.case / a.schedule
    pres = read(folder / 'PRESENTATION.json')
    require(pres['source_id'] == a.case and pres['schedule'] == a.schedule, 'Presentation mismatch')
    out = folder / 'full_frames'
    require(not out.exists(), 'Keep earlier full-frame sheets intact')
    out.mkdir()
    font = ImageFont.truetype(FONT, 20)
    sheets = []
    for first in range(0, pres['valid_frames'], 16):
        frames = list(range(first, min(first + 16, pres['valid_frames'])))
        image = Image.new('RGB', (1920, 300 * ((len(frames) + 3) // 4)), 'black')
        draw = ImageDraw.Draw(image)
        for index, frame in enumerate(frames):
            item = pres['screenshots'][frame]
            require(item['frame'] == frame, 'Frame ordering mismatch')
            verify_record(item)
            source = Image.open(item['file'])
            require(source.size == (2560, 424), 'Unexpected comparison geometry')
            cropped = source.crop((1920, 0, 2560, 360)).resize((480, 270), Image.Resampling.LANCZOS)
            x, y = index % 4 * 480, index // 4 * 300
            image.paste(cropped, (x, y))
            draw.text((x + 12, y + 273), f'{pres["labels"][-1]} · 帧 {frame:03d}', font=font, fill='white')
        path = out / f'frames_{frames[0]:03d}_{frames[-1]:03d}.jpg'
        image.save(path, quality=93, subsampling=0)
        sheets.append({**bound(path), 'frames': frames})
    write(out / 'INDEX.json', {'presentation': bound(folder / 'PRESENTATION.json'),
        'valid_frames': pres['valid_frames'], 'sheets': sheets,
        'scope': 'All valid frames of the new column; spatial resize only; no new temporal sampling.'})
    print(out)


if __name__ == '__main__':
    main()
