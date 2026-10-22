"""CPU-only review derivatives. The sealed experiment is read-only."""
import hashlib
import html
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SOURCE = Path('/Users/researcher/DevProjects/h3-short-event-switching-20261013')
DEST = Path(__file__).resolve().parent
FF = '/opt/homebrew/bin/ffmpeg'
FP = '/opt/homebrew/bin/ffprobe'
FONT = '/System/Library/Fonts/STHeiti Light.ttc'
W, H, HEADER, FOOTER = 560, 440, 66, 38
PANEL_H = HEADER + H + FOOTER
LABELS = ['原片 SOURCE', 'A · 普通提示词', 'B · 明确强调小动作']
COLORS = ['#2463a5', '#327452', '#945492']
SPECS = [
    dict(case='05_real_megumi_v', seed=1, title='黑裙改红 · 种子 1', bounds=[42, 88],
         crop=[480, 120, W, H], overview=[56, 70, 79],
         ranges=[[[50,65]], [[65,80]], [[65,80]]],
         note='原目标 f50–65；A/B 在约 f65–80 出现。目标仍在，约晚 15 帧，周围动作也延后。'),
    dict(case='05_real_megumi_v', seed=2, title='黑裙改红 · 种子 2', bounds=[42, 88],
         crop=[480, 120, W, H], overview=[56, 73, 80],
         ranges=[[[50,65]], [[65,81]], [[65,81]]],
         note='原目标 f50–65；A/B 在约 f65–81 出现。另有明显背景误改，请结合全画面查看。'),
    dict(case='07_real_ary_v', seed=1, title='白衣改蓝 · 种子 1', bounds=[42, 108],
         crop=[440, 0, W, H], overview=[61, 77, 100],
         ranges=[[[54,69]], [[70,85]], [[70,85]]],
         note='源核心 f60–62；A/B 核心约 f76–78。B 后续另有举臂段约 f94–103，目标延迟未修复。'),
    dict(case='07_real_ary_v', seed=2, title='白衣改蓝 · 种子 2', bounds=[18, 110],
         crop=[440, 0, W, H], overview=[33, 60, 78],
         ranges=[[[54,69]], [[54,69]], [[23,46],[71,86]]],
         note='A 在原时间附近保留目标；B 额外出现 f23–46 的相似手势，伴抬腿的目标延后到 f71–86。'),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(path):
    d=json.loads(subprocess.check_output([FP,'-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=width,height,avg_frame_rate,nb_read_frames,duration','-of','json',str(path)]))['streams'][0]
    return d


def font(size):
    return ImageFont.truetype(FONT,size)


def decode(path,crop):
    x,y,w,h=crop
    raw=subprocess.check_output([FF,'-v','error','-threads','2','-i',str(path),'-filter_threads','1',
        '-vf',f'crop={w}:{h}:{x}:{y}','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','-'])
    stride=w*h*3
    assert len(raw)==141*stride,(path,len(raw))
    return [Image.frombytes('RGB',(w,h),raw[i*stride:(i+1)*stride]) for i in range(141)]


def row(frames,spec,index):
    im=Image.new('RGB',(W*3,PANEL_H),'white');d=ImageDraw.Draw(im)
    for col,label in enumerate(LABELS):
        x=col*W
        d.rectangle((x,0,x+W-1,4),fill=COLORS[col])
        d.text((x+12,11),label,font=font(24),fill=COLORS[col])
        d.text((x+12,40),f"{spec['title']} · f{index:03d} · {index/24:.3f} 秒",font=font(18),fill='#263448')
        im.paste(frames[col][index],(x,HEADER))
        active=[r for r in spec['ranges'][col] if r[0]<=index<=r[1]]
        extra=spec['case']=='07_real_ary_v' and spec['seed']==2 and col==2 and 23<=index<=46
        tag=('额外相似手势窗口' if extra else '已标注目标动作窗口') if active else '同一时刻 · 动作上下文'
        d.text((x+12,HEADER+H+9),tag,font=font(19),fill=COLORS[col] if active else '#667383')
        d.line((x,0,x,PANEL_H-1),fill='#d4dde5')
    return im


def encode(rows,path,fps):
    p=subprocess.Popen([FF,'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24',
        '-s',f'{W*3}x{PANEL_H}','-r',str(fps),'-i','-','-an','-c:v','libx264',
        '-threads','2','-preset','fast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(path)],stdin=subprocess.PIPE)
    try:
        for im in rows:p.stdin.write(im.tobytes())
        p.stdin.close();code=p.wait()
        assert code==0,(path,code)
    finally:
        if p.poll() is None:p.kill();p.wait()


def main():
    archive=json.loads((SOURCE/'analysis/archive_validation.json').read_text())
    expected={x['output_file']:x['output_sha256'] for x in archive['formal_runs']}
    review=json.loads((SOURCE/'review/manifest.json').read_text())
    sealed_before=sha(SOURCE/'SHA256SUMS')
    manifest={'source_archive':str(SOURCE),'scope':'CPU-only same-time three-column screenshot/video derivatives',
        'sealed_manifest_sha256':sealed_before,'frame_numbering':'zero-based inclusive at24FPS',
        'time_alignment':'same source frame in every column; no retiming per arm',
        'crop_policy':'same fixed native-pixel crop for all columns/frames within each case; full-frame context retained separately',
        'interpolation':False,'audio':'comparison videos are silent','cases':[]}
    for spec in SPECS:
        key=f"{spec['case']}_s{spec['seed']}";folder=DEST/key;folder.mkdir(exist_ok=True)
        paths=[SOURCE/'inputs'/f"{spec['case']}.mp4"]+[SOURCE/'outputs'/f"{spec['case']}_{a}_s{spec['seed']}_00001_.mp4" for a in ['a','b']]
        for p in paths[1:]:assert sha(p)==expected[p.relative_to(SOURCE).as_posix()]
        probes=[probe(p) for p in paths]
        assert all(int(p['nb_read_frames'])==141 and p['avg_frame_rate']=='24/1' for p in probes)
        frames=[decode(p,spec['crop']) for p in paths]
        ids=list(range(spec['bounds'][0],spec['bounds'][1]+1));rows=[row(frames,spec,i) for i in ids]
        normal=folder/'局部三列_正常速度.mp4';slow=folder/'局部三列_四分之一速度.mp4'
        encode(rows,normal,24);encode(rows,slow,6)
        dense=[]
        for start in range(0,len(ids),3):
            part=rows[start:start+3];im=Image.new('RGB',(W*3,PANEL_H*len(part)),'white')
            for j,v in enumerate(part):im.paste(v,(0,j*PANEL_H))
            dst=folder/f'逐帧_{start//3+1:02d}_f{ids[start]:03d}-{ids[min(start+2,len(ids)-1)]:03d}.jpg'
            im.save(dst,quality=97,subsampling=0)
            dense.append({'file':dst.relative_to(DEST).as_posix(),'frames':ids[start:start+3]})
        overview=Image.new('RGB',(W*3,36+PANEL_H*3),'white');d=ImageDraw.Draw(overview)
        d.text((12,6),'关键时刻概览 · 各行不同时间，每行三列为同一时间 · 完整逐帧组另附',font=font(20),fill='#263448')
        for j,i in enumerate(spec['overview']):overview.paste(row(frames,spec,i),(0,36+j*PANEL_H))
        op=folder/'关键时刻三列概览.jpg';overview.save(op,quality=97,subsampling=0)
        context=next(c for c in review['cases'] if c['clip_id']==spec['case'] and c['seed']==spec['seed'])
        context_paths=[]
        for k,name in [('comparison','全画面三列_正常速度.mp4'),('quarter_speed','全画面三列_四分之一速度.mp4')]:
            dst=folder/name;shutil.copy2(context['render'][k],dst);context_paths.append(dst.relative_to(DEST).as_posix())
        vprobes={p.relative_to(DEST).as_posix():probe(p) for p in [normal,slow]}
        assert all(int(p['nb_read_frames'])==len(ids) for p in vprobes.values())
        item={**spec,'key':key,'inputs':[{'path':str(p),'sha256':sha(p),'probe':q}for p,q in zip(paths,probes)],
            'dense_pages':dense,'overview':op.relative_to(DEST).as_posix(),'local_videos':list(vprobes),
            'local_video_probes':vprobes,'full_context_videos':context_paths,'local_frame_count':len(ids)}
        manifest['cases'].append(item);print('DONE',key,len(ids),'frames',len(dense),'pages',flush=True)
    assert sealed_before==sha(SOURCE/'SHA256SUMS')
    (DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    build_html(manifest)
    (DEST/'README.txt').write_text('两个真人案例 · 小动作三列对照\n打开 index.html 查看。四组＝两个案例×两个种子。每组左原片、中A普通提示词、右B明确强调小动作。\n局部图/视频使用固定同坐标裁切，不做主体跟踪或不同列的时间对齐。每行帧号一致。全画面视频保留背景和黑边。0.25倍速仅以6FPS显示原来的帧，无插帧。\n目标窗口沿用封存实验的非盲AI逐帧观察，边界约±2帧，手指拓扑/实际触碰不确定。这里只做可视化，不生成新模型结果。\n概览每行是指定关键帧，不是连续帧；逐帧组覆盖整个窗口每一帧。局部视频连续。精确来源、裁切坐标和帧号见manifest.json。\n')


def build_html(manifest):
    parts=['''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>真人小动作 · 原片/A/B对照</title><style>body{margin:0;background:#f3f6fa;color:#1c3045;font:17px/1.65 system-ui,sans-serif}main{max-width:1280px;margin:auto;padding:28px}h1{font-size:30px}h2{font-size:24px}section{background:#fff;border:1px solid #d8e2ec;border-radius:12px;padding:22px;margin:24px 0}a{color:#1265a8}video,img{width:100%;height:auto;border-radius:4px;background:#fff}small{color:#536679}summary{cursor:pointer;font-weight:600}.pages{display:flex;flex-wrap:wrap;gap:10px;margin:15px 0}.pages a{padding:5px 10px;background:#eff4f9;border-radius:5px}.note{border-left:4px solid #3073ae;padding-left:15px}.toolbar{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0}button{padding:7px 13px;cursor:pointer}nav a{margin-right:15px}</style><main><h1>真人小动作 · 三列逐帧对照</h1><p><b>左：原片　｜　中：A 普通提示词　｜　右：B 明确强调小动作</b></p><p>两个案例、各两个种子。局部放大保留同一时刻；帧号从0开始，以原片24 FPS计时。0.25倍速无插帧、无逐列时间对齐。</p><p class="note">先看局部慢放，再看关键时刻概览；展开逐帧截图可查看窗口内每一帧。全画面视频保留背景变化、黑边和腿部上下文。时间窗沿用已有AI观察，边界约±2帧，未据此保证精确手指或接触。</p><nav>''']
    for c in manifest['cases']:parts.append(f'<a href="#{c["key"]}">{html.escape(c["title"])}</a>')
    parts.append('</nav>')
    for c in manifest['cases']:
        key=c['key'];lo,hi=c['bounds'];slow=c['local_videos'][1]
        parts.append(f'<section id="{key}"><h2>{c["title"]}</h2><p>{c["note"]}</p><small>连续窗口 f{lo}–{hi}，共 {c["local_frame_count"]} 帧；原时间 {lo/24:.3f}–{hi/24:.3f} 秒。下方默认 0.25×，播放器时间为慢放时间，画面标签为原片时间。</small><video id="v_{key}" controls preload="metadata" src="{slow}"></video><div class="toolbar"><a href="{c["local_videos"][0]}">局部正常速度</a><a href="{slow}">局部0.25倍速</a></div><p>关键时刻概览（每行三列同一帧；行与行之间为选取的不同时间）：</p><a href="{c["overview"]}"><img loading="lazy" src="{c["overview"]}" alt="{c["title"]}关键时刻三列截图"></a><details><summary>展开完整连续逐帧截图组 · {len(c["dense_pages"])}页</summary><div class="pages">')
        for p in c['dense_pages']:parts.append(f'<a target="_blank" href="{p["file"]}">f{p["frames"][0]}–{p["frames"][-1]}</a>')
        parts.append('</div>')
        for p in c['dense_pages']:parts.append(f'<a href="{p["file"]}"><img loading="lazy" src="{p["file"]}" alt="连续三列对照 f{p["frames"][0]}至{p["frames"][-1]}"></a>')
        parts.append(f'</details><details><summary>展开全画面连续对照 · 原片全部141帧</summary><p>局部裁切未显示的腿部、背景和构图请在这里核查。</p><video controls preload="none" src="{c["full_context_videos"][1]}"></video><a href="{c["full_context_videos"][0]}">全画面正常速度</a>　<a href="{c["full_context_videos"][1]}">全画面0.25倍速</a></details></section>')
    parts.append('<p><a href="README.txt">阅读说明</a> · <a href="manifest.json">来源、帧号与裁切坐标</a></p></main></html>')
    (DEST/'index.html').write_text(''.join(parts))


if __name__=='__main__':main()
