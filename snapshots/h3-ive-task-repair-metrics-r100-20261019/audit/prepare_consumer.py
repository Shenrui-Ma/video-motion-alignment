from pathlib import Path
import json,hashlib,shutil
D=Path('/Users/researcher/DevProjects');R=Path(__file__).resolve().parents[1];P=D/'h3-ive-native-screen-metrics-r96-20261018';B=D/'h3-timing-ive-task-repair-r100-20261019'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
assert not (R/'CONSUMER_FREEZE.json').exists()
for directory in ['scripts','tests','configs','inputs','audit','incoming','incoming_pairs','showcase','showcase_pairs','prepared']:(R/directory).mkdir(exist_ok=True)
for folder in ['scripts','tests']:
 for src in (P/folder).glob('*.py'):
  text=src.read_text().replace('R96','R100').replace('r96','r100').replace('long_0047','short_0114').replace('long_0123','short_0392').replace('20261018.html','20261019.html').replace('H3_SERVER_B','H3_SERVER_A').replace('1004','1016').replace('8560','8564').replace('/data4/researcher/h3_runs/timing_ive_native_screen_r100_20261018','/data5/researcher/h3_runs/timing_ive_task_repair_r100_20261019').replace('unexpected .41 runtime','unexpected .9 runtime')
  text=text.replace("SOURCES=('short_0114','short_0392','long_0167','long_0173','long_0174')","SOURCES=('short_0114','short_0392')").replace("len(c.SOURCES),5","len(c.SOURCES),2").replace('test_fixed_five_denominator','test_fixed_two_denominator').replace("'fixed_source_denominator':5","'fixed_source_denominator':2").replace('IVEBench 长视频裁片，预先固定5个来源','IVEBench 完整短视频任务，预先固定2个来源').replace('IVEBench素材片段探索，固定5个来源','IVEBench完整短视频任务，固定2个来源')
  (R/folder/src.name).write_text(text)
s=read(B/'configs/scientific_contract.json');runtime=read(B/'configs/runtime.json');c={'schema':'r100-native-and-paired-media-consumer-v1','producer_local':str(B),'producer_remote':runtime['remote_root'],'producer_seal_sha256':sha(B/'deploy_manifest.json'),'producer_contract_sha256':sha(B/'configs/scientific_contract.json'),'producer_runtime_sha256':sha(B/'configs/runtime.json'),'host':runtime['host'],'source_order':s['source_ids'],'sources':[],'scope':'One-shot CPU collection; actual Native gate then root decides guide or skip; actual paired gate for matched comparison. No verifier, inference, queue submission or watcher.','method':'固定时序引导（20步Euler中步骤索引6–14，α=1，全部有效参考时间位置）；基础编辑验收通过后配对。'}
for source in s['source_ids']:
 a=next(x for x in s['cases'] if x['source_id']==source and x['arm']=='native');b=next(x for x in s['cases'] if x['source_id']==source and x['arm']=='forced')
 row=dict(source_id=source,run_id=a['run_id'],forced_run_id=b['run_id'],graph_sha256=sha(B/'configs/graphs'/(a['run_id']+'.json')),forced_graph_sha256=sha(B/'configs/graphs'/(b['run_id']+'.json')),geometry=a['geometry'],valid_frames=a['valid_frame_count'],crop_xywh=a['evaluation_crop_xywh'],prompt_version=a['prompt_version'],prompt=a['prompt'],original_task=a['original_task'],clip=a['clip'],original_media=dict(file=str(B/'inputs'/(source+'_original.mp4')),sha256=sha(B/'inputs'/(source+'_original.mp4'))))
 for key,name in [('source',a['video']),('provenance',a['provenance'])]:
  shutil.copy2(B/'inputs'/name,R/'inputs'/name);row[key]=dict(file='inputs/'+name,sha256=sha(R/'inputs'/name),bytes=(R/'inputs'/name).stat().st_size)
 c['sources'].append(row)
write(R/'configs/contract.json',c)
for name,src in [('producer_runtime.json','configs/runtime.json'),('producer_scientific_contract.json','configs/scientific_contract.json'),('producer_seal.json','deploy_manifest.json')]:shutil.copy2(B/src,R/'configs'/name)
write(R/'audit/PREPARATION_ORIGIN.json',{'old_consumer':str(P),'old_freeze_sha256':sha(P/'CONSUMER_FREEZE.json'),'new_producer':str(B),'new_producer_seal':sha(B/'deploy_manifest.json'),'no_execution_binding_yet':True,'watcher_started':False,'GPU_started':False})
print('prepared',R,c['source_order'])
