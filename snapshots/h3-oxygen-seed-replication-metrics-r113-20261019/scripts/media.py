"""CPU media preparation for the three same-time R113 comparison columns."""
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
ROLES = ('source', 'native', 'fixed')
LABELS = ('1.参考视频', '2.普通编辑', '3.时序引导后视频')
FONT = '/System/Library/Fonts/STHeiti Medium.ttc'
VALID, TOTAL, FPS = 98, 107, 24
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
    image = Image.new('RGB', (3840, 88), 'black')
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
               for i in range(3)]
    filters += ['[v0][v1][v2]hstack=inputs=3[top]', '[top][3:v]vstack=inputs=2[out]']
    cmd = [FFMPEG, '-v', 'error', '-y']
    for path in paths:
        cmd += ['-threads', '1', '-i', str(path)]
    cmd += ['-loop', '1', '-framerate', '24', '-i', str(dest/'caption.png'),
            '-filter_complex', ';'.join(filters), '-map', '[out]', '-an',
            '-frames:v', str(VALID), '-r', '24', '-c:v', 'libx264', '-preset', 'fast',
            '-crf', '19', '-pix_fmt', 'yuv420p', '-threads', '4', '-movflags', '+faststart',
            str(dest/'comparison.mp4')]
    subprocess.run(cmd, check=True, timeout=600)
    check_time(info(dest/'comparison.mp4'), VALID, 3840, 808)
    subprocess.run([FFMPEG, '-v', 'error', '-threads', '1', '-i', str(dest/'comparison.mp4'),
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
        image = Image.new('RGB', (3*width, 36+(height+28)*(stop-start)), '#0c0d10')
        draw = ImageDraw.Draw(image)
        for i, label in enumerate(LABELS):
            draw.text((i*width+width/2, 17), label, font=font, fill='white', anchor='mm')
        for row, frame in enumerate(range(start, stop)):
            y = 36+row*(height+28)
            draw.text((10, y+2), f'Frame {frame:03d}  ·  {frame/FPS:.3f}s',
                      font=font, fill='#eedca5')
            for col in range(3):
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


def seed_paths(incoming, seed):
    cfg = read(ROOT/'configs/contract.json')
    require(seed in cfg['seeds'], 'unregistered seed')
    return [incoming/'source.mp4', *[incoming/(cfg['runs'][str(seed)][arm]+'.mp4') for arm in ('native', 'fixed')]]


def render(incoming, output_root, seed, publish=True, fixture_paths=None):
    from common import verify_collection
    if fixture_paths is None:
        verify_collection(incoming)
        paths = seed_paths(incoming, seed)
    else:
        require(publish is False and len(fixture_paths) == 3, 'fixture cannot publish as actual output')
        paths = list(fixture_paths)
    require(not output_root.exists(), 'preserve existing presentation')
    output_root.mkdir(parents=True)
    make_comparison(paths, output_root)
    pages = frame_pages(paths, output_root)
    fixture = fixture_paths is not None
    title = 'CPU版式验证：同一参考视频重复三列' if fixture else f'机舱人物替换：种子 {seed}'
    page_html = ''.join('<details><summary>帧 '+str(p['frames'][0])+'–'+str(p['frames'][-1])+ '</summary><img loading="lazy" src="'+uri(output_root/p['file'])+'"></details>' for p in pages)
    task = ('同一参考视频用于检查画布、时间戳与图注，三个画面均为原视频。' if fixture else
            'IVEBench · short_0252。将手持氧气面罩的男人替换为年长女人，保留男孩、机舱、面罩与动作顺序。输入包含参考视频，无角色参考图。')
    document = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>body{max-width:2100px;margin:24px auto;padding:0 20px;background:#101114;color:#eee;font:18px/1.6 system-ui}p{max-width:1400px}video,img{width:100%;background:#000}details{margin:14px 0}a{color:#b4d7ff}</style><h1>'+title+'</h1><p>'+task+'</p><p>三列依次为参考视频、普通编辑、时序引导后视频。98 个有效帧，24fps，各列对应同一物理时刻。</p><video controls playsinline preload="metadata" poster="'+uri(output_root/'poster.jpg')+'" src="'+uri(output_root/'comparison.mp4')+'"></video><p>任务完成情况、事件可见性与事件时刻分别记录。完整帧审阅覆盖 0–97 帧。</p><a id="download" download="R113_seed'+str(seed)+'.mp4">下载三联视频</a><h2>完整逐帧对照</h2>'+page_html+'<script>document.getElementById("download").href=document.querySelector("video").src</script></html>'
    page = output_root/'index.html'
    page.write_text(document)
    receipt = {'seed': seed, 'roles': ROLES, 'labels': LABELS, 'inputs': {role: bound(path) for role, path in zip(ROLES, paths)},
               'valid_frames': VALID, 'fps': FPS, 'crop_xywh': CROP, 'pages': pages,
               'video': bound(output_root/'comparison.mp4'), 'html': bound(page), 'fixture_only': fixture,
               'visual_review': 'PENDING_FULL98_REVIEW', 'official_MF': 'PENDING_SEPARATE_AUTHORIZED_SCORING'}
    if publish:
        prefix = f'H3_R113_机舱人物替换_种子{seed}_20261019'
        for file, suffix in ((page, '.html'), (output_root/'comparison.mp4', '.mp4')):
            target = Path('/Users/researcher/Downloads')/(prefix+suffix)
            require(not target.exists(), 'published artifact already exists')
            shutil.copy2(file, target)
        receipt['download_html'] = bound(Path('/Users/researcher/Downloads')/(prefix+'.html'))
    save(output_root/'PRESENTATION.json', receipt)
    return receipt


def prepare_mf(incoming, output_root, seed):
    from common import verify_collection
    verify_collection(incoming)
    require(not output_root.exists(), 'preserve previous MF inputs')
    output_root.mkdir(parents=True)
    roles = {}
    crop = f'crop=1280:720:16:8,trim=end_frame={VALID},setsar=1'
    for role, full in zip(ROLES, seed_paths(incoming, seed)):
        check_time(info(full), TOTAL, 1312, 736)
        target = output_root/(role+'_score.mp4')
        subprocess.run([FFMPEG, '-v', 'error', '-threads', '2', '-i', str(full), '-vf', crop,
            '-an', '-fps_mode', 'passthrough', '-c:v', 'libx264', '-qp', '0', '-pix_fmt', 'yuv420p',
            '-threads', '2', str(target)], check=True, timeout=120)
        check_time(info(target), VALID, 1280, 720)
        hashes = frame_hashes(target)
        require(hashes == frame_hashes(full, crop), 'lossless MF crop changed decoded pixels')
        roles[role] = {'full_video': bound(full), 'score_video': bound(target), 'frame_md5': hashes}
    value = {'schema': 'r113-official-ive-mf-inputs-v1', 'benchmark': 'IVEBench', 'source_id': 'short_0252', 'seed': seed,
             'valid_frames': VALID, 'total_frames': TOTAL, 'fps': FPS, 'crop_xywh': CROP,
             'physical_frame_indices': list(range(VALID)), 'roles': roles,
             'pair_gate': bound(incoming/f'seed{seed}_PAIR_GATE.json'), 'aggregate_gate': bound(incoming/'AGGREGATE_GATE.json'),
             'collection': bound(incoming/'COLLECTION.json'), 'status': 'CPU_READY_WAIT_SEPARATE_TRACKER_AUTHORIZATION',
             'protocol': {'official_commit': '2dcf8900ee65197f43854c76f61c66a32bb8dbfc', 'grid_size': 10,
                          'grid_query_frame': 0, 'backward_tracking': False, 'window_len': 60},
             'scores': None, 'GPU_started': False}
    save(output_root/'MF_INPUTS.json', value)
    return value


def combined_index():
    from common import SEEDS
    pieces, bindings = [], {}
    for seed in SEEDS:
        folder = ROOT/'showcase'/str(seed)
        receipt = read(folder/'PRESENTATION.json')
        require(receipt['seed'] == seed and receipt['fixture_only'] is False
                and sha(folder/'comparison.mp4') == receipt['video']['sha256'], 'actual seed presentation differs')
        bindings[str(seed)] = bound(folder/'PRESENTATION.json')
        pieces.append('<section><h2>种子 '+str(seed)+'</h2><video controls playsinline preload="metadata" poster="'+uri(folder/'poster.jpg')+'" src="'+uri(folder/'comparison.mp4')+'"></video></section>')
    page = ROOT/'showcase/index.html'
    require(not page.exists(), 'preserve previous combined presentation')
    page.write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>R113 两种子复核</title><style>body{background:#101114;color:#eee;max-width:2100px;margin:24px auto;padding:0 20px;font:18px/1.65 system-ui}video{width:100%;background:#000}section{margin:32px 0}</style><h1>机舱人物替换：两个新种子的复核</h1><p>IVEBench · 将男人替换为年长女人。每组依次为参考视频、该种子的普通编辑、该种子的时序引导编辑。两组共四条成片均保留；任务验收和动作时刻分别评价。</p>'+''.join(pieces)+'</html>')
    target = Path('/Users/researcher/Downloads/H3_R113_机舱人物替换_两种子复核_20261019.html')
    require(not target.exists(), 'published combined presentation exists')
    shutil.copy2(page, target)
    save(ROOT/'showcase/COMBINED_PRESENTATION.json', {'seed_presentations': bindings, 'html': bound(page), 'download_html': bound(target), 'all_four_retained': True})


