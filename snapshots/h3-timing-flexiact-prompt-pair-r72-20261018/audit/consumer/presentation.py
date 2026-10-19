"""Exact-frame local presentation of actual R72 P0/P1 outputs."""
import argparse
import base64
import html
import io
import os
import shutil
import subprocess
import time
from common import *
from collect import verify_collection

FONT = Path('/System/Library/Fonts/STHeiti Light.ttc')
TITLES = {'fitness__game_man_5': '举臂健身 · 红金装甲人物', 'one_leg__movie_man_9': '单腿平衡 · 深色西装人物'}
DOWNLOADS = Path('/Users/researcher/Downloads')
HTML_NAME = 'H3_FlexiAct_两组P0_P1提示适配对照_20261018.html'

def filters():
    return ';'.join([f'[{i}:v]trim=end_frame={VALID},setpts=PTS-STARTPTS,setsar=1[v{i}]' for i in range(3)] + ['[v0][v1][v2]hstack=inputs=3:shortest=1[images]', '[images][3:v]vstack=inputs=2:shortest=1[out]'])

def caption(path):
    from PIL import Image, ImageDraw, ImageFont
    require(FONT.exists(), 'Chinese font missing')
    image = Image.new('RGB', (3 * WIDTH, 88), 'black')
    draw = ImageDraw.Draw(image)
    large, small = ImageFont.truetype(str(FONT), 32), ImageFont.truetype(str(FONT), 22)
    draw.text((14, 8), '角色替换', font=small, fill='white')
    for col, label in enumerate(LABELS):
        draw.text((col * WIDTH + (WIDTH - draw.textlength(label, font=large)) / 2, 43), label, font=large, fill='white')
    image.save(path)

def render(pair):
    from PIL import Image, ImageDraw, ImageFont
    intake = HERE / 'incoming' / pair
    gate = verify_collection(intake, pair)
    rows = cases(ROOT, pair)
    paths = [ROOT / 'inputs' / rows[0]['video']] + [intake / (arm + '.mp4') for arm in ARMS]
    for path in paths:
        check_timeline(path)
    output = ROOT / 'showcase' / pair
    if (output / 'PRESENTATION.json').exists():
        record = read(output / 'PRESENTATION.json')
        require(record['gate']['sha256'] == sha(intake / 'PAIR_RUNTIME_GATE.json'), 'gate changed after presentation')
        for key in ('video', 'figure', 'portrait'):
            require(sha(Path(record[key]['file'])) == record[key]['sha256'], 'presentation changed: ' + key)
        return record
    require(not output.exists(), 'retain incomplete presentation for inspection')
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(pair + f'.rendering.{os.getpid()}')
    temp.mkdir()
    started = time.monotonic()
    strip = temp / 'caption.png'
    caption(strip)
    video = temp / 'source_p0_p1_full147.mp4'
    command = ['ffmpeg', '-v', 'error', '-nostdin', '-n']
    for path in paths:
        command += ['-threads', '2', '-i', str(path)]
    command += ['-framerate', str(FPS), '-loop', '1', '-i', str(strip), '-filter_complex_threads', '2', '-filter_complex', filters(), '-map', '[out]', '-frames:v', str(VALID), '-an', '-fps_mode', 'vfr', '-c:v', 'libx264', '-crf', '17', '-preset', 'fast', '-pix_fmt', 'yuv420p', '-threads', '2', '-movflags', '+faststart', str(video)]
    subprocess.run(command, check=True, timeout=600)
    check_timeline(video, 3 * WIDTH, HEIGHT + 88, VALID)
    tile_w, tile_h, row_h = 576, 384, 432
    canvas = Image.new('RGB', (tile_w * 3, row_h * 6), 'black')
    draw = ImageDraw.Draw(canvas)
    font, small = ImageFont.truetype(str(FONT), 18), ImageFont.truetype(str(FONT), 13)
    for row, index in enumerate(INDICES):
        for col, path in enumerate(paths):
            raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-threads', '1', '-i', str(path), '-vf', f'select=eq(n\\,{index}),scale={tile_w}:{tile_h}:flags=lanczos', '-frames:v', '1', '-threads', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'], timeout=90)
            canvas.paste(Image.open(io.BytesIO(raw)).convert('RGB'), (col * tile_w, row * row_h))
            label = LABELS[col]
            draw.text((col * tile_w + (tile_w - draw.textlength(label, font=font)) / 2, row * row_h + tile_h + 20), label, font=font, fill='white')
        draw.text((8, row * row_h + tile_h + 3), f'{index / FPS:.3f}s', font=small, fill='#bbb')
    canvas.save(temp / 'six_times.png')
    portrait = ROOT / 'inputs' / rows[0]['portrait']
    shutil.copy2(portrait, temp / portrait.name)
    os.replace(temp, output)
    record = {'schema': 'r72-actual-presentation-v1', 'source_id': pair, 'gate': bound(intake / 'PAIR_RUNTIME_GATE.json'), 'inputs': [bound(p) for p in paths], 'video': bound(output / video.name), 'figure': bound(output / 'six_times.png'), 'portrait': bound(output / portrait.name), 'frame_indices': INDICES, 'valid_frames': VALID, 'fps': FPS, 'column_width_height': [WIDTH, HEIGHT], 'caption_height': 88, 'six_times_tile_width_height': [tile_w, tile_h], 'selection': 'six uniformly spaced valid source times fixed before seeing R72 outputs', 'labels': LABELS, 'audio': 'muted presentation', 'render_wall_seconds': time.monotonic() - started, 'inference_wall_seconds': {a: gate['runs'][a]['job_wall_seconds'] for a in ARMS}, 'guidance_calls': {'p0': 0, 'p1': 0}, 'visual_review': 'PENDING', 'created_unix': time.time()}
    save(output / 'PRESENTATION.json', record)
    return record

def data_url(path, mime):
    return f'data:{mime};base64,' + base64.b64encode(Path(path).read_bytes()).decode()

def document():
    sections, deliveries = [], []
    for pair in PAIRS:
        out = ROOT / 'showcase' / pair
        if not (out / 'PRESENTATION.json').exists():
            sections.append('<section><h2>' + html.escape(TITLES[pair]) + '</h2><p>等待实际生成结果。</p></section>')
            continue
        r = render(pair)
        rows = cases(ROOT, pair)
        video, figure, portrait = (Path(r[k]['file']) for k in ('video', 'figure', 'portrait'))
        review_file = out / 'HUMAN_REVIEW.json'
        review = read(review_file) if review_file.exists() else {'summary': '视觉核查待完成。'}
        prompts = ''.join('<details><summary>' + c['prompt_version'] + ' 实际提示词</summary><pre>' + html.escape(c['prompt']) + '</pre></details>' for c in rows)
        mime = 'image/jpeg' if portrait.suffix.lower() in ('.jpeg', '.jpg') else 'image/webp'
        sections.append('<section><h2>' + html.escape(TITLES[pair]) + '</h2><div class="reference"><img alt="实际输入的目标人物原图" src="' + data_url(portrait, mime) + '"><div><strong>目标人物参考图</strong><p>人物外观与环境来自这张图。三栏最左侧视频提供动作及其时间顺序。</p></div></div><p>' + html.escape(review['summary']) + '</p><video controls preload="metadata" src="' + data_url(video, 'video/mp4') + '"></video><details open><summary>六个固定时刻 · ' + ', '.join(f'{i / FPS:.3f}s' for i in INDICES) + '</summary><img class="grid" alt="动作参考、P0和P1的六时刻对照" src="' + data_url(figure, 'image/png') + '"></details>' + prompts + '</section>')
        dest = DOWNLOADS / ('H3_FlexiAct_' + pair + '_P0_P1完整147帧_20261018.mp4')
        if not dest.exists() or sha(dest) != r['video']['sha256']:
            temp = dest.with_name(dest.name + '.tmp')
            shutil.copy2(video, temp)
            os.replace(temp, dest)
        deliveries.append({'source_id': pair, 'video': bound(dest), 'gate': r['gate'], 'visual_review': review})
    require(deliveries, 'no actual completed pair to publish')
    text = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>H3 FlexiAct 提示适配对照</title><style>body{margin:0;padding:28px;background:#0b0c10;color:#eee;font:18px/1.65 system-ui}main{max-width:1900px;margin:auto}h1{font-size:30px}h2{font-size:25px}section{padding:22px 0;border-top:1px solid #393b45;margin-top:32px}p{color:#ccd0d7}video,.grid{display:block;width:100%;background:#000;margin:18px 0}.reference{display:flex;gap:24px;align-items:center}.reference img{width:280px;height:190px;object-fit:contain;background:#000}.reference p{max-width:700px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:15px/1.6 monospace;padding:18px;background:#151820}details{margin:18px 0}summary{cursor:pointer}@media(max-width:600px){body{padding:12px}.reference{display:block}.reference img{width:100%}}</style><main><h1>H3 · FlexiAct 角色替换提示适配</h1><p>两组预先固定的官方源视频与目标人物配对。每组依次展示动作参考视频、P0 原始指令编辑、P1 按 H3 协议整理的指令编辑。保留 147 个有效帧，共 6.125 秒；三列使用相同的原始时间。</p><p>P1 明确图像、视频各自的角色，并写出原片动作和保留要求。P0、P1 均为普通 H3 生成，使用同一原始参考输入与初始噪声。此对照检验整套提示适配的影响。</p>' + ''.join(sections) + '</main></html>'
    dest = DOWNLOADS / HTML_NAME
    temp = dest.with_name(dest.name + '.tmp')
    temp.write_text(text)
    os.replace(temp, dest)
    local = ROOT / 'showcase/index_singlefile.html'
    shutil.copy2(dest, local)
    receipt = {'schema': 'r72-local-delivery-v1', 'html': bound(dest), 'local_html': bound(local), 'completed_pairs': len(deliveries), 'fixed_pair_denominator': 2, 'pairs': deliveries, 'embedded_media': {'videos': len(deliveries), 'images': 2 * len(deliveries)}, 'unix': time.time()}
    save(ROOT / 'showcase/DELIVERY.json', receipt)
    return receipt

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=('render', 'document'))
    p.add_argument('--pair', choices=PAIRS)
    a = p.parse_args()
    require(a.action != 'render' or a.pair is not None, 'render requires pair')
    result = render(a.pair) if a.action == 'render' else document()
    print(json.dumps({'action': a.action, 'source_id': a.pair, 'completed': True}, ensure_ascii=False))
