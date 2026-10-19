"""CPU media preparation for the four actual, same-time R111 comparison columns."""
import base64
import html
import json
from pathlib import Path
import shutil
import subprocess
from PIL import Image, ImageDraw, ImageFont

from common import ROOT, read, save, sha, require, bound

FFMPEG = '/opt/homebrew/bin/ffmpeg'
FFPROBE = '/opt/homebrew/bin/ffprobe'
ROLES = ('source', 'native', 'fixed', 'spatial')
LABELS = ('1.参考视频', '2.普通编辑', '3.固定时序引导', '4.保留空间分布的时序引导')
FONT = '/System/Library/Fonts/STHeiti Medium.ttc'
VALID, TOTAL, FPS = 145, 158, 24
CROP = (16, 8, 1280, 720)


def info(path):
    raw = subprocess.check_output([FFPROBE, '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time',
        '-of', 'json', str(path)])
    value = json.loads(raw)
    require(len(value['streams']) == 1, 'one video stream required')
    stream = value['streams'][0]
    return {**stream, 'pts_s': [float(f['best_effort_timestamp_time']) for f in value['frames']]}


def check_time(value, count, width, height):
    require((value['width'], value['height'], value['avg_frame_rate']) ==
            (width, height, '24/1'), 'video geometry or frame rate differs')
    times = value['pts_s']
    require(len(times) == count and all(abs(t-i/FPS) < 1e-6 for i, t in enumerate(times)),
            'physical frame timestamps differ')


def frame_hashes(path, vf=None):
    cmd = [FFMPEG, '-v', 'error', '-threads', '1', '-i', str(path), '-an']
    if vf:
        cmd += ['-vf', vf]
    cmd += ['-threads', '1', '-f', 'framemd5', '-']
    output = subprocess.check_output(cmd, text=True)
    return [line.rsplit(',', 1)[1].strip() for line in output.splitlines()
            if line and not line.startswith('#')]


def caption(path):
    image = Image.new('RGB', (5120, 88), 'black')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT, 30)
    draw.text((22, 7), '主体编辑', font=font, fill='#dddddd')
    for i, label in enumerate(LABELS):
        draw.text((i*1280+640, 57), label, font=font, fill='white', anchor='mm')
    image.save(path)


def make_comparison(paths, dest):
    for path in paths:
        check_time(info(path), TOTAL, 1312, 736)
    caption(dest/'caption.png')
    filters = [f'[{i}:v]trim=end_frame={VALID},setpts=PTS-STARTPTS,crop=1280:720:16:8[v{i}]'
               for i in range(4)]
    filters += ['[v0][v1][v2][v3]hstack=inputs=4[top]', '[top][4:v]vstack=inputs=2[out]']
    cmd = [FFMPEG, '-v', 'error', '-y']
    for path in paths:
        cmd += ['-threads', '1', '-i', str(path)]
    cmd += ['-loop', '1', '-framerate', '24', '-i', str(dest/'caption.png'),
            '-filter_complex', ';'.join(filters), '-map', '[out]', '-an',
            '-frames:v', str(VALID), '-r', '24', '-c:v', 'libx264', '-preset', 'fast',
            '-crf', '19', '-pix_fmt', 'yuv420p', '-threads', '4', '-movflags', '+faststart',
            str(dest/'four_columns.mp4')]
    subprocess.run(cmd, check=True, timeout=600)
    check_time(info(dest/'four_columns.mp4'), VALID, 5120, 808)
    subprocess.run([FFMPEG, '-v', 'error', '-threads', '1', '-i', str(dest/'four_columns.mp4'),
                    '-frames:v', '1', '-threads', '1', str(dest/'poster.jpg')],
                   check=True, timeout=60)


def frame_pages(paths, dest):
    width, height = 480, 270
    decoded = []
    for path in paths:
        raw = subprocess.check_output([FFMPEG, '-v', 'error', '-threads', '1', '-i', str(path),
            '-an', '-vf', f'crop=1280:720:16:8,scale={width}:{height}:flags=lanczos',
            '-frames:v', str(VALID), '-threads', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
        size = width*height*3
        require(len(raw) == VALID*size, 'full-frame evidence decode differs')
        decoded.append([Image.frombytes('RGB', (width, height), raw[i*size:(i+1)*size])
                        for i in range(VALID)])
    pages = []
    font = ImageFont.truetype(FONT, 20)
    for start in range(0, VALID, 5):
        stop = min(start+5, VALID)
        image = Image.new('RGB', (4*width, 36+(height+28)*(stop-start)), '#0c0d10')
        draw = ImageDraw.Draw(image)
        for i, label in enumerate(LABELS):
            draw.text((i*width+width/2, 17), label, font=font, fill='white', anchor='mm')
        for row, frame in enumerate(range(start, stop)):
            y = 36+row*(height+28)
            draw.text((10, y+2), f'Frame {frame:03d}  ·  {frame/FPS:.3f}s',
                      font=font, fill='#eedca5')
            for col in range(4):
                image.paste(decoded[col][frame], (col*width, y+28))
        name = f'frames_{start:03d}-{stop-1:03d}.jpg'
        image.save(dest/name, quality=94)
        pages.append({'file': name, 'frames': list(range(start, stop)), 'sha256': sha(dest/name)})
    require([i for p in pages for i in p['frames']] == list(range(VALID)),
            'frame ledger must cover every physical frame once')
    save(dest/'FRAME_LEDGER.json', {'valid_frames': VALID, 'fps': FPS, 'roles': ROLES,
         'pages': pages, 'review_status': 'PENDING_HUMAN_OR_AGENT_FULL_FRAME_REVIEW'})
    return pages


def uri(path):
    mime = 'video/mp4' if Path(path).suffix == '.mp4' else 'image/jpeg'
    return 'data:'+mime+';base64,'+base64.b64encode(Path(path).read_bytes()).decode()


def render(incoming, output_root, publish=True):
    require(not output_root.exists(), 'preserve the existing presentation')
    output_root.mkdir(parents=True)
    paths = [incoming/(role+'.mp4') for role in ROLES]
    make_comparison(paths, output_root)
    pages = frame_pages(paths, output_root)
    title = 'H3_R111_空间分布保持_四列对比_20261019'
    page_html = ''.join('<details><summary>帧 '+str(p['frames'][0])+'–'+str(p['frames'][-1])+
        '</summary><img loading="lazy" src="'+uri(output_root/p['file'])+'"></details>' for p in pages)
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>时序引导与空间分布</title><style>body{max-width:2400px;margin:24px auto;padding:0 20px;background:#101114;color:#eee;font:18px/1.6 system-ui}p{max-width:1300px}video,img{width:100%;background:#000}details{margin:14px 0}a{color:#b4d7ff}</style><h1>衣服改色：时序引导与空间分布</h1><p>IVEBench · long_0174。任务：将女子的白色衣服改为黑色，保留人物、行走动作、镜头与场景。</p><p>四列依次为参考视频、普通编辑、R107固定时序引导、R111保留空间注意力分布的时序引导。</p><video controls playsinline preload="metadata" poster="'''+uri(output_root/'poster.jpg')+'" src="'+uri(output_root/'four_columns.mp4')+'''"></video><p>145个有效帧，24fps。各列按同一物理时刻拼接。完整成片用于检查改色、姿态、动作时刻和画面稳定性；逐帧对照覆盖全部有效帧。</p><p>任务完成情况与官方 Motion Fidelity 随本组成片评测更新。</p><a id="download" download="'''+html.escape(title)+'''.mp4">下载完整四列视频</a><h2>完整逐帧对照</h2>'''+page_html+'''<script>document.getElementById('download').href=document.querySelector('video').src</script></html>'''
    local_html = output_root/'index.html'
    local_html.write_text(document)
    receipt = {'roles': ROLES, 'labels': LABELS, 'inputs': {r: bound(p) for r, p in zip(ROLES, paths)},
        'valid_frames': VALID, 'fps': FPS, 'crop_xywh': CROP, 'pages': pages,
        'video': bound(output_root/'four_columns.mp4'), 'html': bound(local_html),
        'official_MF': 'PENDING_ACTUAL_SCORING', 'visual_review': 'PENDING_FULL145_REVIEW',
        'fixture_only': not publish}
    if publish:
        downloads = Path('/Users/researcher/Downloads')
        for file, suffix in ((local_html, '.html'), (output_root/'four_columns.mp4', '.mp4')):
            target = downloads/(title+suffix)
            require(not target.exists(), 'published artifact already exists')
            shutil.copy2(file, target)
        receipt['download_html'] = bound(downloads/(title+'.html'))
        receipt['download_video'] = bound(downloads/(title+'.mp4'))
    save(output_root/'PRESENTATION.json', receipt)
    return receipt


def prepare_mf(incoming, output_root):
    require(not output_root.exists(), 'preserve existing MF input preparation')
    output_root.mkdir(parents=True)
    crop = f'crop=1280:720:16:8,trim=end_frame={VALID},setsar=1'
    roles = {}
    for role in ROLES:
        full = incoming/(role+'.mp4')
        check_time(info(full), TOTAL, 1312, 736)
        target = output_root/(role+'_score.mp4')
        subprocess.run([FFMPEG, '-v', 'error', '-threads', '2', '-i', str(full), '-vf', crop,
            '-an', '-fps_mode', 'passthrough', '-c:v', 'libx264', '-qp', '0',
            '-pix_fmt', 'yuv420p', '-threads', '2', str(target)], check=True, timeout=120)
        check_time(info(target), VALID, 1280, 720)
        hashes = frame_hashes(target)
        require(hashes == frame_hashes(full, crop), 'lossless MF crop changed pixels')
        roles[role] = {'full_video': bound(full), 'score_video': bound(target), 'frame_md5': hashes}
    value = {'schema': 'r111-official-ive-mf-inputs-v1', 'source_id': 'long_0174',
        'valid_frames': VALID, 'total_frames': TOTAL, 'fps': FPS, 'crop_xywh': CROP,
        'physical_frame_indices': list(range(VALID)), 'roles': roles,
        'pair_gate': bound(incoming/'PAIR_RUNTIME_GATE.json'),
        'collection': bound(incoming/'COLLECTION.json'), 'status': 'INPUTS_READY_NO_TRACKER_STARTED',
        'protocol': {'benchmark': 'IVEBench', 'official_commit': '2dcf8900ee65197f43854c76f61c66a32bb8dbfc',
            'grid_size': 10, 'grid_query_frame': 0, 'backward_tracking': False, 'window_len': 60},
        'scores': None}
    save(output_root/'MF_INPUTS.json', value)
    return value
