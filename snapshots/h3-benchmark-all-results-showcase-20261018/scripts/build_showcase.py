#!/usr/bin/env python3
"""Build a portable, evidence-bound H3 results page from independently curated inventories."""
import argparse, base64, hashlib, html, json, math, mimetypes, os, re, shutil, subprocess, tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEDIA_FIELDS = ('reference_image_path','reference_video_path','ordinary_video_path','guided_video_path','alternative_video_path','comparison_video_path')
VIDEO_FIELDS = MEDIA_FIELDS[1:]
CAPTIONS = ['参考视频','普通编辑','时序引导']
STATUS_LABELS = {'local_improvement_candidate':'局部改善候选','zero_intervention':'实际零触发','task_failure':'任务失败','neutral':'无明显增益','prompt_control':'提示词诊断','native_only_guidance_pending':'普通编辑已完成','pending_review':'待人工复核'}
def status_label(value):
    value=str(value or '')
    return STATUS_LABELS.get(value, value if re.search('[\u4e00-\u9fff]',value) else '待人工复核')
def activation(item):
    if item.get('comparison_kind') in ('prompt_control','sampler_control','positional_control','native_only'): return 'not_applicable'
    value=item.get('guidance_activation')
    if value in ('active','zero','not_applicable'): return value
    if item.get('actual_routed_blocks') is not None:
        return 'active' if item['actual_routed_blocks']>0 else 'zero'
    return 'unknown'

def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''): h.update(part)
    return h.hexdigest()

def esc(value): return html.escape(str(value or ''), quote=True)

def render_motion_fidelity(out, item):
    if item.get('comparison_kind') == 'reference_origin_control':
        metric = (item.get('quantitative_metrics') or {}).get('motion_fidelity', {})
        values = [metric.get(k) for k in ('native', 'reference_origin')]
        if any(v is not None and (type(v) not in (int, float) or not math.isfinite(v)) for v in values):
            raise ValueError('Invalid reference-origin-control MF: '+item['id'])
        out.write('<div class="metric-block"><p>参考分支相位对照 · IVEBench Motion Fidelity</p><table><thead><tr><th>普通编辑</th><th>参考分支相位引导</th></tr></thead><tbody><tr>')
        for value in values:
            out.write('<td>'+('待计算' if value is None else f'{value:.6f}')+'</td>')
        out.write('</tr></tbody></table></div>')
        return
    if item.get('comparison_kind') == 'positional_control':
        metric = (item.get('quantitative_metrics') or {}).get('motion_fidelity', {})
        values = [metric.get(k) for k in ('native', 'aligned')]
        if any(v is not None and (type(v) not in (int, float) or not math.isfinite(v)) for v in values):
            raise ValueError('Invalid positional-control MF: '+item['id'])
        out.write('<div class="metric-block"><p>RoPE 时间坐标对照 · IVEBench Motion Fidelity</p><table><thead><tr><th>普通编辑</th><th>RoPE 时间坐标对齐</th></tr></thead><tbody><tr>')
        for value in values:
            out.write('<td>'+('待计算' if value is None else f'{value:.6f}')+'</td>')
        out.write('</tr></tbody></table></div>')
        return
    if item.get('comparison_kind') == 'sampler_control':
        metric = (item.get('quantitative_metrics') or {}).get('motion_fidelity', {})
        values = [metric.get(k) for k in ('euler', 'res_multistep')]
        if any(v is not None and (type(v) not in (int, float) or not math.isfinite(v)) for v in values):
            raise ValueError('Invalid sampler-control MF: '+item['id'])
        out.write('<div class="metric-block"><p>采样器对照 · IVEBench Motion Fidelity</p><table><thead><tr><th>Euler 普通编辑</th><th>res_multistep 普通编辑</th></tr></thead><tbody><tr>')
        for value in values:
            out.write('<td>'+('待计算' if value is None else f'{value:.6f}')+'</td>')
        out.write('</tr></tbody></table><p class="metric-note">'+esc(metric.get('scope') or '两版均为普通编辑，比较采样器对结果的影响。')+'</p></div>')
        return
    if item.get('comparison_kind') == 'prompt_control':
        repair = (item.get('quantitative_metrics') or {}).get('task_repair_motion_fidelity')
        if repair:
            values = [repair.get(k) for k in ('old_native', 'new_native')]
            if any(v is not None and (type(v) not in (int, float) or not math.isfinite(v)) for v in values):
                raise ValueError('Invalid task-repair MF: '+item['id'])
            out.write('<div class="metric-block"><p>普通编辑修复 · 官方 Motion Fidelity</p><table><thead><tr><th>旧普通编辑</th><th>新版普通编辑</th></tr></thead><tbody><tr>')
            for value in values:
                out.write('<td>'+('待计算' if value is None else f'{value:.6f}')+'</td>')
            out.write('</tr></tbody></table><p class="metric-note">'+esc(repair.get('scope'))+'</p></div>')
            return
        out.write('<p class="metric-note">提示词对照的 Motion Fidelity：待补充数值评测。</p>')
        return
    metric = (item.get('quantitative_metrics') or {}).get('motion_fidelity')
    if not metric:
        out.write('<p class="metric-note">Motion Fidelity：待补充数值评测。</p>')
        return
    values = {}
    for name in ('native', 'guided', 'delta'):
        value = metric.get(name)
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
            raise ValueError(f'Invalid Motion Fidelity {name}: {item["id"]}')
        values[name] = value
    if values['native'] is not None and values['guided'] is not None:
        delta = values['guided'] - values['native']
        if values['delta'] is not None and not math.isclose(values['delta'], delta, abs_tol=1e-10):
            raise ValueError(f'Motion Fidelity delta mismatch: {item["id"]}')
        values['delta'] = delta
    else:
        if values['delta'] is not None:
            raise ValueError(f'Motion Fidelity delta without paired scores: {item["id"]}')
    def number(name):
        value = values[name]
        if value is None and name == 'guided' and not item.get('guided_video_path'):
            return '未生成引导版'
        if value is None and name == 'delta':
            return '待配对评分'
        return '待计算' if value is None else (f'{value:+.6f}' if name == 'delta' else f'{value:.6f}')
    protocol = ('FlexiAct' if item.get('benchmark', '').lower() == 'flexiact' else 'IVEBench') + ' Motion Fidelity'
    out.write(f'<div class="metric-block"><p>{esc(protocol)} · 越高越好</p><table><thead><tr><th>普通编辑</th><th>时序引导</th><th>变化（引导 − 普通）</th></tr></thead><tbody><tr>')
    for name in ('native', 'guided', 'delta'):
        out.write(f'<td>{number(name)}</td>')
    out.write('</tr></tbody></table>')
    original_fixed = metric.get('original_fixed')
    if original_fixed is not None:
        if type(original_fixed) not in (int, float) or not math.isfinite(original_fixed) or values['guided'] is None:
            raise ValueError('Invalid original fixed-guidance MF: '+item['id'])
        change = values['guided'] - original_fixed
        recorded = metric.get('extended_minus_original_fixed')
        if recorded is not None and not math.isclose(recorded, change, abs_tol=1e-10):
            raise ValueError('Extended versus original fixed MF mismatch: '+item['id'])
        out.write('<p>本条“时序引导”对应延长版。原固定引导与延长版的比较：</p><table><thead><tr><th>固定引导6–14</th><th>延长引导6–19</th><th>变化（延长 − 固定）</th></tr></thead><tbody>')
        out.write(f'<tr><td>{original_fixed:.6f}</td><td>{values["guided"]:.6f}</td><td>{change:+.6f}</td></tr></tbody></table>')
    note = metric.get('scope') or '衡量运动轨迹保持程度。局部动作时差另行评测。'
    if metric.get('valid_frames'):
        note += f' 对应成片的有效区间为 {metric["valid_frames"]} 帧。'
    out.write(f'<p class="metric-note">{esc(note)}</p></div>')

def render_event_timing(out, item):
    timing = (item.get('quantitative_metrics') or {}).get('event_timing')
    if not timing:
        return
    fps = timing['fps']
    if not isinstance(fps, (int, float)) or not math.isfinite(fps) or fps <= 0:
        raise ValueError('Invalid event timestamp rate')
    measurement = timing.get('measurement') or '视觉事件区间标注'
    sampler = item.get('comparison_kind') == 'sampler_control'
    keys = ('source_frames', 'euler_frames', 'res_multistep_frames') if sampler else ('source_frames', 'native_frames', 'guided_frames')
    labels = ('Euler 普通编辑', 'res_multistep 普通编辑') if sampler else ('普通编辑', '时序引导')
    if item.get('comparison_kind') == 'reference_origin_control':
        keys = ('source_frames', 'native_frames', 'reference_origin_frames')
        labels = ('普通编辑', '参考分支相位引导')
    out.write('<div class="metric-block"><p>局部动作延后范围（秒）· '+esc(measurement)+'</p><table><thead><tr><th>动作</th>'+''.join('<th>'+esc(label)+'</th>' for label in labels)+'</tr></thead><tbody>')
    for event in timing['events']:
        if sampler and event.get('arrival_time') and 'source_frames' not in event:
            visible = [event[k] for k in ('source_visible_frames','euler_visible_frames','res_multistep_visible_frames')]
            if any(len(v)!=2 or not 0 <= v[0] <= v[1] < item['valid_frames'] for v in visible):
                raise ValueError('Invalid final visible frame bounds: '+item['id'])
            out.write('<tr><td>'+esc(event['name'])+'</td>')
            for frames in visible[1:]:
                out.write('<td>第 '+esc(str(frames[0])+'–'+str(frames[1]))+' 帧可见；到达时刻未定</td>')
            out.write('</tr>')
            continue
        intervals = [event[k] for k in keys]
        if any(len(v) != 2 or any(type(i) is not int for i in v) or not 0 <= v[0] <= v[1] < item['valid_frames'] for v in intervals):
            raise ValueError(f'Invalid event frame bounds: {item["id"]}')
        source, native, guided = intervals
        out.write('<tr><td>'+esc(event['name'])+'</td>')
        for edited in (native, guided):
            lo, hi = (edited[0] - source[1])/fps, (edited[1] - source[0])/fps
            out.write(f'<td>{lo:.3f}–{hi:.3f}</td>')
        out.write('</tr>')
    out.write('</tbody></table><p class="metric-note">0 秒表示同步；正值表示延后，负值表示提前。'+esc(timing.get('scope'))+'</p></div>')

def load_inventory(path):
    data = json.loads(path.read_text())
    items = data if isinstance(data, list) else data.get('items')
    if not isinstance(items, list): raise ValueError(f'Inventory must contain items: {path}')
    return items

def render_repair_index(out, items, path):
    if not path.exists():
        return
    aliases = {}
    for item in items:
        aliases[item['id']] = item['id']
        for previous in item.get('also_listed_as', []):
            aliases[previous['id']] = item['id']
    rows = json.loads(path.read_text())['items']
    out.write('<section class="repair-index"><h2>本轮重做与补齐</h2><p class="intro">这里列出指定任务的最新进度。点击“查看当前视频”可直接展开对应版本。</p><table><thead><tr><th>任务</th><th>当前版本与进度</th><th>视频</th></tr></thead><tbody>')
    for row in rows:
        item_id = row.get('latest_item_id')
        if item_id and item_id not in aliases:
            raise ValueError('Repair index points to an absent result: '+item_id)
        link = ('<a data-reveal="case_'+esc(aliases[item_id])+'" href="#case_'+esc(aliases[item_id])+'">查看当前视频</a>') if item_id else '等待成片'
        out.write('<tr><td>'+esc(row['task'])+'</td><td>'+esc(row['status'])+'</td><td>'+link+'</td></tr>')
    out.write('</tbody></table></section>')

def classify(item):
    if item.get('comparison_kind') == 'reference_origin_control':
        return 'reference_origin' if all(item.get(k) for k in ('ordinary_video_path','guided_video_path','comparison_video_path')) else 'pending'
    if item.get('comparison_kind') == 'positional_control':
        if item.get('guided_video_path'):
            raise ValueError('Positional control contains a guided output: '+item.get('id',''))
        return 'positional' if all(item.get(k) for k in ('ordinary_video_path','alternative_video_path','comparison_video_path')) else 'pending'
    if item.get('comparison_kind') == 'sampler_control':
        if item.get('guided_video_path'):
            raise ValueError('Sampler control contains a guided output: '+item.get('id',''))
        return 'sampler' if all(item.get(k) for k in ('ordinary_video_path','alternative_video_path','comparison_video_path')) else 'pending'
    if item.get('guided_video_path') and item.get('ordinary_video_path'):
        return 'guided' if item.get('comparison_video_path') else 'pending'
    if item.get('alternative_video_path') and not item.get('guided_video_path'):
        return 'prompt' if item.get('comparison_video_path') else 'pending'
    return 'pending'

def validate_item(item, cache):
    for name in ('id','benchmark','source_id','title','task'):
        if not item.get(name): raise ValueError(f'Missing {name}: {item.get("id")}')
    if item['benchmark'].lower() not in ('flexiact','ivebench'):
        raise ValueError(f'Unknown benchmark {item["benchmark"]}')
    item = dict(item)
    item['media'] = {}
    for field in MEDIA_FIELDS:
        value = item.get(field)
        if not value: continue
        p = Path(value).expanduser()
        if not p.is_absolute() or not p.is_file(): raise ValueError(f'Missing real media: {field} {p}')
        if not p.stat().st_size: raise ValueError(f'Empty media: {p}')
        key = str(p.resolve())
        if key not in cache:
            cache[key] = {'path':key,'sha256':sha256(p),'bytes':p.stat().st_size,'mime':mimetypes.guess_type(p.name)[0] or ('image/png' if field == 'reference_image_path' else 'video/mp4')}
        item['media'][field] = dict(cache[key])
        expected=(item.get('media_sha256') or {}).get(field)
        if expected and expected != cache[key]['sha256']: raise ValueError(f'Inventory media SHA mismatch: {item["id"]} {field}')
    if item.get('reference_image_used') is True and not item.get('reference_image_path'):
        raise ValueError(f'Used reference image missing: {item["id"]}')
    item['section_kind'] = classify(item)
    return item

def deduplicate(items):
    retained, by_key, merged = [], {}, []
    for item in items:
        m = item['media']
        # An actual ordinary/edited output is required for deduplication. Sources alone do not merge pending jobs.
        outs = tuple(m.get(f, {}).get('sha256') for f in ('ordinary_video_path','guided_video_path','alternative_video_path'))
        key = (item['benchmark'].lower(), m.get('reference_video_path', {}).get('sha256'), outs, item.get('comparison_kind'), item.get('method_label'))
        if any(outs) and key in by_key:
            previous = by_key[key]
            previous.setdefault('also_listed_as', []).append({'id':item['id'],'variant':item.get('variant'),'method_label':item.get('method_label'),'review_summary':item.get('review_summary'),'evidence_paths':item.get('evidence_paths',[])})
            merged.append({'duplicate_id':item['id'],'retained_id':previous['id'],'reason':'identical method, reference and actual output SHA256'})
        else:
            retained.append(item)
            if any(outs): by_key[key] = item
    return retained, merged

def poster(media, ffmpeg):
    p = ROOT/'assets'/'posters'/f'{media["sha256"]}.jpg'
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([ffmpeg,'-v','error','-i',media['path'],'-frames:v','1','-vf','scale=min(1600\\,iw):-2','-q:v','3','-y',str(p)],check=True,timeout=90,stdin=subprocess.DEVNULL)
    return p

def pending_valid_media(media, frames, fps, ffmpeg):
    """Prepare only the first valid frames for a standalone pending-case player."""
    folder=ROOT/'assets/valid_video';folder.mkdir(parents=True,exist_ok=True)
    target=folder/f'{media["sha256"]}_{frames}.mp4';receipt=target.with_suffix('.json')
    if target.exists() and receipt.exists():
        result=json.loads(receipt.read_text())
        if result['sha256']==sha256(target) and result['source_sha256']==media['sha256']:return result
    command=[ffmpeg,'-v','error','-i',media['path'],'-map','0:v:0','-vf',f'trim=end_frame={frames},setpts=PTS-STARTPTS','-fps_mode','passthrough','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-threads','2','-an','-movflags','+faststart','-y',str(target)]
    subprocess.run(command,check=True,timeout=180,stdin=subprocess.DEVNULL)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,r_frame_rate,nb_read_frames','-of','json',str(target)]))['streams'][0]
    if int(probe['nb_read_frames'])!=frames or Fraction(probe['r_frame_rate'])!=Fraction(str(fps)):raise ValueError('Pending valid-frame trim verification failed')
    result={'path':str(target),'sha256':sha256(target),'bytes':target.stat().st_size,'mime':'video/mp4','source_path':media['path'],'source_sha256':media['sha256'],'derived_scope':'display-only valid-frame prefix; original research output retained','frame_mapping':f'output i = source i, 0 <= i < {frames}','valid_frames':frames,'fps':fps,'command':command,'probe':probe}
    receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2));return result

def prepare_pending(items, ffmpeg):
    jobs={}
    for item in items:
        if item['section_kind']!='pending':continue
        for field in ('reference_video_path','ordinary_video_path','guided_video_path','alternative_video_path'):
            if field in item['media']:
                media=item['media'][field];key=(media['sha256'],item['valid_frames'],str(item['fps']))
                jobs[key]=(media,item['valid_frames'],item['fps'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={key:pool.submit(pending_valid_media,*args,ffmpeg) for key,args in jobs.items()}
        results={key:f.result() for key,f in futures.items()}
    for item in items:
        if item['section_kind']=='pending':
            item['pending_display_media']={field:results[(media['sha256'],item['valid_frames'],str(item['fps']))] for field,media in item['media'].items() if field in ('reference_video_path','ordinary_video_path','guided_video_path','alternative_video_path')}

def data_uri(path, mime):
    return 'data:'+mime+';base64,'+base64.b64encode(Path(path).read_bytes()).decode('ascii')

CSS = '''
:root{color-scheme:dark;--bg:#0b0d10;--panel:#14181d;--line:#2c333b;--muted:#a8b1bd;--ink:#edf0f4;--accent:#94baff}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}main{max-width:1700px;margin:auto;padding:36px 28px 80px}h1{font-size:clamp(27px,3vw,42px);line-height:1.25;font-weight:660;margin:10px 0 16px;letter-spacing:-.03em}h2{font-size:26px;margin:44px 0 16px}h3{font-size:22px;margin:0 0 8px;line-height:1.4}p{margin:8px 0}.eyebrow{color:var(--accent);font-size:13px;letter-spacing:.12em}.intro{color:var(--muted);max-width:900px}.stats{display:flex;gap:12px;flex-wrap:wrap;margin:22px 0}.stat{border:1px solid var(--line);border-radius:10px;padding:10px 16px;color:var(--muted);font-size:14px}.stat strong{font-size:24px;color:var(--ink);margin-right:8px;font-weight:600}.toolbar{position:sticky;top:0;z-index:5;display:flex;gap:12px;flex-wrap:wrap;background:#0b0deef0;background:rgba(11,13,16,.96);backdrop-filter:blur(12px);padding:14px 0;border-bottom:1px solid var(--line);margin-bottom:22px}.toolbar label{display:flex;gap:8px;align-items:center;color:var(--muted);font-size:14px}select,input{background:var(--panel);border:1px solid #414b58;border-radius:7px;color:var(--ink);font:inherit;padding:8px 11px}input{min-width:260px;flex:1}.card{border:1px solid var(--line);border-radius:14px;background:var(--panel);overflow:hidden;margin:0 0 28px}.card-head{padding:22px 24px 18px;display:flex;align-items:flex-start;gap:24px}.description{flex:1;min-width:0}.tagline{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}.tag{font-size:12px;border:1px solid #3a4552;border-radius:5px;padding:2px 7px;color:#b6c5d8}.task{font-size:16px;max-width:1150px}.review{color:#d1d8e2;margin-top:12px;border-left:2px solid #536d8f;padding-left:12px}.meta{color:var(--muted);font-size:13px;margin-top:11px}.ref{flex:0 0 126px;margin:0;text-align:center}.ref img{max-width:126px;max-height:126px;object-fit:contain;background:#080a0c;border-radius:6px}.ref figcaption{color:var(--muted);font-size:12px;margin-top:4px}.no-ref{color:var(--muted);font-size:13px;margin:8px 0}.player{background:#000}.player video{display:block;width:100%;max-height:78vh;object-fit:contain;background:#000;aspect-ratio:auto}.labels{display:grid;grid-template-columns:repeat(var(--columns,3),1fr);gap:8px;text-align:center;background:#000;color:#e0e5ec;padding:10px 12px 14px;font-size:14px}.player-tools{display:flex;justify-content:space-between;gap:16px;padding:11px 24px;color:var(--muted);font-size:12px;border-top:1px solid var(--line)}button{font:inherit;border:1px solid #45515f;border-radius:6px;padding:5px 11px;background:#202832;color:#e3eaf4;cursor:pointer}button:hover{background:#314157}.tools-buttons{display:flex;gap:8px}.evidence{padding:0 24px 14px;color:var(--muted);font-size:12px}.evidence summary{cursor:pointer}.evidence ul{overflow-wrap:anywhere;padding-left:20px}.group-details{border:1px solid var(--line);padding:16px;border-radius:12px;margin:28px 0}.group-details>summary{cursor:pointer;font-size:20px;font-weight:600;margin-bottom:8px}.group-details[open]>summary{margin-bottom:20px}.empty{padding:50px;color:var(--muted);text-align:center;border:1px dashed var(--line)}.pending-note{padding:14px 24px;border-top:1px solid var(--line);color:#d9be90}.pending-players{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:2px;background:#000}.pending-players .player-tools{padding:10px}.media-title{background:#000;padding:10px 24px;font-size:14px}.footer{color:var(--muted);font-size:12px;margin-top:36px}a{color:var(--accent)}[hidden]{display:none!important}@media(max-width:720px){main{padding:22px 12px 50px}.card-head{padding:16px;gap:12px}.ref{flex-basis:82px}.ref img{max-width:82px;max-height:100px}h3{font-size:19px}.task{font-size:14px}.labels{font-size:11px}.player-tools{padding:10px 14px}.toolbar{position:relative}.toolbar input{min-width:100%;width:100%}.stat{padding:7px 10px}.pending-players{grid-template-columns:1fr}.group-details{padding:8px}}
'''
CSS += '.metric-block{margin:14px 0;padding:12px 16px;border:1px solid #3a4552;border-radius:8px;max-width:820px}.metric-block>p{font-size:14px}.metric-block table{width:100%;border-collapse:collapse;text-align:left;font-variant-numeric:tabular-nums}.metric-block th,.metric-block td{padding:6px 12px 6px 0}.metric-block th{font-size:13px;color:#b6c5d8;font-weight:500}.metric-block td{font-size:17px}.metric-note{color:#a8b1bd;font-size:13px!important}'
CSS += '.repair-index{overflow-x:auto;margin-bottom:24px}.repair-index table{width:100%;border-collapse:collapse;margin-top:14px;text-align:left}.repair-index th,.repair-index td{padding:10px 16px 10px 0;border-bottom:1px solid var(--line)}.repair-index th{color:var(--muted);font-size:14px}.repair-index td:last-child{white-space:nowrap}.card{scroll-margin-top:100px}'
JS = '''
const cards=[...document.querySelectorAll('.card')];
function filterCards(){const bench=document.querySelector('#bench').value,kind=document.querySelector('#kind').value,status=document.querySelector('#status').value,act=document.querySelector('#activation').value,q=document.querySelector('#search').value.toLowerCase().trim();let shown=0;for(const card of cards){const yes=(!bench||card.dataset.benchmark===bench)&&(!kind||card.dataset.kind===kind)&&(!status||card.dataset.status===status)&&(!act||card.dataset.activation===act)&&(!q||card.dataset.search.includes(q));card.hidden=!yes;if(!yes)for(const v of card.querySelectorAll('video'))v.pause();if(yes)shown++;}document.querySelector('#visible-count').textContent=shown;for(const section of document.querySelectorAll('.benchmark-section'))section.hidden=![...section.querySelectorAll('.card')].some(c=>!c.hidden);for(const d of document.querySelectorAll('.group-details')){d.hidden=![...d.querySelectorAll('.card')].some(c=>!c.hidden);if(kind&&d.dataset.kind===kind)d.open=true;}document.querySelector('#no-results').hidden=shown!==0;}
for(const id of ['bench','kind','status','activation','search'])document.querySelector('#'+id).addEventListener(id==='search'?'input':'change',filterCards);
for(const v of document.querySelectorAll('video'))v.addEventListener('play',()=>{for(const other of document.querySelectorAll('video'))if(other!==v)other.pause();});
for(const button of document.querySelectorAll('[data-fullscreen]'))button.addEventListener('click',()=>{const v=document.getElementById(button.dataset.fullscreen);if(v.requestFullscreen)v.requestFullscreen();else if(v.webkitEnterFullscreen)v.webkitEnterFullscreen();});
for(const button of document.querySelectorAll('[data-download]'))button.addEventListener('click',()=>{const v=document.getElementById(button.dataset.download),a=document.createElement('a');a.href=v.querySelector('source').src;a.download=button.dataset.filename;document.body.append(a);a.click();a.remove();});
for(const link of document.querySelectorAll('[data-reveal]'))link.addEventListener('click',event=>{const target=document.getElementById(link.dataset.reveal);if(!target)return;event.preventDefault();for(const id of ['bench','kind','status','activation','search'])document.getElementById(id).value='';filterCards();for(let p=target.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;target.scrollIntoView({behavior:'smooth',block:'start'});});
filterCards();
'''

def render_video(out, media, video_id, label, ffmpeg, embed_records, labels=None, download_name=None):
    thumb = poster(media,ffmpeg)
    out.write(f'<div class="player"><video id="{video_id}" controls playsinline preload="none" poster="{data_uri(thumb,"image/jpeg")}" aria-label="{esc(label)}"><source src="data:{media["mime"]};base64,')
    stream_hash=hashlib.sha256()
    with open(media['path'],'rb') as f:
        for block in iter(lambda:f.read(3*1024*1024),b''):
            stream_hash.update(block);out.write(base64.b64encode(block).decode('ascii'))
    if stream_hash.hexdigest()!=media['sha256']: raise ValueError('Media changed while embedding')
    out.write(f'" type="{media["mime"]}">浏览器未能播放视频，请使用卡片上的下载按钮。</video>')
    if labels: out.write(f'<div class="labels" style="--columns:{len(labels)}">'+''.join(f'<span>{esc(x)}</span>' for x in labels)+'</div>')
    out.write('</div>')
    out.write(f'<div class="player-tools"><span>点击播放 · 可全屏查看</span><span class="tools-buttons"><button data-fullscreen="{video_id}">全屏</button><button data-download="{video_id}" data-filename="{esc(download_name or Path(media["path"]).name)}">下载视频</button></span></div>')
    embed_records.append({'video_id':video_id,**media,'poster_path':str(thumb),'poster_sha256':sha256(thumb)})

def render_card(out,item,n,ffmpeg,embedded):
    kind=item['section_kind']; m=item['media']; bench=item['benchmark'].lower(); status=status_label(item.get('review_status'))
    display_task=item.get('display_task') or (item['task'] if re.search('[\u4e00-\u9fff]',item['task']) else '')
    brief=item.get('display_summary') or str(item.get('review_summary') or '').split('。')[0]
    search=' '.join(str(item.get(k) or '') for k in ('title','source_id','variant','task','review_summary','method_label')).lower()
    out.write(f'<article id="case_{esc(item["id"])}" class="card" data-benchmark="{esc(bench)}" data-kind="{kind}" data-activation="{activation(item)}" data-status="{esc(status)}" data-search="{esc(search)}"><div class="card-head"><div class="description"><div class="tagline"><span class="tag">{esc(item["source_id"])}</span><span class="tag">{esc(status)}</span><span class="tag">{esc(item.get("method_label"))}</span></div><h3>{esc(item["title"])}</h3><p class="task">{esc(display_task)}</p>')
    if item.get('review_summary'):out.write(f'<p class="review">{esc(brief)}</p>')
    render_motion_fidelity(out,item)
    render_event_timing(out,item)
    duration=[]
    if item.get('valid_frames'):duration.append(f'{item["valid_frames"]} 有效帧')
    if item.get('fps'):duration.append(f'{item["fps"]} fps')
    for key in ('clip_note','source_processing','pair_group'):
        if item.get(key):duration.append(str(item[key]))
    out.write(f'<p class="meta">{esc(" · ".join(duration))}</p>')
    if item.get('reference_image_used') is not True:out.write('<p class="no-ref">'+('使用参考图：待核对' if item.get('reference_image_used') is None else '使用参考图：无')+'</p>')
    out.write('</div>')
    if item.get('reference_image_used') is True:
        image=m['reference_image_path'];out.write(f'<figure class="ref"><img src="{data_uri(image["path"],image["mime"])}" alt="{esc(item["title"])}的实际参考图" loading="lazy"><figcaption>实际参考图</figcaption></figure>')
    out.write('</div>')
    if kind in ('guided','prompt','sampler','positional'):
        labels=item.get('column_labels') or ({'guided':CAPTIONS,'prompt':['参考视频','原提示词编辑','调整提示词编辑'],'sampler':['参考视频','Euler 普通编辑','res_multistep 普通编辑'],'positional':['参考视频','普通编辑','RoPE 时间坐标对齐']}[kind])
        if kind=='prompt':out.write('<div class="media-title">提示词对照 · 第三栏为调整提示词后的编辑结果</div>')
        if kind=='sampler':out.write('<div class="media-title">采样器对照 · Euler 与 res_multistep 普通编辑</div>')
        render_video(out,m['comparison_video_path'],f'v{n}',item['title'],ffmpeg,embedded,labels,download_name=item['id']+'_full_valid.mp4')
    else:
        selected=[f for f in ('reference_video_path','ordinary_video_path','guided_video_path','alternative_video_path') if f in m]
        names={'ordinary_video_path':'普通编辑','guided_video_path':'时序引导','alternative_video_path':'调整提示词编辑','reference_video_path':'参考视频'}
        out.write(f'<div class="pending-note">当前归档：{esc("、".join(names[f] for f in selected))}。下方视频独立播放。</div>')
        out.write('<div class="pending-players">')
        for j,f in enumerate(selected):
            out.write('<div>')
            out.write(f'<div class="media-title">{names[f]}</div>');render_video(out,item.get('pending_display_media',{}).get(f,m[f]),f'v{n}_{j}',item['title']+' '+names[f],ffmpeg,embedded,download_name=item['id']+'_'+f.replace('_path','')+'.mp4');out.write('</div>')
        out.write('</div>')
    paths=item.get('evidence_paths') or []
    out.write('<details class="evidence"><summary>实验记录与来源</summary><ul>')
    out.write(f'<li>记录：{esc(item["id"])} · {esc(item.get("variant"))}</li>')
    out.write(f'<li>素材时间：{esc(item.get("source_time_precision"))}</li>')
    out.write(f'<li>任务说明：{esc(item["task"])}</li><li>完整审阅：{esc(item.get("review_summary"))}</li>')
    for p in paths:out.write(f'<li>{esc(p)}</li>')
    metric=(item.get('quantitative_metrics') or {}).get('motion_fidelity')
    if metric:out.write('<li>Motion Fidelity 记录：<pre>'+esc(json.dumps(metric,ensure_ascii=False,indent=2))+'</pre></li>')
    timing=(item.get('quantitative_metrics') or {}).get('event_timing')
    if timing:out.write('<li>局部时序测量记录：<pre>'+esc(json.dumps(timing,ensure_ascii=False,indent=2))+'</pre></li>')
    for field,media in m.items():out.write(f'<li>{esc(field)}：{esc(media["path"])}<br>SHA256 {media["sha256"]}</li>')
    if item.get('also_listed_as'):out.write('<li>合并相同输出记录：'+esc(', '.join(x['id'] for x in item['also_listed_as']))+'</li>')
    out.write('</ul></details></article>')

def verify_html(path, expected_videos):
    counts=Counter(); tail=''
    patterns={'data_videos':'<source src="data:video/','videos':'<video ','preload_none':'preload="none"','data_images':'<img src="data:image/'}
    with path.open() as f:
        for chunk in iter(lambda:f.read(1024*1024),''):
            text=tail+chunk
            for k,p in patterns.items():counts[k]+=text.count(p)-tail.count(p)
            if re.search(r'(?:src|href)=["\'](?:https?://|file:|/Users/|/data[0-9]/)',text):raise ValueError('External/local media dependency found')
            tail=text[-200:]
    if counts['data_videos']!=expected_videos or counts['videos']!=expected_videos or counts['preload_none']!=expected_videos:
        raise ValueError(f'Embedded video verification failed {counts}, expected {expected_videos}')
    return dict(counts)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inventory',action='append');ap.add_argument('--output',type=Path,default=Path('/Users/researcher/Downloads/H3_FlexiAct_IVEBench_全部实验对比_单文件_20261018.html'));ap.add_argument('--ffmpeg',default=shutil.which('ffmpeg') or 'ffmpeg');args=ap.parse_args()
    inputs=[Path(p) for p in args.inventory] if args.inventory else [ROOT/'inventory/flexiact.json',ROOT/'inventory/ivebench.json']
    cache={}; allitems=[]
    for path in inputs:allitems.extend(validate_item(i,cache) for i in load_inventory(path))
    items,duplicates=deduplicate(allitems);prepare_pending(items,args.ffmpeg);counts=Counter(x['section_kind'] for x in items);embedded=[]
    args.output.parent.mkdir(parents=True,exist_ok=True);temp=args.output.with_suffix('.html.tmp')
    statuses=sorted(set(status_label(x.get('review_status')) for x in items))
    with temp.open('w') as out:
        out.write('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>H3 · FlexiAct 与 IVEBench 实验总览</title><style>'+CSS+'</style></head><body><main><header><div class="eyebrow">H3 VIDEO EDITING · RESEARCH RESULTS</div><h1>FlexiAct 与 IVEBench 实验总览</h1><p class="intro">查看每项任务的原视频、普通编辑和时序引导结果。参考图与视频已嵌入本文件，可直接分享并离线播放。</p><div class="stats">')
        for num,label in ((counts['guided'],'已齐方法对照'),(counts['prompt'],'提示词对照'),(counts['sampler'],'采样器对照'),(counts['positional'],'位置坐标对照'),(counts['reference_origin'],'参考分支相位对照'),(counts['pending'],'普通编辑记录')):out.write(f'<div class="stat"><strong>{num}</strong>{label}</div>')
        out.write('</div></header><nav class="toolbar" aria-label="结果筛选"><label>数据集<select id="bench"><option value="">全部</option><option value="flexiact">FlexiAct</option><option value="ivebench">IVEBench</option></select></label><label>对照<select id="kind"><option value="">全部</option><option value="guided">时序引导</option><option value="prompt">提示词对照</option><option value="sampler">采样器对照</option><option value="positional">位置坐标对照</option><option value="reference_origin">参考分支相位对照</option><option value="pending">普通编辑记录</option></select></label><label>触发<select id="activation"><option value="">全部</option><option value="active">实际干预</option><option value="zero">零触发</option><option value="unknown">待核对</option><option value="not_applicable">普通编辑及其对照</option></select></label><label>审阅<select id="status"><option value="">全部</option>')
        for s in statuses:out.write(f'<option value="{esc(s)}">{esc(s)}</option>')
        out.write('</select></label><input id="search" type="search" aria-label="搜索任务" placeholder="搜索任务、素材或方法"><span class="meta">显示 <span id="visible-count">'+str(len(items))+'</span> 项</span></nav>')
        render_repair_index(out, items, ROOT/'inventory/repair_index.json')
        n=0
        for bench,label in [('flexiact','FlexiAct'),('ivebench','IVEBench')]:
            subset=[x for x in items if x['benchmark'].lower()==bench]
            if not subset:continue
            out.write(f'<section class="benchmark-section" id="{bench}"><h2>{label}</h2>')
            if bench == 'flexiact':
                out.write('<p class="intro">本节采用 FlexiAct 官方 Motion Fidelity，比较点轨迹的运动方向。它与 IVEBench 的同名指标公式不同，两节分数分别解读。</p>')
            else:
                out.write('<p class="intro">本节采用 IVEBench 官方 Motion Fidelity，比较点轨迹的位置与位移变化。轨迹遮挡后的插值可能改变时间对应关系；局部动作另按原始帧时刻评测。</p>')
            out.write('<p class="metric-note">编辑任务是否完成见每项审阅结论；MF 衡量整体运动保持程度。人物未替换成功也可能得到较高 MF。动作时间表列出视觉事件边界及各自的采样精度。</p>')
            for kind,title in [('guided','时序引导对照'),('prompt','提示词对照'),('sampler','采样器对照'),('positional','位置坐标对照'),('reference_origin','参考分支相位对照'),('pending','普通编辑记录')]:
                selected=[x for x in subset if x['section_kind']==kind]
                if not selected:continue
                if kind!='guided':out.write(f'<details class="group-details" data-kind="{kind}"><summary>{title} · {len(selected)} 项</summary>')
                for item in selected:render_card(out,item,n,args.ffmpeg,embedded);n+=1
                if kind!='guided':out.write('</details>')
            out.write('</section>')
        out.write('<div id="no-results" class="empty" hidden>没有符合筛选条件的结果。</div><footer class="footer">所有结果按实际输出归档；同一组视频在不同页面中的重复记录已合并。视频播放使用内嵌媒体，实验文件路径仅供溯源。<br>更新：'+datetime.now().strftime('%Y-%m-%d %H:%M')+'</footer></main><script>'+JS+'</script></body></html>')
    verified=verify_html(temp,len(embedded));os.replace(temp,args.output)
    manifest={'schema':'h3-all-results-showcase-v1','created_at':datetime.now().isoformat(),'output':str(args.output),'output_sha256':sha256(args.output),'output_bytes':args.output.stat().st_size,'inventories':[{'path':str(p),'sha256':sha256(p)} for p in inputs],'input_count':len(allitems),'display_count':len(items),'counts':dict(counts),'duplicates':duplicates,'items':items,'embedded_videos':embedded,'html_verification':verified}
    repair_index = ROOT/'inventory/repair_index.json'
    if repair_index.exists():
        manifest['repair_index'] = {'path':str(repair_index),'sha256':sha256(repair_index),'content':json.loads(repair_index.read_text())}
    (ROOT/'audit'/'SHOWCASE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(json.dumps({k:manifest[k] for k in ('output','output_sha256','output_bytes','input_count','display_count','counts','html_verification')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
