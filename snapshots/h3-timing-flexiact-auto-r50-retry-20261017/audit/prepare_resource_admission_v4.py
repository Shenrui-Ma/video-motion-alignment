"""Root-authorized CPU certificate after the actual dedicated full158 gate."""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(value,message):
 if not value:raise ValueError(message)
def new(p,value):
 with Path(p).open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def main():
 p=argparse.ArgumentParser();p.add_argument('--root-authorized',action='store_true');p.add_argument('--wait-seconds',type=int,default=600);a=p.parse_args();require(a.root_authorized,'explicit root authorization required')
 require(str(ROOT)=='/data5/researcher/h3_runs/timing_flexiact_auto_r50_retry_20261017','actual remote producer required')
 os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['TMPDIR']=str(ROOT/'temp');sys.path.insert(0,str(ROOT/'scripts'))
 from observer_import import t
 from prelaunch_gates import check_layout_cases
 from preflight import check
 manifest=read(ROOT/'deploy_manifest.json')
 require(sha(ROOT/'deploy_manifest.json')=='30f718dc3ef00ad12f5bf4cfee7151a18e5880db3b743eb7cbef5b3b996b41a4','producer seal differs')
 for rel,row in manifest['files'].items():require(sha(ROOT/rel)==row['sha256'],'sealed file changed: '+rel)
 dp=ROOT/'audit/known_endpoint_158_split_gate.json';deadline=time.monotonic()+a.wait_seconds
 while not dp.exists():
  require(time.monotonic()<deadline,'actual full158 gate wait expired');time.sleep(2)
 d=read(dp);require(d['passed'] is True and d['NFE']==0 and d['model_forward_calls']==0 and all(d['checks'].values()),'full158 gate failed')
 require(d['protocol_sha256']==t.PROTOCOL_SHA,'actual decoder protocol differs')
 for rel,digest in d['source_sha256'].items():require(sha(ROOT/rel)==digest,'actual decoder source differs: '+rel)
 require(sha(d['decode_file'])==d['decode_sha256'],'actual decode artifact changed')
 profile=t.decoder_memory_profile();peak=d['decode']['max_memory_reserved_bytes'];require(0<peak<=profile['peak_reserved_bytes'],'new decoder peak exceeds frozen measured profile; root review required')
 oldp=ROOT/'configs/main_memory_evidence/resource_admission_v2.json';old=read(oldp);r=dict(old)
 for row in old['evidence']:require(sha(row['file'])==row['sha256'],'inherited actual evidence changed: '+row['file'])
 required=old['main_native_peak_sampled_bytes']+old['routing_increment_bound_bytes']+old['main_margin_bytes'];require(old['main_estimated_peak_bytes']>=required and old['main_margin_bytes']>=1024**3,'inherited main bound invalid')
 raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True,timeout=10)
 rows=[]
 for line in raw.splitlines():
  if not line.strip():continue
  uuid,pid=[v.strip() for v in line.split(',')];pid=int(pid);status=Path('/proc')/str(pid)/'status'
  require(status.exists(),'compute owner changed while reading; rerun CPU admission')
  uid=int(next(v for v in status.read_text().splitlines() if v.startswith('Uid:')).split()[1]);require(uid!=os.getuid(),'own compute still present; wait for root-owned recovery/gate release')
  rows.append({'gpu_uuid':uuid,'pid':pid,'uid':uid})
 devices={}
 for uuid,minfree in [(old['main_gpu_uuid'],old['main_estimated_peak_bytes']),(old['decoder_gpu_uuid'],profile['required_free_bytes'])]:
  text=subprocess.check_output(['nvidia-smi','--id='+uuid,'--query-gpu=uuid,memory.total,memory.used,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=10).strip();values=[v.strip() for v in text.split(',')]
  require(len(values)==5 and values[0]==uuid,'GPU UUID result differs');total,used,free,util=map(int,values[1:]);require(free*1024**2>=minfree,'actual free memory below approved capacity bound')
  devices[uuid]={'csv':text,'total_bytes':total*1024**2,'free_bytes':free*1024**2,'required_free_bytes':minfree}
 kp=ROOT/'configs/engineering_v2/previous_kernel_gate.json';check_layout_cases(read(kp),ROOT)
 evidence=old['evidence']+[{'file':str(oldp),'sha256':sha(oldp)},{'file':str(dp),'sha256':sha(dp)},{'file':str(ROOT/'configs/decoder_memory_profile.json'),'sha256':profile['profile_sha256']}]
 r.update(observed_unix=time.time(),protocol_sha256=t.PROTOCOL_SHA,engineering_revision_sha256=sha(ROOT/'configs/engineering_revision_v2.json'),kernel_gate_sha256=sha(kp),decoder_gate_sha256=sha(dp),decoder_peak_reserved_bytes=max(old['decoder_peak_reserved_bytes'],peak),decoder_memory_profile_sha256=profile['profile_sha256'],required_free_before_decoder_mib=7752,devices=devices,evidence=evidence,compute_process_snapshot=rows,own_compute_count=0,interpretation='Inherited actual main capacity bound plus newly executed exact full158 decoder. Foreign compute is allowed subject to actual free memory; service and each observer recheck resource availability.')
 new(ROOT/'audit/resource_admission_v2.json',r)
 admission=read(ROOT/'configs/admission_template.json')['fixed_fields']|{'permitted_compute_processes':[],'root_live_review_required':False}
 (ROOT/'configs/admission.json').write_text(json.dumps(admission,indent=2)+'\n')
 try:result=check(ROOT,metadata_only=False)
 except BaseException:
  admission['root_live_review_required']=True;(ROOT/'configs/admission.json').write_text(json.dumps(admission,indent=2)+'\n');raise
 record={'status':'FULL_PREFLIGHT_PASS_CPU_ONLY','resource_admission_sha256':sha(ROOT/'audit/resource_admission_v2.json'),'admission_sha256':sha(ROOT/'configs/admission.json'),'manifest_sha256':sha(ROOT/'deploy_manifest.json'),'preflight':result,'GPU_started':False}
 new(ROOT/'audit/FULL_PREFLIGHT_v4.json',record);print(json.dumps({'status':record['status'],'certificate_sha256':record['resource_admission_sha256'],'full_preflight_sha256':sha(ROOT/'audit/FULL_PREFLIGHT_v4.json')}))
if __name__=='__main__':main()
