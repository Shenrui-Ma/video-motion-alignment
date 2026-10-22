"""Read original archives only; uniformly scale full frames for visual audit."""
import hashlib
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SWITCH = Path('/Users/researcher/DevProjects/h3-short-event-switching-20261013')
FAST = Path('/Users/researcher/DevProjects/h3-fast-motion-followup-20261013')
SPECS = {
    '05_real_megumi_v': (SWITCH, [6, 36, 47, 56, 72, 90, 112, 132]),
    '06_anime_eye_insert': (SWITCH, [18, 41, 47, 61, 77, 96, 112, 132]),
    '07_real_ary_v': (SWITCH, [12, 30, 46, 61, 77, 84, 96, 126]),
    '04_fast_motion': (FAST, [4, 20, 34, 48, 60, 76, 96, 106]),
}
FONT = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 17)
W, H = 352, 198
manifest = {'method': 'Decode original raw archive MP4 by zero-based frame index; uniformly scale entire frame. No crop, masking, temporal warp, interpolation, or image generation.', 'pages': [], 'inputs': {}}
for case, (root, indices) in SPECS.items():
    files = [('SOURCE', root/'inputs'/f'{case}.mp4')]
    files += [(label.upper(), root/'outputs'/f'{case}_{label}_00001_.mp4') for label in ['a_s1', 'b_s1', 'a_s2', 'b_s2']]
    frames = []
    for label, path in files:
        assert path.is_file(), path
        selection = '+'.join(f'eq(n,{n})' for n in indices)
        result = subprocess.run(['/opt/homebrew/bin/ffmpeg', '-v', 'error', '-i', str(path), '-vf', f"select='{selection}',scale={W}:{H}", '-vsync', '0', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], check=True, capture_output=True)
        size = W*H*3
        assert len(result.stdout) == size*len(indices), (path, len(result.stdout))
        frames.append([Image.frombytes('RGB',(W,H),result.stdout[n*size:(n+1)*size]) for n in range(len(indices))])
        manifest['inputs'][str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    for page in range(2):
        canvas = Image.new('RGB',(5*W,4*(H+27)+32),'black')
        draw = ImageDraw.Draw(canvas)
        draw.text((8,5),f'{case} | ORIGINAL ARCHIVE | same-frame audit | page {page+1}',font=FONT,fill='white')
        for row in range(4):
            i = page*4+row
            for col,(label,_) in enumerate(files):
                x,y=col*W,32+row*(H+27)
                draw.text((x+5,y+3),f'{label} | f{indices[i]:03d} | {indices[i]/24:.3f}s',font=FONT,fill='white')
                canvas.paste(frames[col][i],(x,y+27))
        path=HERE/f'{case}_raw_landmarks_p{page+1}.jpg'
        canvas.save(path,quality=96)
        manifest['pages'].append({'path':str(path),'case':case,'frames':indices[page*4:page*4+4]})
(HERE/'render_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'pages':len(manifest['pages']),'raw_inputs':len(manifest['inputs'])}))
