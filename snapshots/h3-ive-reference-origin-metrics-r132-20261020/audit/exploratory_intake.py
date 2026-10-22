"""Root-authorized exploratory media intake; preserve the failed strict input gate."""
import sys, time
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from common import *
from remote import fetch
from render_native import media_info,check_time,choose_font
import render_pair,full_frame_review

def collect():
 c=validate_static();D=R/'incoming_exploratory';F=R/'audit/actual_failed_gate'
 g=read(F/'REFERENCE_ORIGIN_RUNTIME_GATE.json');started=read(F/'STARTED.json');release=read(F/'ROOT_EXIT_RECEIPT.json')
 require(g['passed']is False,'exploratory entry only handles recorded strict failure')
 require(set(g['checks'])==set(REQUIRED_CHECKS),'unexpected gate checks')
 require([k for k,v in g['checks'].items()if v is not True]==['original_input_pixels_tokens_positions_equal_R122'],'failure differs')
 require(g['condition_comparison']['strict_metadata_pixels_tokens_positions_equal']is False,'input mismatch missing')
 require(g['producer_seal_sha256']==c['producer_seal_sha256'] and g['runtime_profile_sha256']==c['runtime_sha256'],'producer binding differs')
 runtime=read(R/'configs/runtime.json');owner=started['owner']
 require(g['runtime_profile']==runtime and g['service_owner']==owner==release['owner'],'actual owner differs')
 require(owner['gpu_uuid']==runtime['gpu_uuid']and owner['port']==runtime['port']and owner['identity']['uid']==runtime['uid'],'runtime differs')
 require(release['passed']and release['process_absent']and release['CUDA_allocation_absent'],'release failed')
 require(set(g['runs'])=={'reference_origin'},'role differs');run=c['case']['run_id'];r=g['runs']['reference_origin']
 require(r['run_id']==run and r['valid_frames']==106 and r['evaluation_crop_xywh']==[16,8,1280,720],'domain differs')
 require(r['NFE']==r['Euler_updates']==20 and r['routed_blocks']==450 and r['original_rope_table_blocks']==1000,'counts differ')
 verify_prefix_diagnostics(g['prefix_comparison']);safe_path(r['video']['file'])
 D.mkdir(exist_ok=True);files={}
 for p in F.glob('*.json'):
  if not(D/p.name).exists():(D/p.name).write_bytes(p.read_bytes())
  require(sha(D/p.name)==sha(p),'original failure evidence changed');files[p.name]=sha(p)
 root=Path(c['producer_remote'])
 for index,(rel,h)in enumerate(r['binding_artifacts'].items()):
  if not rel.endswith('.json'):continue
  safe_path(root/rel);name=f'binding_{index:02d}.json';p=D/name
  if not p.exists():fetch(str(root/rel),p)
  require(sha(p)==h,'artifact digest differs');files[name]=h
  if rel.startswith('configs/graphs/'):graph=read(p)
  if rel.endswith('_history.json'):history=read(p)
  if rel.endswith('_job.json'):job=read(p)
  if rel.endswith('_noise.json'):noise=read(p)
 video=D/'reference_origin.mp4'
 if not video.exists():fetch(r['video']['file'],video)
 require(sha(video)==r['video']['sha256'],'media SHA differs');files[video.name]=sha(video)
 check_time(media_info(video,'/opt/homebrew/bin/ffprobe'),107,1312,736)
 require(graph==read(R/'configs/graphs'/f'{run}.json')and graph['5']['inputs']['prompt']==c['case']['prompt'],'actual graph differs')
 require(history['status']['completed']is True and history['status']['status_str']=='success'and history['prompt'][2]==graph,'actual history failed')
 require(history['prompt'][1]==job['prompt_id']and job['name']==run and job['status']=='success'and job['service_pid']==owner['pid']and job['service_identity']==owner['identity'],'job identity differs')
 entries=history['outputs']['14']['images'];require(len(entries)==1 and entries[0]['type']=='output','history output differs');e=entries[0]
 require(str(root/'output'/e.get('subfolder','')/e['filename'])==r['video']['file'],'history media path differs')
 parent=read(R/'design/r122_long_0039_seed2026101701_native_noise.json');require(noise['signature']==parent['signature']and noise['actual_noise_streams']==parent['actual_noise_streams'],'noise differs')
 p=D/'COLLECTION.json';save(p,dict(schema='r132-exploratory-intake-v1',media_integrity_passed=True,paired_input_exact=False,strict_producer_gate_passed=False,formal_COMPLETE_available=False,attempt='host41_reference_origin_attempt2',files=files,producer_seal_sha256=c['producer_seal_sha256'],consumer_freeze=bound(R/'CONSUMER_FREEZE.json'),intake_adapter=bound(Path(__file__)),valid_frames=106,total_frames=107,fps=24,crop_xywh=[16,8,1280,720],scope='Exploratory observation only; original failed historical decoded-input-pixel gate remains false. No formal paired claim or GPU scoring authorization.',created_unix=time.time()))
 return p

def render(collection):
 c=config();font=choose_font();source=Path(c['parent_media']['source']['file']);new=R/'incoming_exploratory/reference_origin.mp4';outputs=[]
 for prior,label in [('native','2.普通编辑'),('fixed','2.固定时序引导')]:
  dest=R/'showcase_exploratory'/('source_'+prior+'_reference_origin');inputs=[source,Path(c['parent_media'][prior]['file']),new]
  if not(dest/'PRESENTATION.json').exists():
   dest.mkdir(parents=True,exist_ok=True);render_pair.LABELS=('1.参考视频',label,'3.参考分支相位引导')
   media=render_pair.render_files(inputs,dest,107,106,font,'/opt/homebrew/bin/ffmpeg','/opt/homebrew/bin/ffprobe',rows=(6,12))
   save(dest/'PRESENTATION.json',dict(schema='r132-exploratory-three-column-v1',columns=['source',prior,'reference_origin'],comparison_kind='reference_origin_control',collection=bound(collection),paired_input_exact=False,strict_producer_gate_passed=False,inputs=[bound(p)for p in inputs],timeline=dict(fps=24,valid_frames=106,total_frames=107,crop_xywh=[16,8,1280,720]),original_task=c['case']['original_task'],method='450 fixed-step reference-branch phase interventions; original joint RoPE preserved',quality_review='PENDING',**media))
  outputs.append(bound(dest/'PRESENTATION.json'))
 pages=R/'audit/full106_exploratory_review';ledger=pages/'FRAME_LEDGER.json'
 if not ledger.exists():
  inputs=[source,Path(c['parent_media']['native']['file']),new];rows=full_frame_review.render_files(inputs,pages,107,106,font,'/opt/homebrew/bin/ffmpeg','/opt/homebrew/bin/ffprobe')
  save(ledger,dict(columns=['source','native','reference_origin'],all_frames_prepared=True,all_frames_inspected=False,paired_input_exact=False,strict_producer_gate_passed=False,valid_frames=106,fps=24,input_media=[bound(p)for p in inputs],collection=bound(collection),pages=rows,events=bound(R/'audit/EVENT_REVIEW_TEMPLATE.json'),evaluation_plan=bound(R/'audit/R132_EVALUATION_PLAN.json')))
 return dict(presentations=outputs,full_frame_ledger=bound(ledger),paired_input_exact=False,GPU_started=False)

if __name__=='__main__':print(json.dumps(render(collect()),ensure_ascii=False))
