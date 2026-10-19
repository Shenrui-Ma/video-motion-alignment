"""R25 CPU-only postrun intake; adapted from the reviewed R24 consumer.
Writes only the parent analysis/postrun directory; never submits or stops jobs.
"""
import argparse,fcntl,hashlib,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
BASE=Path('/data5/researcher/h3_runs/timing_reverse_reference_r25_20261017')
HERE=BASE/'analysis/postrun'
OLD=Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')
HASHES={'scripts/pose_probe.py':'04c6dd432ddf102300a4cd065f4de8b9c2bc0661ce1abb06d994330b32ae693f','scripts/timing_metrics.py':'eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e','analysis/pose/compare_runs.py':'1e725cd5063ae9e9e770f94c54c91dfa5d0473e951e92dfcebaa56619c844b33'}
WINDOWS=[[50,65],[69,81],[80,92],[99,111]]
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');t.replace(p)
def require(x,message):
 if not x:raise ValueError(message)
def safe(root,rel):
 p=Path(rel);require(not p.is_absolute() and '..' not in p.parts,'unsafe path');x=root/p
 require(not x.is_symlink() and x.resolve().is_relative_to(root.resolve()),'symlink/outside path');return x
def bound(lane):
 b=read(HERE/'BINDING.json')['lanes'][lane];root=BASE/lane
 require(str(root)==b['remote_root'],'remote root changed')
 require(sha(root/'deploy_manifest.json')==b['manifest_sha256'],'manifest changed')
 owner=read(root/'processes/service.json');require(owner==b['service_record'],'service record generation changed')
 proc=Path('/proc')/str(owner['pid'])
 if proc.exists():
  try:st=(proc/'stat').read_text().split(') ',1)[1].split();uid=proc.stat().st_uid;cmd=(proc/'cmdline').read_bytes()
  except FileNotFoundError:require(not proc.exists(),'partial live identity read')
  else:
   e=b['external_identity'];require(uid==e['uid'] and st[19]==e['start_ticks'],'live PID identity changed')
   if st[0]!='Z':require(hashlib.sha256(cmd).hexdigest()==e['cmdline_sha256'],'live command changed')
 return root,b,owner
def output_file(root,h,run):
 xs=h.get('outputs',{}).get('14',{}).get('images',[]);require(len(xs)==1,'one output required');x=xs[0]
 require(x['type']=='output' and x.get('subfolder','')=='' and re.fullmatch(re.escape(run)+r'_\d+_\.mp4',x['filename']),'output identity/path')
 return safe(root,'output/'+x['filename'])
def inventory(root,run):
 h=read(root/'logs'/f'{run}_history.json');j=read(root/'logs'/f'{run}_job.json')
 require(h['status']['completed'] is True and h['status']['status_str']=='success' and j['status']=='success','not successful')
 g=read(root/'configs/graphs'/f'{run}.json');m=read(root/'audit/x0'/run/'manifest.json')
 require(m['status']=='complete','capture incomplete')
 names=[f'x0_step{i:03d}.pt' for i in (5,6,7,8,9,10,15,19)]+['sampler_final.pt']
 require([x['file'] for x in m['captures']+[m['final_sampler_result']]]==names,'capture manifest inventory')
 require(sorted(p.name for p in (root/'audit/x0'/run).glob('*.pt'))==sorted(names),'actual capture inventory')
 shared=g['5']['inputs']['run_id']+'_conditioning.json';n=read(root/'audit'/f'{run}_noise.json')
 rels={f'logs/{run}_history.json',f'logs/{run}_job.json',f'configs/graphs/{run}.json',f'audit/{run}_conditioning.json',f'audit/{run}_noise.json',f'audit/router/{run}.json',f'audit/{shared}',f'audit/{n["pair_id"]}_noise.pt',f'audit/x0/{run}/manifest.json','configs/runtime.json','configs/runtime_provenance.json','configs/admission.json','processes/service.json','deploy_manifest.json'}
 rels.update(f'audit/x0/{run}/'+n for n in names)
 router=read(root/'audit/router'/f'{run}.json')
 for f in router['native_feature_captures']:rels.add(f'audit/native_features/{run}/'+Path(f['file']).name if 'file' in f else f'audit/native_features/{run}/block25_step{f["metadata"]["forward_index"]:03d}.pt')
 def visit(v):
  if isinstance(v,dict):
   if 'tensor_file' in v and {'shape','dtype','sha256'}<=set(v):rels.add('audit/'+v['tensor_file'])
   for z in v.values():visit(z)
  elif isinstance(v,list):
   for z in v:visit(z)
 visit(read(root/'audit'/shared));rels.add(str(output_file(root,h,run).relative_to(root)))
 paths=[safe(root,r) for r in sorted(rels)];require(all(p.is_file() for p in paths),'completed file missing');return paths
def snapshot(lane):
 root,b,owner=bound(lane);run=b['run_id'];hp=root/'logs'/f'{run}_history.json';jp=root/'logs'/f'{run}_job.json'
 h=read(hp) if hp.exists() else {};j=read(jp) if jp.exists() else {};cp=root/'logs/controller_state.json';c=read(cp) if cp.exists() else {}
 terminal=c.get('status') in ('failed','final_close','bounded_idle_expired')
 if h.get('status',{}).get('status_str')=='error' or j.get('status') in ('error','unknown_missing','submission_uncertain'):return {'status':'failed','run':run,'history':h.get('status'),'job':j}
 if not(h.get('status',{}).get('completed') and h['status'].get('status_str')=='success' and j.get('status')=='success'):return {'status':'failed' if terminal else 'pending','run':run,'controller':c}
 try:
  paths=inventory(root,run);rows=[{'path':str(p.relative_to(root)),'size':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns,'json_sha256':sha(p) if p.suffix=='.json' else None} for p in paths]
  return {'status':'success_files_present','run':run,'stability_token':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),'files':len(rows),'controller':c}
 except (FileNotFoundError,KeyError) as e:return {'status':'failed' if terminal else 'completion_files_pending','run':run,'error':str(e)}
def locked():
 f=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);return f
def env():
 e=os.environ.copy();e.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4');return e
def launch(cmd,log):
 with Path(log).open('w') as f:return subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,env=env())
def check_frozen():
 b=read(HERE/'BINDING.json');source=Path(b['source_pose']);require(sha(source)==b['source_pose_sha256'] and read(source)['video']['sha256']==b['source_video_sha256'],'source pose binding')
 for rel,want in HASHES.items():require(sha(OLD/rel)==want,'metric changed '+rel)
 for p in b['parents'].values():require(sha(p['pose'])==p['pose_sha256'] and read(p['pose'])['video']['sha256']==p['video_sha256'],'parent pose binding')
 return b,source
def compact(arc):
 result={}
 for conf in (.3,.5):
  paths=list((arc/'timing'/str(conf)).glob('*.timing.json'))
  if not paths:result[str(conf)]={'status':'UNKNOWN'};continue
  rows=read(paths[0])['diagnostics'];require(len(rows)==20 and all(len(r['curve'])==49 for r in rows),'frozen20x49 curves')
  result[str(conf)]=[{k:r.get(k) for k in ('window','feature','status','flags','reliable_lag_frames')}|{'same_frame_error':r['same_frame']['error'],'same_frame_coverage':r['same_frame']['coverage'],'best_error':r['best']['error'] if r['best'] else None} for r in rows]
 save(arc/'COMPACT_RESULTS.json',result);return result
def consume(lane,token):
 lock=locked();start=time.time();root,b,owner=bound(lane);run=b['run_id'];require(snapshot(lane)['stability_token']==token,'files changed after stable observation')
 for rel,e in read(root/'deploy_manifest.json')['files'].items():require(sha(safe(root,rel))==e['sha256'],'sealed file changed '+rel)
 binding,source=check_frozen();arc=HERE/'captured'/run
 if (arc/'CPU_COMPLETE.json').exists():
  done=read(arc/'CPU_COMPLETE.json');require(done['passed'] and read(arc/'RUN_GATE.json')['passed'],'bad existing completion')
  require(all(sha(safe(root,k))==sha(safe(arc,k))==v['sha256'] for k,v in read(arc/'FILE_INVENTORY.json').items()),'existing archive/source changed');return done
 require(not arc.exists(),'incomplete archive; inspect before retry');arc.mkdir(parents=True)
 paths=inventory(root,run);before={str(p.relative_to(root)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in paths}
 p=launch([sys.executable,str(root/'scripts/verify_completed.py'),'--root',str(root),'--parent-root',binding['parent_root'],'--output',str(arc/'RUN_GATE.json')],arc/'verify.log')
 require(p.returncode==0 and read(arc/'RUN_GATE.json')['passed'],'sealed actual verifier failed; see retained log')
 for src in paths:
  rel=str(src.relative_to(root));dst=safe(arc,rel);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst);require(sha(dst)==before[rel]['sha256']==sha(src),'copy/source changed')
 save(arc/'FILE_INVENTORY.json',before)
 h=read(arc/'logs'/f'{run}_history.json');video=output_file(arc,h,run)
 import cv2
 cv2.setNumThreads(1);cap=cv2.VideoCapture(str(video));geo=[int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),cap.get(cv2.CAP_PROP_FPS)];cap.release();require(geo==[1312,736,141,24.0],'formal MP4 geometry')
 cmd=[sys.executable,str(OLD/'scripts/pose_probe.py'),'--video',str(video),'--output-dir',str(arc/'pose'),'--threads','4']
 for f in (55,86,105):cmd+=['--overlay-frame',str(f)]
 p=launch(cmd,arc/'pose_extract.log');require(p.returncode==0,'pose extractor execution error; output retained')
 pp=arc/'pose'/(video.stem+'.pose.json');raw=read(pp);require(raw['video']['sha256']==sha(video) and raw['statistics']['processed_frames']==141 and [r['frame'] for r in raw['frames']]==list(range(141)),'pose input/frame binding')
 sp=read(source)['provenance']
 for k in ('detector_sha256','pose_sha256','detector_code_sha256','pose_code_sha256','script_sha256'):require(raw['provenance'][k]==sp[k],'pose provenance '+k)
 unknown={}
 for conf in (.3,.5):
  cmd=[sys.executable,str(OLD/'scripts/timing_metrics.py'),'--source',str(source),'--edited',str(pp),'--confidence',str(conf),'--max-lag','24','--output-dir',str(arc/'timing'/str(conf))]
  for w in WINDOWS:cmd+=['--window',':'.join(map(str,w))]
  p=launch(cmd,arc/f'timing_{conf}.log')
  if p.returncode:
   if 'Insufficient reliable torso anchors for scale normalization' in (arc/f'timing_{conf}.log').read_text():unknown[str(conf)]='UNKNOWN: frozen evaluator lacks torso anchors'
   else:raise RuntimeError('timing evaluator error; retained log')
 require(all(sha(safe(root,k))==sha(safe(arc,k))==v['sha256'] for k,v in before.items()),'source/archive changed after CPU')
 summary=compact(arc);done={'passed':True,'run_id':run,'video':str(video),'video_sha256':sha(video),'pose':str(pp),'pose_sha256':sha(pp),'source_pose_sha256':sha(source),'elapsed_seconds':time.time()-start,'timing_unavailable':unknown,'no_GPU':True,'pose_device':raw['provenance']['device'],'pose_providers':raw['provenance']['providers'],'NFE':20,'eligible_routes':450,'cleanup_claim':False};save(arc/'CPU_COMPLETE.json',done);return done
def compare():
 lock=locked();b,source=check_frozen();runs={k:v['pose'] for k,v in b['parents'].items()};dest=HERE/'comparison';dest.mkdir(exist_ok=True);checks={}
 records=[]
 for lane,z in b['lanes'].items():
  root,_,_=bound(lane);arc=HERE/'captured'/z['run_id'];require(read(arc/'CPU_COMPLETE.json')['passed'] and read(arc/'RUN_GATE.json')['passed'],'arm incomplete')
  require(all(sha(safe(root,k))==sha(safe(arc,k))==v['sha256'] for k,v in read(arc/'FILE_INVENTORY.json').items()),'arm archive/source changed')
  runs[lane]=read(arc/'CPU_COMPLETE.json')['pose'];records.append((arc,read(arc/'audit'/f'{z["run_id"]}_conditioning.json'),read(arc/'audit'/f'{z["run_id"]}_noise.json')))
 checks['both_conditions_equal']=records[0][1]['pair_snapshot']['actual']==records[1][1]['pair_snapshot']['actual']
 checks['both_noise_equal']=all(records[0][2][k]==records[1][2][k] for k in ('signature','actual_noise_streams'))
 require(all(checks.values()),'reverse arms actual pairing mismatch')
 descriptions=WINDOWS+[[0,140],[0,46],[47,67],[68,140],[112,140]];unknown={}
 for subset in (list(runs),['native','full','reverse_block'],['native','full','reverse_same']):
  name='__'.join(subset)
  for conf in (.3,.5):
   cmd=[sys.executable,str(OLD/'analysis/pose/compare_runs.py'),'--source',str(source),'--confidence',str(conf),'--output',str(dest/f'{name}_{conf}.json')]
   for label in subset:cmd+=['--run',label+'='+runs[label]]
   for w in descriptions:cmd+=['--window',':'.join(map(str,w))]
   p=launch(cmd,dest/f'{name}_{conf}.log')
   if p.returncode:
    if 'Insufficient reliable torso anchors for scale normalization' in (dest/f'{name}_{conf}.log').read_text():unknown[name+str(conf)]='UNKNOWN: frozen torso scale unavailable'
    else:raise RuntimeError('common-support evaluator error')
 result={'passed':True,'checks':checks,'source_pose_sha256':sha(source),'pose_hashes':{k:sha(v) for k,v in runs.items()},'windows':WINDOWS,'descriptive_windows':descriptions[4:],'unknown':unknown,'no_cleanup_claim':True};save(dest/'COMPARISON_COMPLETE.json',result)
 save(dest/'FILES.json',{p.name:sha(p) for p in dest.iterdir() if p.is_file() and p.name!='FILES.json'});return result
def main():
 a=argparse.ArgumentParser();a.add_argument('mode',choices=['snapshot','consume','compare']);a.add_argument('--lane',choices=['reverse_block','reverse_same']);a.add_argument('--token');x=a.parse_args()
 try:r=snapshot(x.lane) if x.mode=='snapshot' else consume(x.lane,x.token) if x.mode=='consume' else compare()
 except BlockingIOError:print('CPU_LOCK_BUSY');raise SystemExit(75)
 print(json.dumps(r,allow_nan=False))
if __name__=='__main__':main()
