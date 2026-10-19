"""Read-only parent inspection; no model imports, GPU calls or remote writes."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=Path('/Users/researcher/DevProjects')
PARENTS=[
 ('short_0210','h3-timing-ivebench-prompt-pair-r71-20261018','r71_short_0210_seed2026101701_p1','p1','audit/consumer/incoming/PAIR_RUNTIME_GATE.json'),
 ('short_0230','h3-timing-local-edit-repair-r80-20261018','r80_short_0230_seed2026101701_native','native','audit/input_decode_recovery_v2/incoming/short_0230/NATIVE_RUNTIME_GATE_HOST9_v2.json'),
 ('short_0352','h3-timing-local-edit-repair-r80-20261018','r80_short_0352_seed2026101701_native','native','audit/input_decode_recovery_v2/incoming/short_0352/NATIVE_RUNTIME_GATE_HOST9_v2.json'),
]
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def main():
 cases=[];files=[]
 for source,name,run,arm,gate_rel in PARENTS:
  parent=BASE/name;gatefile=parent/gate_rel;g=read(gatefile);assert g['passed'] is True and all(g['checks'].values())
  runtime=read(parent/'configs/runtime.json');graphfile=parent/'configs/graphs'/f'{run}.json';graph=read(graphfile);result=g['runs'][arm]
  assert g['runtime_profile']==runtime and g['runtime_profile_sha256']==sha(parent/'configs/runtime.json')
  assert runtime['host']=='H3_SERVER_A' and runtime['memory_mode']=='normal' and runtime['reserve_vram']==8
  assert result['run_id']==run and result['NFE']==20 and result['Euler_updates']==20 and result['routed_blocks']==0
  assert graph['50']['inputs']['mode']=='native' and graph['5']['inputs']['length']==90 and graph['6']['inputs']['noise_seed']==2026101701
  assert 'ref_image' not in graph['5']['inputs'] and result['evaluation_crop_xywh']==[16,8,1280,720]
  kernel=read(parent/'configs/runtime_kernel_hashes.json');actual_kernel={rel:sha(parent/rel) for rel in kernel}
  assert all(actual_kernel[rel]==v['current_sha256'] for rel,v in kernel.items())
  snap=ROOT/'design'/source;snap.mkdir(exist_ok=True)
  for original,name2 in [(gatefile,'PARENT_ACTUAL_GATE.json'),(graphfile,'PARENT_GRAPH.json'),(parent/'configs/runtime.json','PARENT_RUNTIME.json'),(parent/'configs/parent_core_hashes.json','PARENT_CORE_HASHES.json'),(parent/'configs/runtime_kernel_hashes.json','PARENT_NUMERICAL_FILES.json')]:
   target=snap/name2;data=original.read_bytes()
   if target.exists():assert target.read_bytes()==data
   else:target.write_bytes(data)
   files.append({'original':str(original),'snapshot':str(target.relative_to(ROOT)),'sha256':sha(target)})
  prompt=graph['5']['inputs']['prompt'];(snap/'PARENT_PROMPT.txt').write_text(prompt)
  video=parent/'inputs'/graph['22']['inputs']['file'];assert video.is_file()
  noise_pair=graph['6']['inputs']['pair_id']; shared=graph['5']['inputs']['run_id']
  prefix=result['snapshots'][:6];assert all(Path(r['file']).name==f'x0_step{i:03}.pt' for i,r in enumerate(prefix))
  cases.append({'source_id':source,'parent_local_root':str(parent),'parent_remote_root':runtime['remote_root'],'parent_run':run,'parent_arm_key':arm,'parent_gate_local':str(gatefile),'parent_gate_sha256':sha(gatefile),'parent_video':result['video'],'parent_runtime_sha256':sha(parent/'configs/runtime.json'),'parent_graph_sha256':sha(graphfile),'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'prepared_video_local':str(video),'prepared_video_sha256':sha(video),'parent_shared_run':shared,'parent_noise_relative':f'audit/{noise_pair}_noise.pt','parent_conditioning_relative':f'audit/{run}_conditioning.json','parent_shared_conditioning_relative':f'audit/{shared}_conditioning.json','parent_x0_manifest_relative':f'audit/x0/{run}/manifest.json','parent_prefix_0_5':prefix,'total_frames':90,'valid_frames':result['valid_frames'],'fps':24,'reference_video_count':1,'reference_image_count':0,'core_hashes':read(parent/'configs/parent_core_hashes.json'),'numerical_file_hashes':actual_kernel,'runtime_shared':{k:runtime[k] for k in ['host','core','python','dependencies','models','kj_nodes','memory_mode','reserve_vram']},'scientific_matching_status':'PENDING_NEW_GUIDED_ACTUAL_CONDITIONS_NOISE_AND_PREFIX','quality_status':'PENDING_ROOT_TASK_ACCEPTANCE'})
 assert all(c['core_hashes']==cases[0]['core_hashes'] and c['numerical_file_hashes']==cases[0]['numerical_file_hashes'] and c['runtime_shared']==cases[0]['runtime_shared'] for c in cases)
 output={'schema':'r99-local-parent-inspection-v1','passed':True,'scope':'CPU local historical records. Remote existence/content and future actual matching are separate gates.','cases':cases,'snapshots':files,'all_three_same_core_and_numerical_files':True}
 save(ROOT/'design/PARENT_LINEAGE_LOCAL.json',output)
 print(json.dumps({'passed':True,'sources':[c['source_id'] for c in cases],'valid':[c['valid_frames'] for c in cases],'parent_records':len(files),'all_three_same_core_and_numerical_files':True}))
if __name__=='__main__':main()
