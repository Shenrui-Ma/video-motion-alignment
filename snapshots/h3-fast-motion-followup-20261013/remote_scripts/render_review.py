#!/usr/bin/env python3
"""CPU-only derivative review renderer. Never writes into inputs/ or outputs/."""
from __future__ import annotations
import argparse, hashlib, html, json, math, os, re, shutil, subprocess, tempfile, time
from fractions import Fraction
from pathlib import Path
from urllib.parse import quote
from PIL import Image, ImageDraw, ImageFont

FF = shutil.which('ffmpeg') or '/opt/homebrew/bin/ffmpeg'
FP = shutil.which('ffprobe') or '/opt/homebrew/bin/ffprobe'
FONT_PATH = '/System/Library/Fonts/Helvetica.ttc'
VERSION = 1

def font(size):
    return ImageFont.truetype(FONT_PATH, size) if Path(FONT_PATH).exists() else ImageFont.load_default()

def probe(path):
    data = json.loads(subprocess.check_output([FP, '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_streams', '-show_format', '-of', 'json', str(path)]))
    s = data['streams'][0]
    return {'frames': int(s.get('nb_read_frames') or s['nb_frames']), 'fps': float(Fraction(s['avg_frame_rate'])), 'fps_rational': s['avg_frame_rate'], 'width': s['width'], 'height': s['height'], 'duration': float(s.get('duration', data['format']['duration']))}

def fingerprint(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()

def rel(path, base): return quote(os.path.relpath(path, base), safe='/')
def safe(name): return re.sub(r'[^A-Za-z0-9_.-]', '_', name)

def decode(path, width=328, height=184):
    raw = subprocess.check_output([FF, '-v', 'error', '-i', str(path), '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2', '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    n = width*height*3
    if len(raw) % n: raise RuntimeError(f'Incomplete decoded frame: {path}')
    return [Image.frombytes('RGB', (width,height), raw[i:i+n]) for i in range(0,len(raw),n)]

def event_bounds(meta):
    ranges = [v for k,v in meta.get('event', {}).items() if k.endswith('_frames_inclusive') and isinstance(v,list) and len(v)==2]
    return [max(0, min(v[0] for v in ranges)-6), min(meta.get('output_frames',107)-1, max(v[1] for v in ranges)+6)] if ranges else [0,106]

def sheets(frames, folder, title, fps):
    folder.mkdir(parents=True,exist_ok=True)
    paths=[]
    for p in range(math.ceil(len(frames)/30)):
        part=frames[p*30:(p+1)*30]
        im=Image.new('RGB',(1680,48+212*math.ceil(len(part)/5)), 'white'); d=ImageDraw.Draw(im)
        d.text((8,8),f'{title} | all decoded frames | page {p+1}',font=font(20),fill='black')
        for j,fr in enumerate(part):
            idx=p*30+j;x=(j%5)*336;y=48+(j//5)*212
            im.paste(fr,(x,y));d.text((x+3,y+186),f'frame {idx:03d} | {idx/fps:.3f}s',font=font(18),fill='black')
        dst=folder/f'frames_p{p+1}.jpg';im.save(dst,quality=92);paths.append(dst)
    return paths

def make_asset(path, out, label, cache):
    key=safe(label); dst=out/'assets'/key; sig=fingerprint(path)
    old=cache.get(key)
    if old and old.get('sha256')==sig and old.get('renderer_version')==VERSION and all((out/p).exists() for p in old['sheets']): return old
    info=probe(path); frames=decode(path)
    if len(frames)!=info['frames']: raise RuntimeError(f'Decoder/count disagreement for {path}')
    imgs=sheets(frames,dst,label,info['fps'])
    item={'path':str(path),'sha256':sig,'renderer_version':VERSION,'probe':info,'sheets':[str(p.relative_to(out)) for p in imgs]}
    cache[key]=item;return item

def render_compare(paths, labels, dest, bounds, test_label=''):
    infos=[probe(p) for p in paths]
    if any(abs(x['fps']-24)>0.02 for x in infos):
        return {'status':'fps_mismatch','warning':'Comparison not rendered: original frame rates differ from 24 FPS. Original files and full frame sheets remain available.','probes':infos}
    frames=[decode(p,656,368) for p in paths]
    counts=[len(x) for x in frames]; count=max(counts)
    dest.parent.mkdir(parents=True,exist_ok=True)
    tmp=dest.with_name(dest.stem+'.partial.mp4')
    cmd=[FF,'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1968x416','-r','24','-i','-','-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(tmp)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    event_dir=dest.parent/(dest.stem+'_event');event_dir.mkdir(exist_ok=True)
    event_pages=[]; event_rows=[]
    def flush_event():
        if not event_rows:return
        page=Image.new('RGB',(1968,len(event_rows)*416),'white')
        for j,row in enumerate(event_rows):page.paste(row,(0,j*416))
        q=event_dir/f'event_p{len(event_pages)+1}.jpg';page.save(q,quality=93);event_pages.append(q);event_rows.clear()
    try:
        for idx in range(count):
            im=Image.new('RGB',(1968,416),'black');d=ImageDraw.Draw(im)
            for col,(seq,label) in enumerate(zip(frames,labels)):
                x=col*656
                if idx<len(seq): im.paste(seq[idx],(x,48))
                else:d.text((x+30,195),'NO FRAME - ORIGINAL ENDED',font=font(24),fill='#ffcc44')
                d.text((x+10,5),f'{label} | frame {idx:03d} | {idx/24:.3f}s',font=font(20),fill='white')
                if test_label:d.text((x+10,27),test_label,font=font(14),fill='#ffcc44')
                elif bounds[0]<=idx<=bounds[1]:d.text((x+10,27),'EVENT REVIEW WINDOW (includes margins)',font=font(14),fill='#ffcc44')
            proc.stdin.write(im.tobytes())
            if bounds[0]<=idx<=bounds[1]:
                event_rows.append(im)
                if len(event_rows)==4:flush_event()
        flush_event();proc.stdin.close();code=proc.wait()
        if code:raise RuntimeError(f'ffmpeg returned {code}')
        tmp.replace(dest)
    except BaseException:
        if proc.poll() is None:proc.kill();proc.wait()
        raise
    slow=dest.with_name(dest.stem+'_quarter_speed.mp4')
    stmp=slow.with_name(slow.stem+'.partial.mp4')
    subprocess.run([FF,'-v','error','-y','-i',str(dest),'-an','-vf','setpts=4*(PTS-STARTPTS)','-r','6','-fps_mode','cfr','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(stmp)],check=True)
    stmp.replace(slow)
    vp,sp=probe(dest),probe(slow)
    if vp['frames']!=count or sp['frames']!=count:raise RuntimeError('Derivative video changed frame count')
    if abs(sp['fps']-6)>0.0001:raise RuntimeError('Quarter-speed video is not 6 FPS')
    return {'status':'ready','comparison':str(dest),'quarter_speed':str(slow),'event_sheets':[str(p) for p in event_pages],'original_frame_counts':counts,'comparison_frames':count,'warning':('FRAME COUNT MISMATCH: missing frames shown as black labeled panels; no trimming or frozen-frame concealment.' if len(set(counts))>1 or count!=107 else ''),'probe':vp,'quarter_speed_probe':sp,'slow_motion_method':'setpts=4*PTS, 6 FPS, same frame count; no optical flow or generated intermediate frames'}

STYLE='''body{font:16px system-ui,sans-serif;max-width:1500px;margin:auto;padding:24px;background:#f4f5f7;color:#182330}h1{font-size:27px}h2{font-size:22px}section{background:white;margin:22px 0;padding:20px;border-radius:10px;border:1px solid #dde1e6}video{max-width:100%;background:#000}button,a{margin-right:12px}button{padding:7px 12px}table{border-collapse:collapse;width:100%}td,th{padding:9px;text-align:left;border-bottom:1px solid #ddd}.warn{background:#fff1ce;padding:12px;white-space:pre-wrap}.pending{color:#9b6600}.panels{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.panels figure{margin:0}details{margin-top:10px}summary{cursor:pointer}small{color:#56616b}pre{white-space:pre-wrap;word-break:break-word}.frame-label{font-variant-numeric:tabular-nums}img{max-width:100%}.test{background:#c70022;color:white;padding:14px}'''
JS='''function vids(id){return [...document.getElementById(id).querySelectorAll('video.sync')]}function pause(id){vids(id).forEach(v=>v.pause())}function rate(id,r){vids(id).forEach(v=>v.playbackRate=r)}function play(id){let vs=vids(id),t=vs[0]?.currentTime||0;vs.forEach(v=>{v.currentTime=Math.min(t,Math.max(0,v.duration-0.001));v.play().catch(()=>{})})}function step(id,n){pause(id);let vs=vids(id),f=Math.round((vs[0]?.currentTime||0)*24)+n;f=Math.max(0,f);vs.forEach(v=>{v.currentTime=Math.min((f+0.001)/24,Math.max(0,v.duration-0.001))});let label=document.querySelector('#'+id+' .frame-label');if(label)label.textContent='Requested source frame '+f+' | '+(f/24).toFixed(3)+'s'}function seekFrame(id,f){pause(id);vids(id).forEach(v=>v.currentTime=Math.min((f+0.001)/24,Math.max(0,v.duration-0.001)))}document.querySelectorAll('video.sync').forEach(v=>v.addEventListener('timeupdate',()=>{let s=v.closest('section'),vs=vids(s.id);if(v!==vs[0])return;let label=s.querySelector('.frame-label');if(label)label.textContent='Source frame ≈ '+Math.floor(v.currentTime*24)+' | '+v.currentTime.toFixed(3)+'s';if(!v.paused)vs.slice(1).forEach(o=>{if(Math.abs(o.currentTime-v.currentTime)>0.09&&v.currentTime<o.duration)o.currentTime=v.currentTime})}));'''

def build(root,out,test_label=''):
    out.mkdir(parents=True,exist_ok=True)
    cache_file=out/'asset_cache.json';cache=json.loads(cache_file.read_text()) if cache_file.exists() else {}
    metas=[]
    for p in sorted((root/'inputs').glob('0*.json')):
        d=json.loads(p.read_text())
        if 'clip_id' in d and 'event' in d:metas.append(d)
    output_files=sorted((root/'outputs').rglob('*.mp4')) if (root/'outputs').exists() else []
    benchmark=[p for p in output_files if 'benchmark' in p.name.lower()];output_files=[p for p in output_files if p not in benchmark]
    used=set();cases=[];errors=[];parts=[f'<!doctype html><html lang="zh"><meta charset="utf-8"><title>H3 快速大动作追加实验复核</title><style>{STYLE}</style><h1>H3 快速大动作追加实验 · 结果复核</h1>']
    if test_label:parts.append(f'<p class="test">{html.escape(test_label)} — fixture source copies only; not model results.</p>')
    parts.append('<p>原始输入／输出不改写。本页只产生复核用派生文件；不自动给事件保真或编辑质量打分。所有帧号从 0 开始，正常时间基准 24 FPS。A = 正常外观编辑；B = A + 明确保留事件。</p><p>三栏原片提供同步播放、0.25×／1×和逐帧按钮；浏览器拖动存在解码精度限制，精确逐帧核查请看带编号图。比较 MP4 无音频；原始输出链接保留原文件。</p>')
    for meta in metas:
        clip=meta['clip_id'];source=root/'inputs'/f'{clip}.mp4';bounds=event_bounds(meta)
        try:source_asset=make_asset(source,out,clip+'_source',cache)
        except Exception as e:errors.append({'path':str(source),'error':str(e)});continue
        for seed in (1,2):
            key=f'{clip}_s{seed}';matches={}
            for cond in ('a','b'):
                pattern=re.compile(r'^'+re.escape(clip)+r'_'+cond+r'_s'+str(seed)+r'(?:_\d+_?)?\.mp4$')
                matches[cond]=[p for p in output_files if pattern.match(p.name)]
                used.update(matches[cond])
            record={'clip_id':clip,'seed':seed,'event':meta['event'],'event_review_bounds_inclusive':bounds,'source':source_asset,'matches':{k:[str(p) for p in v] for k,v in matches.items()},'status':'pending','assets':{}}
            parts.append(f'<section id="{key}"><h2>{html.escape(clip)} · seed {seed}</h2><p>{html.escape(meta["event"]["label"])}</p><small>{html.escape(meta["event"].get("type",""))} | review frames {bounds[0]}–{bounds[1]} (margins included)</small>')
            warnings=[]
            for cond in ('a','b'):
                if len(matches[cond])>1:warnings.append(f'{cond.upper()}: multiple outputs matched; newest by modification time shown; all preserved.')
                if matches[cond]:
                    p=max(matches[cond],key=lambda p:p.stat().st_mtime_ns)
                    try:record['assets'][cond]=make_asset(p,out,p.stem,cache)
                    except Exception as e:errors.append({'path':str(p),'error':str(e)});warnings.append(f'{cond.upper()}: not readable / may be incomplete: {e}')
            parts.append('<div class="panels">')
            for label,asset in [('SOURCE',source_asset),('A',record['assets'].get('a')),('B',record['assets'].get('b'))]:
                if asset:
                    p=Path(asset['path']);pr=asset['probe'];url=rel(p,out)
                    parts.append(f'<figure><figcaption><b>{label}</b> · {pr["frames"]} frames · {pr["fps"]:.4g} FPS</figcaption><video class="sync" muted controls preload="metadata" src="{url}"></video><a href="{url}">原始文件</a><details><summary>全部逐帧图</summary>'+''.join(f'<a target="_blank" href="{quote(x)}">第 {i+1} 页</a>' for i,x in enumerate(asset['sheets']))+'</details></figure>')
                    if pr['frames']!=107 or abs(pr['fps']-24)>0.02:warnings.append(f'{label}: expected 107 frames / 24 FPS, actual {pr["frames"]} / {pr["fps"]}.')
                else:parts.append(f'<figure><figcaption><b>{label}</b></figcaption><p class="pending">PENDING — 尚无可读正式结果</p></figure>')
            parts.append(f'</div><p><button onclick="play(\'{key}\')">同步播放</button><button onclick="pause(\'{key}\')">暂停</button><button onclick="rate(\'{key}\',0.25)">0.25×</button><button onclick="rate(\'{key}\',1)">1×</button><button onclick="step(\'{key}\',-1)">前一帧</button><button onclick="step(\'{key}\',1)">后一帧</button><button onclick="seekFrame(\'{key}\',{bounds[0]})">事件区间起点</button><span class="frame-label"></span></p>')
            if all(c in record['assets'] for c in ('a','b')):
                paths=[source]+[Path(record['assets'][c]['path']) for c in ('a','b')]
                sig=':'.join([source_asset['sha256']]+[record['assets'][c]['sha256'] for c in ('a','b')])+f':{VERSION}:{bounds}'
                ledger=out/'derived'/f'{key}.json';old=json.loads(ledger.read_text()) if ledger.exists() else {}
                result=old.get('render') if old.get('signature')==sig and old.get('render',{}).get('status')=='ready' and Path(old['render']['comparison']).exists() and Path(old['render']['quarter_speed']).exists() else None
                try:
                    if result is None:
                        result=render_compare(paths,['SOURCE','A: appearance edit','B: explicit event'],out/'derived'/f'{key}_source_A_B.mp4',bounds,test_label)
                        ledger.parent.mkdir(exist_ok=True);ledger.write_text(json.dumps({'signature':sig,'render':result},indent=2))
                    record['render']=result;record['status']=result['status']
                    if result.get('warning'):warnings.append(result['warning'])
                    if result['status']=='ready':
                        parts.append(f'<p>派生比较：<a href="{rel(Path(result["comparison"]),out)}">24 FPS 同步横排</a><a href="{rel(Path(result["quarter_speed"]),out)}">1/4 速版（同样帧数，6 FPS）</a></p><details><summary>事件窗口密集对比（每一帧，无稀疏抽样）</summary>'+''.join(f'<a target="_blank" href="{rel(Path(p),out)}">第 {i+1} 页</a>' for i,p in enumerate(result['event_sheets']))+'</details>')
                except Exception as e:record['status']='render_error';warnings.append(str(e));errors.append({'case':key,'error':str(e)})
            if warnings:parts.append('<p class="warn">'+html.escape('\n'.join(warnings))+'</p>')
            parts.append('<details><summary>事件人工预标注／限制与提示词</summary><pre>'+html.escape(json.dumps({'event':meta['event'],'qa':meta.get('qa',{}),'prompts':meta.get('prompts',{})},ensure_ascii=False,indent=2))+'</pre></details></section>')
            record['warnings']=warnings;cases.append(record)
            print(key,record['status'],flush=True)
    extras=[p for p in output_files if p not in used]
    parts.append('<section><h2>其他输出／自适应对照／编码诊断</h2><p>下列未按 A/B 主实验归组，单独保留；不混入主对照。</p>')
    for p in extras:
        try:
            asset=make_asset(p,out,p.stem,cache)
            parts.append(f'<details><summary>{html.escape(p.name)} · {asset["probe"]["frames"]} frames</summary><video controls preload="none" src="{rel(p,out)}"></video><p><a href="{rel(p,out)}">原始文件</a>'+''.join(f'<a href="{quote(x)}">逐帧图 {i+1}</a>' for i,x in enumerate(asset['sheets']))+'</p></details>')
        except Exception as e:errors.append({'path':str(p),'error':str(e)})
    parts.append(f'<p>排除 benchmark 文件 {len(benchmark)} 个。</p></section><script>{JS}</script></html>')
    (out/'index.html').write_text('\n'.join(parts),encoding='utf-8')
    cache_file.write_text(json.dumps(cache,indent=2))
    report={'renderer_version':VERSION,'created_local_time':time.strftime('%Y-%m-%d %H:%M:%S %z'),'root':str(root),'test_label':test_label,'cases':cases,'additional_outputs':[str(p) for p in extras],'excluded_benchmarks':[str(p) for p in benchmark],'errors':errors,'rating_policy':'No automatic scores or inferred model success; human review required.'}
    (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));return report

def self_test(root,out):
    with tempfile.TemporaryDirectory(prefix='SYNTHETIC_RENDER_TEST_') as td:
        test=Path(td);(test/'inputs').mkdir();(test/'outputs').mkdir()
        metas=[json.loads(p.read_text()) for p in sorted((root/'inputs').glob('0*.json')) if 'clip_id' in json.loads(p.read_text())]
        for i,m in enumerate(metas):
            name=m['clip_id'];src=root/'inputs'/f'{name}.mp4'
            shutil.copy2(src,test/'inputs'/src.name);(test/'inputs'/f'{name}.json').write_text(json.dumps(m))
            for c in ('a','b'):
                dst=test/'outputs'/f'{name}_{c}_s1_00001_.mp4'
                if i==2 and c=='b':subprocess.run([FF,'-v','error','-y','-i',str(src),'-frames:v','83','-an','-c:v','libx264','-crf','20',str(dst)],check=True)
                else:shutil.copy2(src,dst)
        shutil.copy2(test/'inputs'/f'{metas[0]["clip_id"]}.mp4',test/'outputs'/'excluded_benchmark2.mp4')
        a=build(test,test/'review','SYNTHETIC TEST COPY — NO MODEL INFERENCE')
        ready=[c for c in a['cases'] if c['status']=='ready'];assert len(ready)==3
        assert len(a['excluded_benchmarks'])==1
        assert len([c for c in a['cases'] if c['status']=='pending'])==3
        for c in ready:assert c['render']['probe']['frames']==107 and c['render']['quarter_speed_probe']['frames']==107
        assert any('MISMATCH' in c['render'].get('warning','') for c in ready)
        first=Path(ready[0]['render']['comparison']);stamp=first.stat().st_mtime_ns
        b=build(test,test/'review','SYNTHETIC TEST COPY — NO MODEL INFERENCE');assert first.stat().st_mtime_ns==stamp
        result={'status':'passed','test_kind':'Renderer-only; 3 real source clips copied as artificial A/B fixtures, not model outputs','checks':['3 source/A/B derived comparisons produced','6 expected cases: 3 ready, 3 pending','benchmark excluded','83-frame B mismatch explicitly flagged; comparison retains 107 frames with missing panels','quarter-speed videos retain exactly 107 frames at 6 FPS','repeat render reuses comparison artifact','temporary fixtures deleted after test'],'errors':a['errors']}
    out.mkdir(exist_ok=True,parents=True);(out/'render_tool_test_report.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--review-dir',type=Path);ap.add_argument('--self-test',action='store_true');args=ap.parse_args()
    root=args.root.resolve();out=(args.review_dir or root/'review').resolve()
    if out==root/'outputs' or root/'outputs' in out.parents:raise SystemExit('Refusing to write derivatives into original outputs/')
    if args.self_test:self_test(root,out)
    else:build(root,out)
if __name__=='__main__':main()
