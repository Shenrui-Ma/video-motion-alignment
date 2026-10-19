"""CPU intake and source/retained-Native/fixed-route presentation, actual passed pairs only."""
import argparse
import base64
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts'))
from r84_contract import read, sha, registry, SOURCES, require
REMOTE = Path(read(ROOT / 'configs/runtime.json')['remote_root'])
INDICES = [0, 29, 58, 88, 117, 146]
LABELS = ['1.参考视频', '2.编辑后视频', '3.编辑＋固定时序引导后视频']
DOWNLOADS = Path('/Users/researcher/Downloads')
HTML = DOWNLOADS / 'H3_FlexiAct_既有成功换人_固定时序引导_20261018.html'


def checked_gate(gate, source):
    required_checks = {'Native_prefix_0_5_equal', 'actual_initial_AV_noise_equal',
        'prompt_equal', 'input_video_equal', 'native_vae_calls_equal', 'qwen_presentation_equal',
        'tokenization_before_vision_expansion_equal', 'conditioning_embedding_equal',
        'token_tags_equal', 'target_latent_shapes_equal', 'packed_layout_equal'}
    require(gate.get('schema') == 'r84-historical-native-paired-runtime-gate-v1' and
            gate.get('source_id') == source and gate.get('passed') is True and
            required_checks <= set(gate.get('checks', {})) and
            all(v is True for v in gate['checks'].values()), 'actual pair gate has not passed')
    require(gate['checks']['Native_prefix_0_5_equal'] is True and
            gate['checks']['actual_initial_AV_noise_equal'] is True, 'actual prefix/noise gate failed')
    case = next(v['case'] for v in registry()[0].values() if v['source_id'] == source)
    for arm in ('native', 'forced'):
        row = gate['runs'][arm]; expected = case['baseline_run'] if arm == 'native' else case['run_id']
        require(row['run_id'] == expected and row['valid_frames'] == 147 and
                row['NFE'] == row['Euler_updates'] == 20 and row['routed_blocks'] == (0 if arm == 'native' else 450),
                'actual pair identity/count differs')
        file = Path(row['video']['file'])
        expected_root = REMOTE if arm == 'forced' else Path(case['baseline_root'])
        require(file.parent == expected_root / 'output' and
                file.name.startswith(expected + '_') and file.suffix == '.mp4',
                'actual video path differs from registered run')
    return case


def checked_media_inputs(gate, case, paths):
    expected = [case['video_sha256']] + [gate['runs'][arm]['video']['sha256'] for arm in ('native', 'forced')]
    require(len(paths) == 3 and all(sha(path) == digest for path, digest in zip(paths, expected)),
            'presentation input bytes differ from verified pair')


def collect(source):
    code = '''from pathlib import Path
import io,json,hashlib,sys,tarfile
r=Path(REMOTE);source=SOURCE;gate_path=r/'analysis/postrun'/source/'PAIR_RUNTIME_GATE.json'
g=json.loads(gate_path.read_text());assert g['passed'] is True and g['source_id']==source
assert g['checks']['Native_prefix_0_5_equal'] and g['checks']['actual_initial_AV_noise_equal'] and all(g['checks'].values())
paths={'PAIR_RUNTIME_GATE.json':gate_path}
for arm in ('native','forced'):
 p=Path(g['runs'][arm]['video']['file']);assert p.is_file() and p.suffix=='.mp4' and p.stat().st_size<200000000
 assert hashlib.sha256(p.read_bytes()).hexdigest()==g['runs'][arm]['video']['sha256'];paths[arm+'.mp4']=p
manifest=[]
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as t:
 for name,p in paths.items():
  manifest.append({'name':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size});t.add(p,arcname=name)
 raw=json.dumps(manifest,indent=2).encode();m=tarfile.TarInfo('MANIFEST.json');m.size=len(raw);t.addfile(m,io.BytesIO(raw))
'''.replace('Path(REMOTE)', 'Path(' + repr(str(REMOTE)) + ')').replace('source=SOURCE', 'source=' + repr(source))
    folder = HERE / 'incoming' / source; folder.mkdir(parents=True, exist_ok=True)
    archive = folder / 'actual_media.tar'
    if not archive.exists():
        temporary = archive.with_suffix('.partial')
        with temporary.open('wb') as out:
            subprocess.run(['ssh', '-S', '/tmp/h3-codex-41-recovery-20261018.sock', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=30', 'H3_SERVER_B', 'python3 -c ' + shlex.quote(code)], stdout=out, check=True, timeout=300)
        temporary.rename(archive)
    with tarfile.open(archive) as t:
        manifest = json.load(t.extractfile('MANIFEST.json'))
        require({x['name'] for x in manifest} == {'PAIR_RUNTIME_GATE.json', 'native.mp4', 'forced.mp4'}, 'download inventory differs')
        for item in manifest:
            raw = t.extractfile(item['name']).read()
            require(len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256'], 'download hash differs')
            target = folder / item['name']
            if target.exists(): require(target.read_bytes() == raw, 'existing actual evidence differs')
            else: target.write_bytes(raw)
    gate = read(folder / 'PAIR_RUNTIME_GATE.json'); checked_gate(gate, source)
    for arm in ('native', 'forced'):
        require(sha(folder / (arm + '.mp4')) == gate['runs'][arm]['video']['sha256'], 'actual media binding differs')
    (folder / 'COLLECTION.json').write_text(json.dumps({'passed': True, 'files': manifest, 'archive_sha256': sha(archive)}, indent=2) + '\n')
    return folder


def properties(path, width=1152, height=768, frames=158):
    command = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames', '-show_frames',
        '-show_entries', 'stream=width,height,avg_frame_rate,nb_read_frames:frame=best_effort_timestamp_time', '-of', 'json', str(path)]
    result = json.loads(subprocess.check_output(command, timeout=90)); s = result['streams'][0]
    require((s['width'], s['height'], int(s['nb_read_frames']), s['avg_frame_rate']) == (width, height, frames, '24/1'), 'media geometry differs')
    pts = [float(f['best_effort_timestamp_time']) for f in result['frames']]
    require(len(pts) == frames and all(abs(t-i/24)<1e-6 for i,t in enumerate(pts)), 'physical media timeline differs')
    return s


def bound(path):
    path = Path(path); return {'file': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}


def render(source):
    from PIL import Image, ImageDraw, ImageFont
    incoming = HERE / 'incoming' / source
    g = read(incoming / 'PAIR_RUNTIME_GATE.json'); c = checked_gate(g, source)
    paths = [ROOT / 'inputs' / c['video'], incoming / 'native.mp4', incoming / 'forced.mp4']
    checked_media_inputs(g, c, paths)
    for path in paths: properties(path)
    output = ROOT / 'showcase' / source; output.mkdir(parents=True, exist_ok=True)
    record_path = output / 'PRESENTATION.json'
    if record_path.exists():
        value = read(record_path)
        require(value['gate']['sha256'] == sha(incoming/'PAIR_RUNTIME_GATE.json'), 'gate changed after presentation')
        for key in ('video','figure','portrait'): require(sha(value[key]['file']) == value[key]['sha256'], 'presentation media changed')
        return value
    font = '/System/Library/Fonts/STHeiti Light.ttc'
    caption = Image.new('RGB', (3456, 88), 'black'); draw = ImageDraw.Draw(caption)
    big = ImageFont.truetype(font, 32); small = ImageFont.truetype(font, 22)
    draw.text((14, 8), '角色替换', fill='white', font=small)
    for col, text in enumerate(LABELS): draw.text((col*1152+(1152-draw.textlength(text,font=big))/2,43),text,font=big,fill='white')
    strip = output/'caption.png'; caption.save(strip)
    video = output/'source_native_forced_full147.mp4'
    command=['ffmpeg','-v','error','-nostdin','-n']
    for path in paths: command += ['-threads','2','-i',str(path)]
    filters=';'.join([f'[{i}:v]trim=end_frame=147,setpts=PTS-STARTPTS,setsar=1[v{i}]' for i in range(3)]+['[v0][v1][v2]hstack=inputs=3:shortest=1[images]','[images][3:v]vstack=inputs=2:shortest=1[out]'])
    command += ['-framerate','24','-loop','1','-i',str(strip),'-filter_complex_threads','2','-filter_complex',filters,'-map','[out]',
        '-frames:v','147','-an','-fps_mode','vfr','-c:v','libx264','-crf','17','-preset','fast','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(video)]
    subprocess.run(command,check=True,timeout=600); properties(video,3456,856,147)
    canvas=Image.new('RGB',(1728,2592),'black'); draw=ImageDraw.Draw(canvas)
    label_font=ImageFont.truetype(font,18); time_font=ImageFont.truetype(font,13)
    for row,index in enumerate(INDICES):
        for col,path in enumerate(paths):
            data=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(path),'-vf',f'select=eq(n\\,{index}),scale=576:384:flags=lanczos','-frames:v','1','-threads','1','-f','image2pipe','-vcodec','png','-'],timeout=60)
            canvas.paste(Image.open(io.BytesIO(data)).convert('RGB'),(col*576,row*432))
            text=LABELS[col]; draw.text((col*576+(576-draw.textlength(text,font=label_font))/2,row*432+405),text,font=label_font,fill='white')
        draw.text((8,row*432+387),f'{index/24:.3f}s',font=time_font,fill='#bbb')
    figure=output/'six_times.png';canvas.save(figure)
    portrait=output/c['portrait'];shutil.copy2(ROOT/'inputs'/c['portrait'],portrait)
    value={'source_id':source,'gate':bound(incoming/'PAIR_RUNTIME_GATE.json'),'inputs':[bound(p) for p in paths],
        'video':bound(video),'figure':bound(figure),'portrait':bound(portrait),'frame_indices':INDICES,'valid_frames':147,'fps':24,
        'column_labels':LABELS,'prompt_version':c['prompt_version'],'baseline_run':c['baseline_run'],'forced_run':c['run_id'],
        'inference_efficiency': {arm: {key:g['runs'][arm][key] for key in
            ('job_wall_seconds','NFE','Euler_updates','routed_blocks')} for arm in ('native','forced')},
        'efficiency_scope':'Job wall time runs from submission to observed completion and includes loading and status polling; service generations differ.',
        'visual_review':'PENDING','comparison':'existing Native versus fixed temporal route; same original frame times'}
    record_path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    dest=DOWNLOADS/('H3_FlexiAct_'+source+'_固定时序引导_完整三栏_20261018.mp4')
    if dest.exists(): require(sha(dest)==sha(video),'Downloads media changed')
    else: shutil.copy2(video,dest)
    return value


def publish():
    blocks=[];expected=[];records=[]
    names={'one_leg__movie_man_9':'单腿平衡 · 特朗普角色替换','fitness__game_man_5':'举臂健身 · 红金铠甲角色替换'}
    for source in SOURCES:
        p=ROOT/'showcase'/source/'PRESENTATION.json'
        if not p.exists(): blocks.append('<section><h2>'+names[source]+'</h2><p>等待配对结果。</p></section>');continue
        r=read(p);video=Path(r['video']['file']);portrait=Path(r['portrait']['file']);figure=Path(r['figure']['file'])
        for key in ('video','figure','portrait'):require(sha(r[key]['file'])==r[key]['sha256'],'published asset changed')
        expected.append(video);records.append(r)
        mime='image/webp' if portrait.suffix=='.webp' else 'image/jpeg'
        uri=lambda path,kind:'data:'+kind+';base64,'+base64.b64encode(path.read_bytes()).decode()
        blocks.append('<section><h2>'+names[source]+'</h2><img class="portrait" alt="目标人物参考图" src="'+uri(portrait,mime)+'"><p>目标人物参考图。三栏依次为参考视频、普通编辑、固定时序引导。</p><video controls preload="metadata" src="'+uri(video,'video/mp4')+'"></video><details><summary>六个固定时刻</summary><img class="figure" alt="相同物理时刻对比" src="'+uri(figure,'image/png')+'"></details></section>')
    require(records,'no actual pair to publish')
    doc='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FlexiAct 固定时序引导</title><style>body{background:#101114;color:#eee;margin:24px;font:18px/1.6 system-ui}main{max-width:1900px;margin:auto}section{margin:40px 0;padding-top:20px;border-top:1px solid #444}video,.figure{width:100%;display:block;background:#000}.portrait{width:280px;max-height:240px;object-fit:contain}p{color:#ccc}summary{cursor:pointer}</style><main><h1>FlexiAct · 已完成换人的固定时序引导对照</h1><p>人物外观和场景以目标图为参考，动作取自源视频。普通编辑保留原来的提示词、素材和噪声；新生成在第6至14步加入固定时序路由。每组展示完整147个有效帧，时长6.125秒。</p>'+''.join(blocks)+'</main></html>'
    HTML.write_text(doc)
    embedded=re.findall(r'data:video/mp4;base64,([^\"]+)',doc);require(len(embedded)==len(expected),'video count differs')
    for blob,path in zip(embedded,expected):require(base64.b64decode(blob,validate=True)==path.read_bytes(),'embedded video differs')
    receipt={'html':bound(HTML),'completed_pairs':len(records),'fixed_sources':list(SOURCES),'all_embedded_video_bytes_verified':True}
    (HERE/'DELIVERY.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['collect','render','publish']);p.add_argument('--source',choices=SOURCES)
    a=p.parse_args();require(a.action=='publish' or a.source is not None,'source required')
    result=collect(a.source) if a.action=='collect' else render(a.source) if a.action=='render' else publish()
    print(json.dumps(result,default=str,ensure_ascii=False))
