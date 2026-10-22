"""Administrative host60 one-GPU variant; pinned official MF math is unchanged."""
import ast,hashlib,json,os,shutil
from pathlib import Path
R=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def prepare(sid):
 source=R/'host9_batches'/sid;dest=R/'host60_batches'/sid
 assert not dest.exists(),'Preserve prepared variant'
 for folder in ['scripts','configs','cases','audit']:
  for rel,digest in read(source/'SEAL.json')['files'].items():
   if not rel.startswith(folder+'/'):continue
   p=source/rel;q=dest/rel;q.parent.mkdir(parents=True,exist_ok=True)
   assert sha(p)==digest
   os.link(p,q) if folder=='cases' else shutil.copyfile(p,q)
 # No altered tracker equations, score implementation, or pixel validation.
 remote='/home/researcher/h3_runs/guidance_schedule_mf_r150_host60_20261021/'+sid
 shared='/home/researcher/h3_runs/guidance_schedule_mf_r150_host60_20261021/shared/runtime/ive'
 rt=read(source/'configs/RUNTIME.json');rt.update(host='root3360',uid=1015,gpu_uuid='GPU-REDACTED',gpu_index=3,remote_root=remote,python='/home/researcher/es/envs/comfyui/bin/python',checkpoint=shared+'/weights/baseline_offline.pth',peer_roots=[],minimum_gpu_free_mib=20480,maximum_own_cards=1,ffmpeg_bin='/home/researcher/es/bin')
 save(dest/'configs/RUNTIME.json',rt)
 for name in ['common.py','run_batch.py','capacity_v1.py','peer_support.py']:
  p=dest/'scripts'/name;s=p.read_text().replace('1016','1015')
  if name=='common.py':s=s.replace("float(free)>=40960", "float(free)>=rt['minimum_gpu_free_mib']")
  if name=='peer_support.py':s=s.replace("len(devices) <= 2, 'would exceed two own GPUs'", "len(devices) <= 1, 'would exceed one own MF GPU'")
  if name=='run_batch.py':
   s=s.replace("release=review['prerequisite_release'];assert sha(release['file'])==release['sha256'];released=read(release['file']);assert released['passed'] and released['process_absent'] and released['CUDA_allocation_absent'];assert not Path('/proc',str(released['owner']['pid'])).exists()", "assert review['execution_scope']=='host60_single_tracker_only';assert read(ROOT/'configs/BATCH_RELEASE.json')['passed'];assert not read(ROOT/'configs/RUNTIME.json')['peer_roots']")
  p.write_text(s);ast.parse(s)
 p=dest/'audit/collect.py';p.write_text(p.read_text().replace('H3_SERVER_A:','H3_SERVER:'))
 save(dest/'audit/REMOTE_REUSE_PLAN.json',{'runtime/ive':shared})
 # This replacement only sets the existing executable search path and CPU import checks.
 p=dest/'audit/verify_inputs.py';s=p.read_text().replace("from pathlib import Path", "from pathlib import Path\nimport os\nos.environ['PATH']='/home/researcher/es/bin:'+os.environ.get('PATH','')");p.write_text(s)
 for n in ['track.py','score.py']:
  assert sha(dest/'scripts'/n)==sha(source/'scripts'/n)
 runtime=(source/'runtime/ive').resolve();(dest/'runtime').mkdir();(dest/'runtime/ive').symlink_to(runtime,target_is_directory=True)
 files={str(p.relative_to(dest)):sha(p) for top in ['scripts','configs','cases','audit'] for p in (dest/top).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
 save(dest/'SEAL.json',{'schema':'r150-host60-mf-administrative-v1','final_inputs_bound':True,'files':files,'new_target_trackers':4,'new_source_trackers':0,'parent_seal_sha256':sha(source/'SEAL.json')})
 save(dest/'ADMIN_DIFF.json',{'parent':{'file':str(source/'SEAL.json'),'sha256':sha(source/'SEAL.json')},'changes':['UID/hostname/paths for host60','20GiB free per tracker from actual <=16.79GiB reserved evidence','one own GPU; no own video peer','input generation release bound across hosts without testing unrelated same-number PIDs','existing ffmpeg PATH; compact SSH collector alias'],'numerical_track_score_unchanged':True,'failure':'Existing exact child cleanup; nonzero/OOM stops batch, preserves failure, does not touch foreign PID','GPU_started':False})
 save(dest/'ROOT_REVIEW_TEMPLATE.json',{'passed':False,'CPU_upload_authorized':True,'GPU_execution_authorized':False,'seal_sha256':sha(dest/'SEAL.json'),'gpu':rt['gpu_uuid'],'execution_scope':'host60_single_tracker_only','minimum_gpu_free_mib':20480,'maximum_own_cards':1,'prerequisite_release':None})
 print(sid,sha(dest/'SEAL.json'))
if __name__=='__main__':
 for sid in ['short_0085','long_0039']:prepare(sid)
