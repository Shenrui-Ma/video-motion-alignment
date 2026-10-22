"""Actual27-bin kernel and full90 isolated decoder gates, bound to root resource review."""
import hashlib,json
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def require(ok,message):
 if not ok:raise ValueError(message)

def check_layout_cases(k,root):
 rows=[v for v in k['cases'] if v['actual_shape']];cases=read(root/'configs/protocol.json')['cases']
 require([v.get('case_run') for v in rows]==[c['run_id'] for c in cases],'five actual single-video layouts required')
 for actual,case in zip(rows,cases):
  condition=read(root/case['parent_conditioning']);segments=condition['packed_layout']['segments'];n=condition['packed_layout']['seq_len']
  targets=[s for s in segments if s[2]=='video'];refs=[s for s in segments if s[2]=='ref_img']
  require(len(targets)==len(refs)==1 and refs[0][1]-refs[0][0]==27*943,'single-video reference layout differs')
  expected={'seq_len':n,'frame_rows':943,'latent_interval_half_open':[0,27],'query_interval_half_open':targets[0][:2],'reference_video_segment':refs[0][:2]}
  require(actual['shape']==[1,56,n,128] and actual['plan']==expected,'actual27-bin kernel layout differs')
 require(all(v['passed'] and all(v['checks'].values()) for v in k['cases']),'partial kernel failure')

def check(root):
 root=Path(root);protocol=sha(root/'configs/protocol.json');kp=root/'audit/gpu_dynamic_union_gate.json';dp=root/'audit/known_endpoint_90_gate.json';rp=root/'audit/resource_admission.json'
 k,d,r=read(kp),read(dp),read(rp)
 from observer_import import t
 profile=t.decoder_memory_profile()
 require(profile['evidence_sha256']==sha(dp) and profile['peak_reserved_bytes']==d['decode']['max_memory_reserved_bytes'],'formal decoder profile differs from actual full90 gate')
 require(k['schema']=='h3-r27-kernel-gate-v1' and k['passed'] is True and k['NFE']==0,'current model-free kernel gate missing')
 require(d['schema']=='r55-full90-decoder-gate-v1' and d['passed'] is True and d['NFE']==0 and d['model_forward_calls']==0 and all(d['checks'].values()),'current full90 decoder gate missing')
 for gate in (k,d):
  require(gate['protocol_sha256']==protocol,'GPU gate protocol changed')
  for name,digest in gate['source_sha256'].items():require(sha(root/name)==digest,'GPU gate source changed:'+name)
 check_layout_cases(k,root)
 require(sha(Path(d['decode_file']))==d['decode_sha256'],'actual decode artifact changed')
 require(r['schema']=='r55-root-two-GPU-resource-admission-v1' and r['root_approved'] is True,'root dualGPU resource review missing')
 require(r['main_gpu_uuid']=='GPU-REDACTED' and r['decoder_gpu_uuid']=='GPU-REDACTED','resource device differs')
 require(r['protocol_sha256']==protocol and r['kernel_gate_sha256']==sha(kp) and r['decoder_gate_sha256']==sha(dp),'resource review unbound')
 fields=('main_native_peak_reserved_bytes','routing_increment_bound_bytes','main_total_memory_bytes','main_estimated_peak_bytes','decoder_peak_reserved_bytes','decoder_total_memory_bytes')
 for key in fields:require(type(r[key]) is int and r[key]>0,'invalid resource estimate:'+key)
 require(r['main_estimated_peak_bytes']>=r['main_native_peak_reserved_bytes']+r['routing_increment_bound_bytes'] and r['main_estimated_peak_bytes']<=r['main_total_memory_bytes'],'main device capacity estimate failed')
 require(r['decoder_peak_reserved_bytes']>=d['decode']['max_memory_reserved_bytes'] and r['decoder_peak_reserved_bytes']<=r['decoder_total_memory_bytes'],'decoder capacity estimate failed')
 require(r['scope']=='GPU1 main model; GPU2 isolated decoder; maximum2 owned GPUs','resource scope differs')
 require(isinstance(r['evidence'],list) and len(r['evidence'])>=2,'actual memory evidence missing')
 for row in r['evidence']:require(sha(Path(row['file']))==row['sha256'],'resource evidence changed')
 return {'kernel_gate_sha256':sha(kp),'decoder_gate_sha256':sha(dp),'resource_admission_sha256':sha(rp)}
