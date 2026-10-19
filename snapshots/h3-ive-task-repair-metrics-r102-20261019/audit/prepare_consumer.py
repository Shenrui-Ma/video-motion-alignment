from pathlib import Path
import json,hashlib,shutil
D=Path('/Users/researcher/DevProjects');R=Path(__file__).resolve().parents[1];P=D/'h3-ive-task-repair-metrics-r100-20261019';B=D/'h3-timing-ive-task-repair-r102-20261019'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
assert not(R/'CONSUMER_FREEZE.json').exists()
for name in ['scripts','tests','configs','inputs','audit','incoming','incoming_pairs','showcase','showcase_pairs','prepared']:(R/name).mkdir(exist_ok=True)
parentfreeze=read(P/'CONSUMER_FREEZE.json');copied={}
for folder in ['scripts','tests']:
 for src in (P/folder).glob('*.py'):
  rel=str(src.relative_to(P));assert sha(src)==parentfreeze['files'][rel]
  text=src.read_text().replace('R100','R102').replace('r100','r102').replace('short_0114','short_0263').replace('short_0392','short_0092').replace('8564','8566')
  text=text.replace("SOURCES=('short_0263','short_0092')","SOURCES=('short_0263','short_0092','short_0126')").replace('len(c.SOURCES),2','len(c.SOURCES),3').replace('test_fixed_two_denominator','test_fixed_three_denominator').replace("'fixed_source_denominator':2","'fixed_source_denominator':3").replace('固定2个来源','固定3个来源')
  if src.name=='test_metric_inputs.py':text=text.replace("'frames':107","'frames':90").replace("'valid_frames':105","'valid_frames':74").replace('range(105)','range(74)').replace("v['valid_frames'],105","v['valid_frames'],74")
  (R/rel).write_text(text);copied[rel]={'parent_sha256':sha(src),'new_sha256':sha(R/rel)}
s=read(B/'configs/scientific_contract.json');runtime=read(B/'configs/runtime.json')
c={'schema':'r102-native-and-paired-media-consumer-v1','producer_local':str(B),'producer_remote':runtime['remote_root'],'producer_seal_sha256':sha(B/'deploy_manifest.json'),'producer_contract_sha256':sha(B/'configs/scientific_contract.json'),'producer_runtime_sha256':sha(B/'configs/runtime.json'),'host':runtime['host'],'source_order':s['source_ids'],'sources':[],'scope':'One-shot CPU collection; actual Native gate then root decides guide or skip; actual paired gate for matched comparison. No producer verifier, inference, queue submission or watcher.','method':'固定时序引导（20步Euler中步骤索引6–14，α=1，全部有效参考时间位置）；基础编辑验收通过后配对。'}
labels={'short_0263':'把女人替换为年轻女孩，保留坐蓝色斜躺椅读书及原庭院。','short_0092':'移除室内植物，保留女人、手势、摄像机和其余房间内容。','short_0126':'在原床上男人旁添加猫，保留男人背向镜头坐姿伸展。'}
for sid in s['source_ids']:
 a=next(x for x in s['cases'] if x['source_id']==sid and x['arm']=='native');b=next(x for x in s['cases'] if x['source_id']==sid and x['arm']=='forced')
 row=dict(source_id=sid,run_id=a['run_id'],forced_run_id=b['run_id'],graph_sha256=sha(B/'configs/graphs'/(a['run_id']+'.json')),forced_graph_sha256=sha(B/'configs/graphs'/(b['run_id']+'.json')),geometry=a['geometry'],valid_frames=a['valid_frame_count'],crop_xywh=a['evaluation_crop_xywh'],prompt_version=a['prompt_version'],prompt=a['prompt'],original_task=a['original_task'],clip=a['clip'],display_task=labels[sid],reference_image_used=False)
 for key,name in [('source',a['video']),('provenance',a['provenance']),('original_media',sid+'_original.mp4')]:
  shutil.copy2(B/'inputs'/name,R/'inputs'/name);row[key]=dict(file=('inputs/'+name) if key!='original_media' else str(R/'inputs'/name),sha256=sha(R/'inputs'/name),bytes=(R/'inputs'/name).stat().st_size)
 c['sources'].append(row)
write(R/'configs/contract.json',c)
for name,src in [('producer_runtime.json','configs/runtime.json'),('producer_scientific_contract.json','configs/scientific_contract.json'),('producer_seal.json','deploy_manifest.json')]:shutil.copy2(B/src,R/'configs'/name)
write(R/'audit/PREPARATION_ORIGIN.json',{'old_consumer':str(P),'old_freeze_sha256':sha(P/'CONSUMER_FREEZE.json'),'new_producer':str(B),'new_producer_seal':sha(B/'deploy_manifest.json'),'copied_administrative_files':copied,'scientific_metric_algorithm_added_or_modified':False,'no_execution_binding_yet':True,'watcher_started':False,'GPU_started':False})
write(R/'audit/METADATA_ERRATUM.json',{'source_file':str(B/'analysis/postrun/verify_pair.py'),'source_sha256':sha(B/'analysis/postrun/verify_pair.py'),'field':'quality_assessment','inherited_text':'IVEBench source clip exploration; separate requested-edit and motion assessment, no full official benchmark score','accurate_scope':'R102 uses three complete official short sources, development task repairs; padding excluded; not full benchmark reproduction. Consumer labels this actual scope.','producer_science_or_file_changed':False})
print('prepared',R,c['source_order'])
