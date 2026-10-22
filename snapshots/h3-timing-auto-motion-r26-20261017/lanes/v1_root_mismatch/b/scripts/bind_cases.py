"""Bind three source-only selected clips into two Native lanes; no service launch."""
import argparse,json,shutil,subprocess
from fractions import Fraction
from pathlib import Path
from r26_contract import ROOT,REMOTE_BASE,SEEDS,ARMS,sha,case_check,run_name,expected_graph

LANES={'a':['40372','51304'],'b':['51317']}
PORTS={'a':8488,'b':8489}
GPUS={'a':'GPU-REDACTED','b':'GPU-REDACTED'}
def write(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def video_probe(path):
 r=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames','-of','json',str(path)],capture_output=True,text=True,check=True)
 streams=json.loads(r.stdout)['streams']
 if len(streams)!=1:raise ValueError('one video stream required')
 z=streams[0]
 if (int(z['width']),int(z['height']),int(z['nb_read_frames']),Fraction(z['avg_frame_rate']))!=(1312,736,141,24):raise ValueError('frozen source geometry/rate must be 1312x736x141@24')
 return z

def bind_case(source,lane_root,scaffold=ROOT,*,append=False):
 lane_root=Path(lane_root);scaffold=Path(scaffold);lane=source['lane']
 if lane not in LANES:raise ValueError('lane must be a or b')
 if lane_root.exists() and not append:raise FileExistsError('Never overwrite existing lane: '+str(lane_root))
 case={'case_id':source['case_id'],'source_id':source['source_id'],'prompt':source['prompt'],'primary_window_inclusive':[0,140],'new_to_study_attestation':source['new_to_study_attestation'],'window_semantics':'unused full-clip Native interface metadata; no supplied action window'}
 files={}
 for key,field in [('video','video_file'),('portrait','portrait_file'),('provenance','source_provenance_file')]:
  p=Path(source[field]).resolve(strict=True)
  if not p.is_file():raise ValueError('not a file: '+str(p))
  actual=sha(p)
  if source[key+'_sha256']!=actual:raise ValueError('supplied '+key+' SHA mismatch')
  case[key]=case['case_id']+'_'+key+p.suffix.lower();case[key+'_sha256']=actual;files[key]=p
 case_check(case);probe=video_probe(files['video'])
 if not append:
  lane_root.mkdir(parents=True)
  for folder in ('scripts','extensions','tests'):shutil.copytree(scaffold/folder,lane_root/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
  for folder in ('configs','inputs','audit'):(lane_root/folder).mkdir()
  configs=scaffold/'configs/runtime_templates'
  if not configs.exists():configs=scaffold/'configs'
  for p in configs.glob('*.json'):shutil.copy2(p,lane_root/'configs'/p.name)
  runtime={'lane':lane,'remote_root':str(REMOTE_BASE/lane),'gpu_uuid':GPUS[lane],'port':PORTS[lane],'resource_assignment':'candidate; root live admission required'}
  write(lane_root/'configs/runtime.json',runtime)
  write(lane_root/'configs/queue.json',{'jobs':[],'approved_continuations':[],'finalize':False})
  write(lane_root/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
 else:
  runtime=json.loads((lane_root/'configs/runtime.json').read_text())
  if runtime['lane']!=lane:raise ValueError('append lane mismatch')
  if (lane_root/'deploy_manifest.json').exists():raise ValueError('initial binding cannot append after seal')
 for key,p in files.items():
  dst=lane_root/'inputs'/case[key]
  if dst.exists():raise FileExistsError('asset collision')
  shutil.copy2(p,dst)
 jobs={}
 for seed in SEEDS:
  for arm in ARMS:
   run=run_name(case,seed,arm);p=lane_root/'configs/graphs'/f'{run}.json'
   write(p,expected_graph(lane_root,case,seed,arm));jobs[run]={'seed':seed,'arm':arm,'graph_sha256':sha(p)}
 batch={'root_approved':True,'approval_basis':'root authorized three fixed Native source screens; source selection protocol frozen before outputs','case':case,'jobs':jobs}
 q=json.loads((lane_root/'configs/queue.json').read_text())
 if append:
  rel='configs/approved_continuations/'+case['case_id']+'.json';write(lane_root/rel,batch);q['approved_continuations'].append({'file':rel,'sha256':sha(lane_root/rel)})
 else:write(lane_root/'configs/job_registry.json',batch)
 q['jobs'].extend(jobs);write(lane_root/'configs/queue.json',q)
 write(lane_root/'audit'/('source_binding_'+case['case_id']+'.json'),{'case':case,'prepared_video_probe':probe,'timebase':'zero-based selected RGB frames0..140 at24fps; source mapping in immutable provenance','source_manifest_entry':source,'scientific_contract_sha256':sha(lane_root/'configs/scientific_contract.json'),'scope':'material binding only; no inference or launch'})
 return {'lane':lane,'local_root':str(lane_root),'runtime':runtime,'case':case,'jobs':list(jobs)}

def bind_manifest(path,scaffold=ROOT):
 data=json.loads(Path(path).read_text())
 if data.get('approved_for_binding') is not True:raise ValueError('material review approval missing')
 cases=data['cases']
 if [str(c['source_id']) for c in cases]!=['40372','51304','51317'] or [c['lane'] for c in cases]!=['a','a','b']:raise ValueError('exact predeclared three-source lane order required')
 if len({c['case_id'] for c in cases})!=3 or len({c['video_sha256'] for c in cases})!=3:raise ValueError('three distinct source IDs and video bytes required')
 science=json.loads((Path(scaffold)/'configs/runtime_templates/scientific_contract.json').read_text())
 if any(c['prompt']!=science['prompt'] or c['portrait_sha256']!=science['portrait_sha256'] for c in cases):raise ValueError('frozen R24 Sam identity/prompt changed')
 if any((Path(scaffold)/'lanes'/lane).exists() for lane in LANES):raise FileExistsError('existing lanes preserved')
 results=[bind_case(c,Path(scaffold)/'lanes'/c['lane'],scaffold,append=(i==1)) for i,c in enumerate(cases)]
 for lane,ids in LANES.items():write(Path(scaffold)/'lanes'/lane/'configs/native_screen.json',{'source_ids':ids,'seed':2026101701,'arm':'native','capture_indices':list(range(20)),'material_manifest_sha256':sha(path),'append_after_seal':False,'prompt':science['prompt'],'portrait_sha256':science['portrait_sha256']})
 return results
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('manifest',type=Path);a=p.parse_args();print(json.dumps(bind_manifest(a.manifest),indent=2))
