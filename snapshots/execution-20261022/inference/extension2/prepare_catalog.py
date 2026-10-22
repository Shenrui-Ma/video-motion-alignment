"""Build a disjoint, outcome-blind extension. Only writes beside this script."""
import copy, hashlib, json, math, subprocess
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parent
RUN=ROOT.parents[1]
DEV=Path('/Users/researcher/DevProjects')
REMOTE='/home/researcher/h3_runs/benchmark_schedule_20261022_host9a'
INVENTORY=DEV/'h3-timing-auto-motion-r26-20261017/literature/benchmark_selection_20261017/IVE_FULL_600_INVENTORY.json'
TEMPLATE=RUN/'inference/host9a/graphs/expand_short_0353_native.json'
RAW_IDS=['short_0039','short_0185','short_0220','short_0308','short_0309','short_0318','short_0394','short_0395']

def read(p): return json.loads(Path(p).read_text())
def save(p,x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def probe(p):
 return json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,time_base,r_frame_rate,nb_frames,duration:frame=best_effort_timestamp','-show_frames','-of','json',str(p)]))

def main():
 expanded=read(RUN/'expanded_catalog.json'); excluded=set(expanded['excluded_primary_ive_ids'])|{t['task_id'] for t in expanded['tasks']}|{t['task_id'] for t in read(RUN/'task_catalog.json')['tasks']}
 metadata={Path(t['stable_id']).stem:t for t in read(INVENTORY)['items']}
 tasks=[]; transfers=[]
 for tid,dirname in [('short_0166','h3-timing-local-scene-r79-20261018'),('long_0174','h3-timing-ive-native-screen-r96-20261018')]:
  base=DEV/dirname; c=next(c for c in read(base/'configs/scientific_contract.json')['cases'] if c['source_id']==tid and c['arm']=='native')
  prov=read(base/'inputs'/f'{tid}_provenance.json'); source=base/'inputs'/c['video'];graph=base/'configs/graphs'/f'{c["run_id"]}.json'
  assert source.exists() and graph.exists()
  d={'task_id':tid,'reference_video':str(source),'reference_original':str(source),'graph_template':str(graph),'graph_sha256':sha(graph),'geometry':c['geometry'],'valid_frames':c['valid_frame_count'],'evaluation_crop_xywh':c['evaluation_crop_xywh'],'clip':c.get('clip',{'scope':'full_official_video'}),'input_to_original_frame':prov['input_to_original_frame'],'input_status':'existing_prepared','provenance_path':str(base/'inputs'/f'{tid}_provenance.json')}
  tasks.append(d);transfers.append({'task_id':tid,'kind':'prepared_video','local_path':str(source),'remote_path':REMOTE+'/input/expand2_'+tid+'_video.mp4','bytes':source.stat().st_size,'sha256':sha(source)})
 for tid in RAW_IDS:
  if tid in ['short_0309','short_0395']:
   source=DEV/'h3-ivebench-body-candidates-20261018/sources'/f'{tid}.mp4'
  else:
   group='ive_more_subject_sources_20261018' if tid in ['short_0039','short_0185'] else 'ive_identity_sources_20261018'
   source=DEV/'h3-timing-architecture-r2-20261016/audit'/group/'sources'/f'{tid}.mp4'
  p=probe(source); stream=p['streams'][0];timebase=Fraction(stream['time_base']); pts=[int(f['best_effort_timestamp'])*timebase for f in p['frames']]; pts=[v-pts[0] for v in pts]
  valid=math.ceil(pts[-1]*24)+1; total=17*math.ceil((valid-5)/17)+5
  mapping=[min(range(len(pts)),key=lambda k:(abs(pts[k]-Fraction(i,24)),k)) for i in range(valid)];mapping += [len(pts)-1]*(total-valid)
  d={'task_id':tid,'reference_video':REMOTE+'/input/expand2_'+tid+'_video.mp4','reference_original':str(source),'graph_template':str(TEMPLATE),'graph_sha256':sha(TEMPLATE),'geometry':{'width':1312,'height':736,'frames':total,'fps':24},'valid_frames':valid,'evaluation_crop_xywh':[16,8,1280,720],'clip':{'scope':'full_official_video','start_frame':0,'end_frame_inclusive':len(pts)-1,'original_frame_interval_half_open':[0,len(pts)]},'input_to_original_frame':mapping,'original_pts_rational':[str(v) for v in pts],'source_probe':stream,'input_status':'requires_remote_preparation','preparation_transform':'scale=1280:720:flags=lanczos,pad=1312:736:16:8:black,setsar=1','temporal_rule':'N=ceil(last original rational PTS*24)+1; nearest original PTS for each t/24, ties earlier; repeat final frame to minimum T=17k+5; exclude padded indices from evaluation.'}
  tasks.append(d);transfers.append({'task_id':tid,'kind':'official_original','local_path':str(source),'remote_path':REMOTE+'/extension2/sources/'+tid+'.mp4','bytes':source.stat().st_size,'sha256':sha(source)})
 jobs=[]
 for t in tasks:
  tid=t['task_id'];assert tid not in excluded
  official=metadata[tid]['metadata']
  t['official_asset']=metadata[tid]['official_asset']
  if t['input_status']=='requires_remote_preparation':
   assert next(v for v in transfers if v['task_id']==tid)['sha256']==t['official_asset']['lfs']['oid']
   t['official_source_sha256_verified']=True
  t.update(benchmark='IVEBench',title=official['edit_prompt'],selection_reason='Already downloaded source; subject replacement or clothing color edit; source/target metadata retain original action. Historical outcome, metric and review fields are not selection inputs.',original_task=official,evaluation_metadata={**official,'source_caption':official['source_prompt'],'edited_caption':official['target_prompt'],'editing_instruction':official['edit_prompt']},recommended_prompt=official['edit_prompt'],recommended_prompt_protocol='verbatim_official_edit_prompt',reference_image=None,seed=2026101701,fps=24,graph_input_names={'video':'expand2_'+tid+'_video.mp4','image':None},source_caption=official['source_prompt'],target_caption=official['target_prompt'],historical_outputs_not_reused=True,visual_inspection_performed=False,evaluation_crop_origin='inherited_1312x736_content_rectangle',assets_verified={'source':next(v for v in transfers if v['task_id']==tid)},evidence_paths=[str(INVENTORY),t['graph_template']])
  for method in ['native','global_weak']:
   g=read(TEMPLATE); jid='expand2_'+tid+'_'+method
   g['5']['inputs'].update(prompt=official['edit_prompt'],width=t['geometry']['width'],height=t['geometry']['height'],length=t['geometry']['frames'])
   g['22']['inputs']['file']=t['graph_input_names']['video'];g['6']['inputs']['noise_seed']=t['seed']
   g['50']['inputs'].update(mode='native' if method=='native' else 'mass_preserve',alpha=1.0 if method=='native' else .25,end_frame=t['valid_frames']-1,schedule=method)
   g['14']['inputs']['filename_prefix']=jid+'/{attempt_id}'
   save(ROOT/'graphs'/f'{jid}.json',g)
   jobs.append({'id':jid,'graph':f'graphs/{jid}.json','expected_output_prefix':jid+'/','progress_file':REMOTE+'/logs/comfy.log','metadata':{**t,'method':method,'timing_file':REMOTE+'/audit/timing/{attempt_id}.json','source_video':REMOTE+'/input/'+t['graph_input_names']['video'],'host':'H3_SERVER_A','remote_root':REMOTE,'steps':20}})
 catalog={'schema':'h3-expanded-ive-catalog-v1','created_date':'2026-10-22','count':len(tasks),'selection_uses_observed_method_effect':False,'excluded_ids':sorted(excluded),'task_order':[t['task_id'] for t in tasks],'tasks':tasks,'protocol':{'seed':2026101701,'steps':20,'sampler':'euler','prompt':'verbatim official edit_prompt','methods':['native','global_weak'],'weak_alpha':.25,'weak_steps':[0,20],'blocks':[0,50],'geometry':'Reuse prepared inputs or inherited 1280x720 content padded to 1312x736; 24fps nearest PTS, final-frame padding to 17k+5','visual_review':False}}
 save(ROOT/'catalog.json',catalog);save(ROOT/'jobs_append.json',{'jobs':jobs});save(ROOT/'jobs_append_ready.json',{'jobs':jobs[:4]});save(ROOT/'assets_to_transfer.json',{'remote_root':REMOTE,'files':transfers,'total_bytes':sum(t['bytes'] for t in transfers),'note':'Reference original files in place; no local video copies. Prepared inputs first; original inputs require prepare_remote_inputs.py.'})
 print(json.dumps({'tasks':len(tasks),'jobs':len(jobs),'ready_jobs':4,'transfer_bytes':sum(t['bytes'] for t in transfers),'geometry':{t['task_id']:[t['geometry']['frames'],t['valid_frames']] for t in tasks}},indent=2))
if __name__=='__main__': main()
