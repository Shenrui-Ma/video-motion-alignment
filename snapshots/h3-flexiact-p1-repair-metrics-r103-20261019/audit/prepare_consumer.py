from pathlib import Path
import json,hashlib,shutil
D=Path('/Users/researcher/DevProjects');R=Path(__file__).resolve().parents[1];P=D/'h3-ive-task-repair-metrics-r100-20261019';B=D/'h3-timing-flexiact-p1-repair-r103-20261019'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
assert not (R/'CONSUMER_FREEZE.json').exists()
for folder in ['scripts','tests','configs','inputs','incoming','incoming_pairs','showcase','showcase_pairs','prepared']:(R/folder).mkdir(exist_ok=True)
for folder in ['scripts','tests']:
 for src in (P/folder).glob('*.py'):
  text=src.read_text()
  for a,b in [('R100','R103'),('r100','r103'),('short_0114','human2animal_2__game_man_4'),('short_0392','chest__game_girl_1'),('H3_SERVER_A','H3_SERVER_B'),('1016','1004'),('8564','8567'),('/data5/researcher/h3_runs/timing_ive_task_repair_r103_20261019','/data4/researcher/h3_runs/timing_flexiact_p1_repair_r103_20261019'),('unexpected .9 runtime','unexpected .41 runtime'),('1312','1152'),('736','768'),('crop=1280:720:16:8','crop=1152:768:0:0')]:text=text.replace(a,b)
  (R/folder/src.name).write_text(text)
s=read(B/'configs/scientific_contract.json');runtime=read(B/'configs/runtime.json')
c=dict(schema='r103-native-and-paired-media-consumer-v1',producer_local=str(B),producer_remote=runtime['remote_root'],producer_seal_sha256=sha(B/'deploy_manifest.json'),producer_contract_sha256=sha(B/'configs/scientific_contract.json'),producer_runtime_sha256=sha(B/'configs/runtime.json'),host=runtime['host'],source_order=s['source_ids'],sources=[],scope='CPU one-shot intake only after actual Native or paired runtime gate; no watcher, verifier or GPU.',method='固定时序引导（去噪步骤索引6–14，α=1，全部有效参考时间位置）；基础编辑完成后由 root 决定是否生成引导对照。')
tasks=['将参考图的黑发绿披肩动漫男子迁移到原片的盘腿前屈动作，使用目标图白背景。','将参考图中的半身铠甲女性迁移到原片的双臂拉索收放动作，使用目标图暗背景。']
for i,source in enumerate(s['source_ids']):
 a=next(x for x in s['cases'] if x['source_id']==source and x['arm']=='native');b=next(x for x in s['cases'] if x['source_id']==source and x['arm']=='forced')
 row=dict(source_id=source,run_id=a['run_id'],forced_run_id=b['run_id'],graph_sha256=sha(B/'configs/graphs'/(a['run_id']+'.json')),forced_graph_sha256=sha(B/'configs/graphs'/(b['run_id']+'.json')),geometry=a['geometry'],valid_frames=a['valid_frame_count'],crop_xywh=a['evaluation_crop_xywh'],evaluation_indices=a['evaluation_indices'],evaluation_fps=8,prompt_version=a['prompt_version'],prompt=a['prompt'],display_task=tasks[i],original_task={'pair_id':a['original_pair_id'],'group':a['group'],'motion_source_id':a['motion_source_id'],'target_identity':a['identity'],'edit_prompt':tasks[i],'prompt_scope':'Our P1 prompt for unchanged official assets; human2animal crosspair is an extension.'},reference_image_expected=a['reference_image_expected'])
 for key,name in [('source',a['video']),('provenance',a['provenance']),('portrait',a['portrait'])]:
  shutil.copy2(B/'inputs'/name,R/'inputs'/name);row[key]=dict(file='inputs/'+name,sha256=sha(R/'inputs'/name),bytes=(R/'inputs'/name).stat().st_size)
 c['sources'].append(row)
write(R/'configs/contract.json',c)
for name,src in [('producer_runtime.json','configs/runtime.json'),('producer_scientific_contract.json','configs/scientific_contract.json'),('producer_seal.json','deploy_manifest.json')]:shutil.copy2(B/src,R/'configs'/name)
write(R/'audit/PREPARATION_ORIGIN.json',dict(old_consumer=str(P),old_freeze_sha256=sha(P/'CONSUMER_FREEZE.json'),new_producer=str(B),new_producer_seal=sha(B/'deploy_manifest.json'),watcher_started=False,GPU_started=False))
# Add actual one-image layout and original sampling obligations to the reused gates.
f=R/'scripts/common.py';t=f.read_text().replace("'native_actual_noise_cache')","'native_actual_noise_cache','native_reference_geometry')").replace("('source','provenance')","('source','provenance','portrait')")
t=t.replace(" v=r['video'];safe_path", " require(r.get('evaluation_indices')==p['evaluation_indices'] and r.get('evaluation_fps')==8,'original 49-frame physical sampling differs')\n v=r['video'];safe_path")
f.write_text(t)
f=R/'scripts/prepare_freeze.py';t=f.read_text().replace("case['prompt']==p['prompt'] and case['original_task']==p['original_task'] and case['clip']==p['clip']","case['prompt']==p['prompt'] and case['original_pair_id']==p['original_task']['pair_id'] and case['identity']==p['original_task']['target_identity']")
t=t.replace("case['reference_image_count']==0","case['reference_image_count']==1").replace("('provenance','provenance_sha256')","('provenance','provenance_sha256'),('portrait','portrait_sha256')")
t=t.replace("   field='graph_sha256'", "   require(case['evaluation_indices']==p['evaluation_indices']==list(range(0,147,3)) and case['reference_image_expected']==p['reference_image_expected'],'Flex sampling/reference layout differs')\n   field='graph_sha256'")
f.write_text(t)
# The raw source and generated media have identical 1152x768 canvases.
for name in ['render_native.py','render_pair.py']:
 f=R/'scripts'/name;t=f.read_text()
 for a,b in [('2560','2304'),('3840','3456'),('1280','1152'),('808','856'),('640,360','576,384'),('1920','1728'),('406','430'),('+382','+406'),('+363','+387'),('主体编辑','角色替换'),('IVEBench 完整短视频任务，预先固定2个来源','FlexiAct 原素材，2个原动作；分别为公开配对和原素材交叉配对')]:t=t.replace(a,b)
 # Native contact sheet width is 1280 in its original version; prior replacement makes it 1152.
 t=t.replace("'prompt_version':p['prompt_version']", "'prompt_version':p['prompt_version'],'reference_image':p['portrait'],'reference_image_expected':p['reference_image_expected']")
 t=t.replace(" pictures=''.join", " portrait=ROOT/p['portrait']['file'];require(sha(portrait)==p['portrait']['sha256'],'portrait changed');portrait_uri='data:image/'+('webp' if portrait.suffix=='.webp' else 'jpeg')+';base64,'+base64.b64encode(portrait.read_bytes()).decode()\n pictures=''.join")
 t=t.replace('<p>任务：{task}</p>', '<p>任务：{task}</p><figure><img style="width:auto;max-width:260px;max-height:300px" src="{portrait_uri}"><figcaption>目标角色参考图（原始素材）</figcaption></figure>')
 f.write_text(t)
f=R/'scripts/metric_inputs.py';t=f.read_text().replace('IVEBench official MF','FlexiAct official MF').replace("'evaluate_indices':list(range(p['valid_frames']))","'evaluate_indices':p['evaluation_indices'],'evaluation_fps':8")
t=t.replace("'reference_image_used':False","'reference_image_used':True,'reference_image':bound(ROOT/p['portrait']['file'])")
t=t.replace('Complete official short-source subset. Score all fixed valid frames; no generated-result temporal alignment or sample filtering.', '49 original source instants at 8fps, indices 0,3,...144 in 24fps media. Human2animal is an official-assets crosspair; chest is an official CSV pair. Score all fixed instants without time alignment.')
t=t.replace(" require(sha(rows['source']['file'])", " require(sha(ROOT/p['portrait']['file'])==p['portrait']['sha256'],'metric portrait SHA differs')\n require(sha(rows['source']['file'])")
f.write_text(t)
# Fixture adaptations verify physical sampling rather than inherited IVE assumptions.
for name in ['test_consumer.py','test_paired.py']:
 f=R/'tests'/name;t=f.read_text().replace("'evaluation_crop_xywh':p['crop_xywh']", "'evaluation_crop_xywh':p['crop_xywh'],'evaluation_indices':p['evaluation_indices'],'evaluation_fps':8").replace("'evaluation_crop_xywh':self.case['crop_xywh']", "'evaluation_crop_xywh':self.case['crop_xywh'],'evaluation_indices':self.case['evaluation_indices'],'evaluation_fps':8")
 f.write_text(t)
f=R/'tests/test_metric_inputs.py';t=f.read_text().replace("(root/'native.mp4').write_bytes", "(root/'inputs/portrait.jpg').write_bytes(b'portrait fixture');(root/'native.mp4').write_bytes")
t=t.replace("'geometry':{'frames':107},'valid_frames':105,'crop_xywh':[16,8,1280,720]", "'portrait':{'file':'inputs/portrait.jpg','sha256':m.sha(root/'inputs/portrait.jpg')},'geometry':{'frames':158},'valid_frames':147,'evaluation_indices':list(range(0,147,3)),'crop_xywh':[0,0,1152,768]")
t=t.replace('list(range(105))','list(range(0,147,3))').replace("v['valid_frames'],105","v['valid_frames'],147").replace('[16,8,1280,720]','[0,0,1152,768]').replace("'inputs/ref.mp4']", "'inputs/ref.mp4','inputs/portrait.jpg']")
f.write_text(t)
print('Prepared independent CPU consumer; not frozen yet',R)
