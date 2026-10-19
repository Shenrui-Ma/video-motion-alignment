"""Prepare every valid physical frame for CPU review; review status stays pending."""
import subprocess
from PIL import Image, ImageDraw, ImageFont
from common import *
from render_media import media_info, check_time, choose_font

def pages(valid, per_page=5):
    require(type(valid) is int and valid > 0 and per_page > 0, 'invalid page range')
    return [list(range(start, min(start+per_page, valid))) for start in range(0, valid, per_page)]

def render_files(inputs, destination, total, valid, font, ffmpeg, ffprobe):
    require(len(inputs) in (2, 3) and 0 < valid <= total, 'invalid review shape')
    destination.mkdir(parents=True, exist_ok=True)
    labels = ('1.参考视频', '2.普通编辑', '3.时序引导')[:len(inputs)]
    w, h, row_height = 640, 360, 406
    raw = []
    for file in inputs:
        check_time(media_info(file, ffprobe), total, 1312, 736)
        data = subprocess.check_output([ffmpeg, '-v', 'error', '-threads', '1', '-i', str(file),
            '-vf', 'crop=1280:720:16:8,scale=640:360:flags=lanczos', '-frames:v', str(valid),
            '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-threads', '1', '-'], timeout=180)
        require(len(data) == valid*w*h*3, 'decoded review frame count differs')
        raw.append(data)
    ledger = []
    f = ImageFont.truetype(str(font), 22)
    small = ImageFont.truetype(str(font), 16)
    for page, indices in enumerate(pages(valid)):
        image = Image.new('RGB', (w*len(inputs), row_height*len(indices)), 'black')
        draw = ImageDraw.Draw(image)
        for row, ix in enumerate(indices):
            for col, data in enumerate(raw):
                image.paste(Image.frombytes('RGB', (w, h), data[ix*w*h*3:(ix+1)*w*h*3]), (w*col, row_height*row))
                label = labels[col]
                draw.text((col*w+(w-draw.textlength(label, font=f))/2, row*row_height+382), label, font=f, fill='white')
            draw.text((8, row*row_height+363), f'frame {ix} | {ix/24:.3f}s', font=small, fill='#bbb')
        path = destination/f'{page+1:03d}.jpg'
        require(not path.exists(), 'review page already exists')
        image.save(path, quality=94)
        ledger.append({'file':path.name, 'sha256':sha(path), 'physical_frame_indices':indices})
    return ledger

