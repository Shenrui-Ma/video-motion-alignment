"""Build the requested overnight-only, offline video review without touching reports."""
import base64
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT.parent
AUDIT = PROJECTS / 'h3-research-progress-notes-20261020/overnight_audit/RESULT.json'
INVENTORY = PROJECTS / 'h3-benchmark-all-results-showcase-20261018/inventory/ivebench.json'
EVIDENCE = PROJECTS / 'h3-benchmark-all-results-showcase-20261018/task_view_20261019/display_evidence.json'
OUTPUT = Path('/Users/researcher/Downloads/H3_睡眠期间新增实验对比_20261020.html')
EXTRA = ROOT / 'after_wake_extra.json'
TITLES = {
 'short_0252':'角色替换 — 机舱男人换为年长女人',
 'short_0358':'外观编辑 — 给饮酒男子加眼镜',
 'long_0039':'物体编辑 — 办公室书本改为蓝色',
 'long_0161':'角色替换 — 公园男子换为儿童',
 'long_0034':'物体编辑 — 切黄瓜场景添加砧板',
 'long_0122':'主体替换 — 金刚鹦鹉换为巨嘴鸟',
 'long_0059':'物体编辑 — 擦眼男子手中添加白手帕',
 'long_0031':'物体编辑 — 木砧板换为大理石砧板',
 'long_0163':'外观编辑 — 办公室浅蓝正装改为黑色',
 'short_0362':'外观编辑 — 蓝色书封改为红色',
 'short_0177':'主体替换 — 打哈欠的老虎换为狮子',
 'short_0353':'外观编辑 — 蓝色手术服改为绿色',
 'short_0084':'角色替换 — 放下手臂的男子换为女子',
 'short_0235':'外观编辑 — 海獭改为绿色',
 'long_0191':'位置编辑 — 手势男子向右移动',
 'long_0116':'位置编辑 — 俯卧撑人物向左移动',
 'short_0163':'位置编辑 — 指电脑的男子移到电脑另一侧',
}
METHODS = {'native_only':'普通编辑', 'guided_pair':'固定时序引导',
 'resumed_online_guidance':'自动时序引导', 'positional_control':'RoPE 时间坐标对齐',
 'reference_origin_control':'参考分支相位引导'}
PROMPTS = {
 'official_edit_prompt':'benchmark 原文',
 'official_edit_prompt_with_task_reference_envelope':'原文 + 输入绑定',
 'official_edit_prompt_with_task_reference_and_generic_retention':'原文 + 输入绑定 + 通用保留要求',
 'IVEBench-edit-with-generic-retention-v1':'原文 + 输入绑定 + 通用保留要求',
}

def sha(path):
 return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def prompt_label(item, fallback):
 text=item.get('prompt','')
 headings=('subject_definitions:','summary:','retention_analysis:',
           'detailed_description:','overall_soundscape:','non_diegetic_music:')
 if all(heading in text.splitlines() for heading in headings):
  return '六段提示词：含人物、场景与动作描述'
 if item.get('prompt_version') in (
  'official_edit_prompt_with_task_reference_and_generic_retention',
  'IVEBench-edit-with-generic-retention-v1'):
  return 'benchmark原句 + 输入绑定 + 通用保留要求'
 return fallback

def fixed_method(item):
 """Explain the schedule only after checking the actual graph and runtime gate."""
 bindings=item.get('actual_prompt_by_column',{}).get('guided',{}).get('graph_bindings',[])
 if item['comparison_kind']!='guided_pair' or len(bindings)!=1:
  return item.get('method_label',''),None
 binding=bindings[0];path=Path(binding['graph'])
 assert sha(path)==binding['graph_sha256'],'fixed graph hash changed'
 graph=json.loads(path.read_text())
 assert graph[binding['node_id']]['inputs']['prompt']==item['prompt']
 routers=[n['inputs'] for n in graph.values() if n.get('class_type')=='H3TemporalRouter']
 gate_path=path.parent/'PAIR_RUNTIME_GATE.json'
 assert sha(gate_path)==item['evidence_sha256'][str(gate_path)],'fixed gate hash changed'
 gate=json.loads(gate_path.read_text())
 expected={'mode':'mass_preserve','step_start':6,'step_end':15,'start_frame':0,
  'end_frame':item['valid_frames']-1,'radius':0,'time_offset':0,'alpha':1.0,
  'block_start':0,'block_end':50}
 matches=(len(routers)==1 and all(routers[0].get(k)==v for k,v in expected.items())
  and gate['passed'] and gate['runs']['forced']['NFE']==20)
 proof={'id':item['id'],'graph':str(path),'graph_sha256':sha(path),
  'gate':str(gate_path),'gate_sha256':sha(gate_path),'same_registered_schedule':matches,
  'parameters':routers,'actual_NFE':gate['runs']['forced']['NFE']}
 detail=('固定引导：20步中的第7–15步开启；覆盖整段有效视频；各时刻关注参考视频同一时间单元。'
  'α=1，50个 DiT block，内部步骤编号为6–14。') if matches else item.get('method_label','')
 return detail,proof

def publish(local, expected_sha256=None):
 """Replace only a verified export; preserve any intervening user edit."""
 target = OUTPUT
 prior = sha(target) if target.exists() else None
 if target.exists() and prior != expected_sha256:
  target = OUTPUT.with_name(OUTPUT.stem + '_R141b.html')
  if target.exists():
   if sha(target) == sha(local):
    return target, 'existing_identical_addition', prior
   raise RuntimeError('Both export names exist; preserve them and choose a new output name')
 temp = target.with_name('.' + target.name + '.tmp')
 if temp.exists():
  raise RuntimeError('Export temporary path already exists')
 os.link(local, temp)
 try:
  if target == OUTPUT and prior is not None:
   if sha(target) != expected_sha256:
    raise RuntimeError('Export changed while building; user file preserved')
   os.replace(temp, target)
   return target, 'replaced_matching_sha256', prior
  os.link(temp, target)
  return target, 'created_addition' if target != OUTPUT else 'created', prior
 finally:
  temp.unlink(missing_ok=True)

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--replace-sha256',help='Only replace the existing requested export if this SHA matches')
 args=parser.parse_args()
 audit=json.loads(AUDIT.read_text()); inv=json.loads(INVENTORY.read_text())['items']; by={x['id']:x for x in inv}
 extra=json.loads(EXTRA.read_text()) if EXTRA.exists() else {'successful_outputs':[]}
 outputs_all=audit['successful_outputs']+extra['successful_outputs']
 identities={json.dumps(o['generation_identity'],sort_keys=True) for o in outputs_all}
 assert len(identities)==len(outputs_all),'duplicate generated output identity'
 assert all(o['period']=='after_wake' for o in extra['successful_outputs'])
 summary=dict(audit['summary'])
 summary['after_wake_generated_outputs']=sum(o['period']=='after_wake' for o in outputs_all)
 summary['after_wake_independent_source_videos']=len({o['source_id'] for o in outputs_all if o['period']=='after_wake'})
 summary['current_inventory_split']={**summary['current_inventory_split'],'IVEBench':len(inv)}
 summary['current_inventory_version_records']=sum(summary['current_inventory_split'].values())
 proofs=json.loads(EVIDENCE.read_text()).get('versions',{}) if EVIDENCE.exists() else {}
 ids=list(dict.fromkeys(x['inventory_id'] for x in outputs_all))
 assets={}; items=[]; bindings=[];fixed_proofs=[]
 def asset(path,mime,expected=None):
  path=Path(path);digest=sha(path)
  if expected: assert digest==expected,(str(path),'media hash differs')
  if digest not in assets:
   assets[digest]={'mime':mime,'b64':base64.b64encode(path.read_bytes()).decode()}
   bindings.append({'path':str(path),'sha256':digest,'bytes':path.stat().st_size})
  return digest
 for ident in ids:
  x=by[ident]; media=Path(x['comparison_video_path']); proof=proofs.get(ident,{})
  keys=x.get('key_same_frame_indices') or [x['valid_frames']//2]
  frame=int(proof.get('still_frame',keys[len(keys)//2]));frame=max(0,min(frame,x['valid_frames']-1))
  if ident.startswith('r138_'):frame=50
  jpg=ROOT/'stills'/f'{ident}_f{frame}.jpg'
  if not jpg.exists():
   subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-i',str(media),'-vf',f'select=eq(n\\,{frame}),scale=min(2048\\,iw):-2','-frames:v','1','-q:v','3','-threads','2',str(jpg)],check=True)
  mode=x['comparison_kind']; metric=x.get('quantitative_metrics',{}).get('motion_fidelity',{})
  role={'resumed_online_guidance':'visible_only','positional_control':'aligned','reference_origin_control':'reference_origin'}.get(mode,'guided')
  align=x.get('action_alignment_by_method') or {}
  prompt=x.get('prompt_protocol',{}); version=x.get('prompt_version','')
  label=prompt.get('label') or PROMPTS.get(version) or ('含场景与动作描述' if 'full_context' in ident else version or x.get('variant',''))
  label=prompt_label(x,label)
  detail,fixed_proof=fixed_method(x)
  if fixed_proof:fixed_proofs.append(fixed_proof)
  outputs=[o for o in outputs_all if o['inventory_id']==ident]
  event=x.get('event_review',{}).get('events',[])
  items.append({'id':ident,'source':x['source_id'],'title':TITLES[x['source_id']],
   'method':METHODS.get(mode,mode),'mode':mode,'variant':x.get('variant',ident),
   'video':asset(media,'video/mp4',x.get('media_sha256',{}).get('comparison_video_path')),
   'still':asset(jpg,'image/jpeg'),'still_frame':frame,
   'labels':x.get('column_labels',[]),'review':x.get('display_summary') or x.get('review_summary',''),
   'task_ok':x.get('count_as_complete_task_success'),'alignment':[align.get('native'),align.get(role)],
   'mf':[metric.get('native'),metric.get(role)],'frames':x['valid_frames'],'fps':x['fps'],
   'prompt_label':label,'prompt':x.get('prompt',''),'task':x.get('original_task',{}).get('edit_prompt') or x['task'],
   'reference_image':bool(x.get('reference_image_used')),'events':event,
   'event_metrics':x.get('quantitative_metrics',{}).get('event_timing'),
   'event_table':(x.get('quantitative_metrics',{}).get('event_timing') or {}).get('events',[]),
   'method_detail':detail,
   'new_outputs':len(outputs),'completion':max(o['completion']['unix'] for o in outputs),
   'after_wake':all(o['period']=='after_wake' for o in outputs),
   'completion_cst':max(o['completion']['cst'] for o in outputs),
   'full_review':x.get('full_frame_review_path'),'source_record':ident})
 assert len(items)==len(ids) and all(Path(x['path']).exists() for x in bindings)
 # Keep actual output counts distinct from paired displays that reuse older controls.
 data={'items':items,'assets':assets,'summary':summary,
  'default_version':extra.get('default_inventory_id','r138_short_0252_seed2026101703_visible_only')}
 assert data['default_version'] in ids
 template=(ROOT/'template.html').read_text()
 payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
 html=template.replace('__DATA__',payload).replace('__AFTER_WAKE__',str(summary['after_wake_generated_outputs']))
 local=ROOT/'index.html';temp=ROOT/'index.tmp';temp.write_text(html);os.replace(temp,local)
 output,action,prior=publish(local,args.replace_sha256)
 receipt={'output':str(output),'output_sha256':sha(output),'bytes':output.stat().st_size,
  'export_action':action,'previous_export_sha256':prior,
  'version_count':len(items),'source_count':len({i['source'] for i in items}),
  'overnight_generated_outputs':audit['summary']['sleep_generated_outputs'],
  'after_wake_outputs':summary['after_wake_generated_outputs'],
  'after_wake_extra_sha256':sha(EXTRA) if EXTRA.exists() else None,
  'audit_sha256':sha(AUDIT),'inventory_sha256':sha(INVENTORY),'media_bindings':bindings,
  'all_assets_embedded':True,'external_urls':False,'protected_report_touched':False}
 (ROOT/'audit/BUILD.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
 (ROOT/'audit/FIXED_METHOD_BINDINGS.json').write_text(json.dumps(fixed_proofs,ensure_ascii=False,indent=2))
 print(json.dumps({k:v for k,v in receipt.items() if k!='media_bindings'},ensure_ascii=False))

if __name__=='__main__':main()
