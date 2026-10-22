"""Bind reviewed new materials into isolated four-job lanes; never starts services."""
import argparse,json,shutil,subprocess
from fractions import Fraction
from pathlib import Path
from r24_contract import ROOT,REMOTE_BASE,SEEDS,ARMS,sha,case_check,run_name,expected_graph

def write(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')

def video_probe(path):
 result=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames','-of','json',str(path)],capture_output=True,text=True,check=True)
 streams=json.loads(result.stdout)['streams']
 if len(streams)!=1:raise ValueError('one video stream required')
 z=streams[0]
 if int(z['nb_read_frames'])!=141 or Fraction(z['avg_frame_rate'])!=24:raise ValueError('new source must be frozen 141RGB frames at24fps before binding; event window uses this exact timeline')
 return z

def bind_case(source,lane_root,scaffold=ROOT):
 lane_root=Path(lane_root);scaffold=Path(scaffold)
 if lane_root.exists():raise FileExistsError('Never overwrite existing lane: '+str(lane_root))
 lane=source['lane']
 if lane not in ('a','b'):raise ValueError('lane must be a or b')
 case={'case_id':source['case_id'],'prompt':source['prompt'],'primary_window_inclusive':source['primary_window_inclusive'],'new_to_study_attestation':source['new_to_study_attestation']}
 files={}
 for key,field in [('video','video_file'),('portrait','portrait_file'),('provenance','source_provenance_file')]:
  p=Path(source[field]).resolve(strict=True)
  if not p.is_file():raise ValueError('not a file: '+str(p))
  actual=sha(p)
  if key!='provenance' and source[key+'_sha256']!=actual:raise ValueError('supplied '+key+' SHA mismatch')
  case[key]=case['case_id']+'_'+key+p.suffix.lower();case[key+'_sha256']=actual;files[key]=p
 case_check(case)
 probe=video_probe(files['video'])
 lane_root.mkdir(parents=True)
 for folder in ('scripts','extensions','tests'):
  shutil.copytree(scaffold/folder,lane_root/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 (lane_root/'configs').mkdir();(lane_root/'inputs').mkdir();(lane_root/'audit').mkdir()
 for name in ('graph_template.json','scientific_contract.json','original_extension_hashes.json','parent_core_hashes.json','model_hashes_host9.json','parent_runtime_provenance.json','backend_reuse_manifest.json'):
  shutil.copy2(scaffold/'configs'/name,lane_root/'configs'/name)
 runtime={'lane':lane,'remote_root':str(REMOTE_BASE/lane),'gpu_uuid':source.get('gpu_uuid',{'a':'GPU-REDACTED','b':'GPU-REDACTED'}[lane]),'port':source.get('port',{'a':8484,'b':8485}[lane]),'resource_assignment':'candidate; root live admission required'}
 write(lane_root/'configs/runtime.json',runtime)
 for key,p in files.items():shutil.copy2(p,lane_root/'inputs'/case[key])
 jobs={}
 for seed in SEEDS:
  for arm in ARMS:
   run=run_name(case,seed,arm);p=lane_root/'configs/graphs'/f'{run}.json'
   write(p,expected_graph(lane_root,case,seed,arm));jobs[run]={'seed':seed,'arm':arm,'graph_sha256':sha(p)}
 write(lane_root/'configs/job_registry.json',{'root_approved':True,'case':case,'jobs':jobs})
 write(lane_root/'configs/queue.json',{'jobs':list(jobs),'approved_continuations':[],'finalize':False})
 write(lane_root/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
 write(lane_root/'audit/source_binding.json',{'case':case,'prepared_video_probe':probe,'event_timebase':'zero-based RGB frames of this frozen141frame24fps video','source_manifest_entry':source,'scientific_contract_sha256':sha(lane_root/'configs/scientific_contract.json'),'scope':'material binding only; no inference or launch'})
 return {'lane':lane,'local_root':str(lane_root),'runtime':runtime,'case':case,'jobs':list(jobs)}

def bind_manifest(path,scaffold=ROOT):
 data=json.loads(Path(path).read_text())
 if data.get('approved_for_binding') is not True:raise ValueError('material review approval missing')
 if [c['lane'] for c in data['cases']]!=['a','b'] or len({c['case_id'] for c in data['cases']})!=2:raise ValueError('exactly two distinct source lanes required')
 if len({c['video_sha256'] for c in data['cases']})!=2:raise ValueError('two lanes cannot share the same video bytes')
 targets=[Path(scaffold)/'lanes'/c['lane'] for c in data['cases']]
 if any(p.exists() for p in targets):raise FileExistsError('one or more lanes already exist')
 return [bind_case(c,p,scaffold) for c,p in zip(data['cases'],targets)]
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('manifest',type=Path);a=p.parse_args();print(json.dumps(bind_manifest(a.manifest),indent=2))
