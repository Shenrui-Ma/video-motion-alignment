"""Bind one completed field execution; requires observed backend counts and exact output."""
from pathlib import Path
import hashlib,json,math
from field_audit import check_field,check_layer

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def first_forward(doc):
 forwards=doc.get('feature_forward_summaries',[])
 first=next((x['layers'] for x in forwards if x['forward']==0),[])
 if len(first)<50:return None
 assert len(first)==50 and {x['block'] for x in first}==set(range(50))
 for row in first:
  check_layer(row)
  assert all(abs(a-.25)<=1e-7 for a in row['alpha']),'first-forward anchor must use alpha prior .25'
 return {'forward':0,'blocks':50,'finite':True,'alpha_min':min(min(x['alpha']) for x in first),'alpha_max':max(max(x['alpha']) for x in first)}

def backend_check(d,pid,complete):
 assert d['pid']==pid and not d['logging_errors']
 ops=d['operations'];assert set(ops)=={b+'.'+o for b in ['cuda','triton','eager'] for o in ['int8_linear','w4a8_int8_linear']};t=ops['triton.int8_linear'];assert t['registry_resolves_wrapper'] and t['failed_calls']==0
 assert t['successful_calls']>0
 if complete:assert t['attempted_calls']==t['successful_calls']==4000
 for k,v in ops.items():
  assert v['failed_calls']==0,k
  if k!='triton.int8_linear':assert v['attempted_calls']==0,k
 return {k:{x:v[x] for x in ('attempted_calls','successful_calls','failed_calls')} for k,v in ops.items()}

def bind(root,history,record,assets):
 root=Path(root);job=json.loads((root/'jobs.json').read_text())['jobs'][0];tid=job['id'];g=root/job['graph']
 assert history['status']['completed'] is True and history['status']['status_str']=='success'
 assert history['prompt'][2]==json.loads(g.read_text())
 a=root/'audit/feature_gain_field'/(tid+'.json');d=json.loads(a.read_text());summary=check_field(d)
 t=root/'audit/timing'/(tid+'.json');timing=json.loads(t.read_text());seconds=timing['sampler_wall_seconds'];assert math.isfinite(seconds) and seconds>0 and len(timing['steps'])==20
 outputs=[(root/'output'/v.get('subfolder','')/v['filename']).resolve() for n in history['outputs'].values() for v in n.get('images',[]) if v.get('type')=='output' and v['filename'].endswith('.mp4')]
 assert len(outputs)==1;video=outputs[0];assert video.is_relative_to((root/'output'/tid).resolve()) and video.stat().st_size>0
 backend=root/'logs/backend_dispatch_audit.json';b=json.loads(backend.read_text());counts=backend_check(b,record['pid'],True)
 peaks=[]
 for p in (root/'audit/memory').glob('*.json'):
  if str(record['pid']) in p.stem:peaks.append({'path':str(p),'sha256':sha(p),'data':json.loads(p.read_text())})
 assert peaks,'own process memory audit missing'
 for path,h in assets.items():assert sha(root/path)==h,path
 return {'schema':'h3-field-environment-trajectory-gate-v1','passed':True,'cohort':'field_environment_reproduction','case':'short_0358','method':'temporal_gain_field','job_id':tid,'actual_model_forward_count':20,'completed_blocks':1000,'graph_sha256':sha(g),'field_audit_file':str(a),'field_audit_sha256':sha(a),'field_summary':summary,'actual_video_file':str(video),'actual_video_sha256':sha(video),'actual_video_bytes':video.stat().st_size,'sampling_seconds':seconds,'mean_sampling_step_seconds':seconds/20,'timing_file':str(t),'timing_sha256':sha(t),'backend_file':str(backend),'backend_sha256':sha(backend),'observed_backend_counts':counts,'memory_peak_records':peaks,'runtime_assets':assets}


def verify_inputs(root):
 root=Path(root);identity=json.loads((root/'INPUT_IDENTITY.json').read_text());g=json.loads((root/'graphs/temporal_gain_field_graph.json').read_text())
 assert sha(g['5']['inputs']['cache_manifest'])==identity['cache_manifest_sha256']
 for p in identity['payloads']:assert sha(p['path'])==p['sha256'],p['path']
 assert sha(g['6']['inputs']['noise_file'])==identity['noise_file_sha256']
 for p,h in identity['core_source_shas'].items():assert sha(root.parent/'core'/p)==h,p
 model=identity['model_current_stat_matches_full_sha'];st=Path(model['path']).stat()
 assert (st.st_ino,st.st_mtime_ns,st.st_size)==(model['inode'],model['mtime_ns'],model['bytes']), 'checkpoint changed since full SHA'
 return True
