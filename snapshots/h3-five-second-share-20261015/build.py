import base64
import hashlib
import html
import json
import shutil
from pathlib import Path

HOME = Path('/Users/researcher')
SOURCE = HOME / 'Downloads/H3_四组完整版横向对比_Musk_Sam_20261015'
OUT = HOME / 'Downloads/H3_四组5秒对比_便携版_20261015'
SINGLE = HOME / 'Downloads/H3_四组5秒对比_单文件版_20261015.html'
OUT.mkdir(parents=True, exist_ok=True)
manifest = json.loads((SOURCE / 'manifest.json').read_text())
videos = manifest['videos']
credits = (SOURCE / 'CREDITS.txt').read_text()

STYLE = '''
*{box-sizing:border-box}html{color-scheme:dark}body{font:16px system-ui,sans-serif;background:#080808;color:#fff;margin:0 auto;padding:24px;max-width:1968px}h1{font-size:26px;line-height:1.35;margin:0 0 12px}h2{font-size:21px;line-height:1.4;margin:0 0 14px}p{line-height:1.6;color:#ddd}a{color:#fff;text-underline-offset:3px;overflow-wrap:anywhere}section{border-top:1px solid #444;margin:28px 0;padding-top:20px}video{display:block;width:100%;height:auto;aspect-ratio:1968/416;background:#000;margin:14px 0}.toolbar{display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin:18px 0}button,select{font:inherit;border:1px solid #666;border-radius:5px;background:#202020;color:#fff;padding:8px 12px;cursor:pointer}button:hover,button:focus-visible{background:#333}label{display:flex;align-items:center;gap:7px}input{accent-color:#fff}.meta{font-size:14px;color:#aaa}.links{margin:12px 0}summary{cursor:pointer;padding:12px 0}pre{font:13px/1.6 system-ui,sans-serif;white-space:pre-wrap;overflow-wrap:anywhere;color:#bbb}footer{border-top:1px solid #444;padding-top:12px;margin-top:32px}#status{min-height:1.6em}@media(max-width:640px){body{padding:16px}h1{font-size:22px}h2{font-size:18px}.toolbar{gap:8px}button,select{font-size:14px;padding:8px}section{margin:24px 0}video{margin:12px 0}}
'''
SCRIPT = '''
const videos=[...document.querySelectorAll('video')];
const status=document.getElementById('status');
document.querySelectorAll('[data-download]').forEach(a=>{a.href=document.getElementById(a.dataset.download).getAttribute('src')});
document.getElementById('play').onclick=async()=>{const results=await Promise.allSettled(videos.map(v=>v.play()));status.textContent=results.some(r=>r.status==='rejected')?'请点击对应视频的播放按钮。':''};
document.getElementById('pause').onclick=()=>videos.forEach(v=>v.pause());
document.getElementById('restart').onclick=()=>{videos.forEach(v=>{v.pause();v.currentTime=0});status.textContent='已回到开头。'};
document.getElementById('loop').onchange=e=>videos.forEach(v=>v.loop=e.target.checked);
document.getElementById('speed').onchange=e=>videos.forEach(v=>v.playbackRate=Number(e.target.value));
videos.forEach(v=>v.addEventListener('error',()=>{status.textContent='视频未能加载，请使用浏览器打开单文件版，或确认解压后的素材与 index.html 位于同一文件夹。'}));
'''

def data_url(path, mime):
    return 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode('ascii')

def make_page(embedded):
    sections = []
    for i, v in enumerate(videos, 1):
        src = data_url(OUT / v['video'], 'video/mp4') if embedded else html.escape(v['video'], quote=True)
        poster = data_url(OUT / v['preview'], 'image/png') if embedded else html.escape(v['preview'], quote=True)
        sections.append(f'''<section id="case-{i}"><h2>{i:02d} · {html.escape(v['title'])}</h2><video id="video-{i}" aria-label="{html.escape(v['title'])}：参考、未加权、三倍加权" controls playsinline preload="metadata" poster="{poster}" src="{src}" data-source-frames="0-140" data-source-fps="24"></video><p class="links"><a data-download="video-{i}" href="{html.escape(v['video'], quote=True) if not embedded else '#'}" download="{html.escape(v['video'], quote=True)}">下载本组横向对比视频</a></p></section>''')
    share = '本页已内嵌全部视频和预览图。只发送这个 HTML 文件，对方下载后用浏览器打开即可离线观看。' if embedded else '分享时请发送完整 ZIP，并在解压后打开 index.html；单独发送本页文件不会携带视频。'
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>H3 四组完整视频对比 · Musk / Sam</title><style>{STYLE}</style></head><body>
<header><h1>四组视频对比：Musk / Sam</h1><p>完整片段 · 每组 5.875 秒 · 正常速度 · 三栏同帧对照</p><p>从左到右：参考视频 ／ 编辑后视频（未加权）／ 编辑后视频（短时动作三倍加权）。</p><p class="meta">Musk 与 Sam 画面为 AI 人物替换实验，并非本人跳舞实录。保留原有黑底中文标注。</p>
<div class="toolbar"><button id="play" type="button">播放全部</button><button id="pause" type="button">暂停全部</button><button id="restart" type="button">回到开头</button><label><input id="loop" type="checkbox">循环播放</label><label>速度 <select id="speed"><option value="1">1× 原速</option><option value="0.5">0.5×</option><option value="0.25">0.25×</option></select></label></div><p id="status" class="meta" role="status" aria-live="polite"></p></header>
{''.join(sections)}
<footer><p>{share}</p><details><summary>片段说明与素材来源</summary><p>与指定参考页面一致，展示源帧 0–140，共 141 帧，24 fps，实际时长 5.875 秒。相较之前约 2.54 秒的短动作截取，此版恢复完整片段。三栏已合成为一个视频，帧号始终一致。视频静音，未重新推理、变速或补帧。</p><pre>{html.escape(credits)}</pre></details></footer>
<script>{SCRIPT}</script></body></html>'''

for v in videos:
    for key in ['video', 'preview']:
        shutil.copy2(SOURCE / v[key], OUT / v[key])
    assert hashlib.sha256((OUT / v['video']).read_bytes()).hexdigest() == v['sha256']
(OUT / 'index.html').write_text(make_page(False))
SINGLE.write_text(make_page(True))
(OUT / 'CREDITS.txt').write_text(credits)
(OUT / 'README.txt').write_text('四组完整横向对比视频\n每组实际 5.875 秒（141 帧，24 fps），与用户指定参考页面一致；未裁尾、变速、补帧或重新推理。\n\n打开 index.html 即可观看。分享请发送整个 ZIP，对方解压后打开 index.html。\n另有已内嵌全部媒体的单文件 HTML，单发该文件即可离线观看；不要只复制本机 file:// 地址。\n视频顺序：Musk 真人书记舞、Musk 床边舞、Sam 真人书记舞、Sam 床边舞。\n三栏顺序：参考、未加权编辑、短时动作三倍加权编辑。\n')
share_manifest = {'duration_note': 'Full 5.875s matches the supplied reference page, rather than cropping to exactly 5.000s.', 'videos': [{k: v[k] for k in ['title', 'video', 'preview', 'source_frames_inclusive', 'probe', 'sha256']} for v in videos], 'embedded_html': SINGLE.name}
(OUT / 'manifest.json').write_text(json.dumps(share_manifest, ensure_ascii=False, indent=2))
checksums = '\n'.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name for p in sorted(OUT.iterdir()) if p.is_file() and p.name != 'SHA256SUMS')
(OUT / 'SHA256SUMS').write_text(checksums + '\n')
zip_path = shutil.make_archive(str(OUT), 'zip', OUT.parent, OUT.name)
print(json.dumps({'page': str(OUT / 'index.html'), 'single_file': str(SINGLE), 'single_bytes': SINGLE.stat().st_size, 'zip': zip_path, 'zip_bytes': Path(zip_path).stat().st_size, 'video_hashes_unchanged': True}, ensure_ascii=False, indent=2))
