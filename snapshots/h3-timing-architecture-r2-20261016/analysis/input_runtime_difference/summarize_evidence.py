"""Pure-local audit aggregation; no remote actions or model operations."""
from pathlib import Path
import hashlib,json
import numpy as np
ROOT=Path('/Users/researcher/DevProjects')
OUT=ROOT/'h3-timing-architecture-r2-20261016/analysis/input_runtime_difference'
def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def strip_file(x):
 if isinstance(x,dict):return {k:strip_file(v) for k,v in x.items() if k!='tensor_file'}
 if isinstance(x,list):return [strip_file(v) for v in x]
 return x
def measurements(a,b):
 a=np.asarray(a,dtype=np.float32);b=np.asarray(b,dtype=np.float32);d=a.astype(np.float64)-b.astype(np.float64)
 return {'n_values':int(a.size),'unequal_values':int(np.count_nonzero(a!=b)),'max_abs':float(np.abs(d).max()),'rms':float(np.sqrt(np.mean(d*d))),'mean_abs':float(np.abs(d).mean())}
r={'schema':'h3-input-runtime-difference-v1','scope':'CPU read-only remote probes and local audit aggregation','source_conditions':{},'within_host':{},'cross_host':{},'fixed_sample_differences':{},'sample_quantization_checks':{},'decode_conversion':{},'limits':['Fixed-sample error magnitudes are not whole-frame/global RMSE.','No GPU inference was repeated; output differences cannot be apportioned causally across preprocessing and model numerics.','FFmpeg library version tuples match; binary build identity and precise PyAV behavior change were not established.']}
cs={}; ns={}
fields=['prompt','input_video','native_vae_calls','qwen_presentation','tokenization_before_vision_expansion','conditioning_embedding','token_tags','target_latent_shapes','packed_layout']
for tag,project in [('r2','h3-timing-architecture-r2-20261016'),('r3','h3-timing-spatial-r3-20261016')]:
 base=ROOT/project/'analysis/pose/pilot';paths=sorted(base.glob(f'{tag}_s05_*_provenance/conditioning.json'))
 native=base/f'{tag}_s05_native_provenance/conditioning.json'; c=read(native);n=read(native.with_name('noise.json'));cs[tag]=c;ns[tag]=n
 r['source_conditions'][tag]={'path':str(native),'file_sha256':digest(native),'noise_path':str(native.with_name('noise.json')),'noise_file_sha256':digest(native.with_name('noise.json')),'actual_fields':{k:strip_file(c[k]) for k in fields if k not in ['prompt','tokenization_before_vision_expansion']},'prompt_sha256':hashlib.sha256(c['prompt'].encode()).hexdigest(),'noise_signature':n['signature'],'noise_streams':n['actual_noise_streams'],'pair_snapshot_actual':strip_file(c['pair_snapshot']['actual'])}
 checks=[]
 for p in paths:
  cc=read(p);nn=read(p.with_name('noise.json'));check={k:strip_file(cc[k])==strip_file(c[k]) for k in fields}
  check['pair_snapshot_actual']=strip_file(cc['pair_snapshot']['actual'])==strip_file(c['pair_snapshot']['actual']);check['noise_signature']=nn['signature']==n['signature'];check['noise_streams']=nn['actual_noise_streams']==n['actual_noise_streams']
  checks.append({'run':cc['run_id'],'path':str(p),'condition_file_sha256':digest(p),'noise_file_sha256':digest(p.with_name('noise.json')),'checks':check,'all_equal':all(check.values())})
 r['within_host'][tag]={'arms_available':len(checks),'checks':checks,'all_available_arms_paired':all(x['all_equal'] for x in checks)}
r['cross_host']={k:strip_file(cs['r2'][k])==strip_file(cs['r3'][k]) for k in fields};r['cross_host'].update({'noise_signature':ns['r2']['signature']==ns['r3']['signature'],'noise_streams':ns['r2']['actual_noise_streams']==ns['r3']['actual_noise_streams'],'identity_prepared_rgb':strip_file(cs['r2']['native_vae_calls'][0]['prepared_frames'])==strip_file(cs['r3']['native_vae_calls'][0]['prepared_frames']),'identity_encoded_latent':strip_file(cs['r2']['native_vae_calls'][0]['latent'])==strip_file(cs['r3']['native_vae_calls'][0]['latent'])})
probes={k:read(OUT/f'{k}_actual_runtime_probe.json') for k in ['r2','r3']}
for stage in ['decoded_samples','prepared_samples']:
 r['fixed_sample_differences'][stage]={}
 for f in ['0','55','83','140']:
  r['fixed_sample_differences'][stage][f]=measurements(probes['r2'][stage][f]['values'],probes['r3'][stage][f]['values'])
for tag,p in probes.items():
 checks={}
 for f in ['0','55','83','140']:
  a=np.asarray(p['decoded_samples'][f]['values'],dtype=np.float32);expected=(np.clip(np.float32(255.)*a,0,255).astype(np.uint8).astype(np.float32)/np.float32(255.))
  checks[f]=measurements(expected,p['prepared_samples'][f]['values'])
 r['sample_quantization_checks'][tag]={'same_size_lanczos_quantization_matches_samples':all(x['unequal_values']==0 for x in checks.values()),'checks':checks}
a=read(OUT/'r2_conversion_probe.json');b=read(OUT/'r3_conversion_probe.json');c=read(OUT/'r2_base16_conversion_control.json')
r['decode_conversion']={'r2_actual':a,'r3_actual':b,'r2_same_host_base16_control':c,'full_native_yuv_equal':a['full_native_yuv_sha256']==b['full_native_yuv_sha256']==c['full_native_yuv_sha256'],'full_float_rgb_r2_actual_reproduced':a['full_gbrpf32le_sha256']==cs['r2']['input_video']['sha256'],'full_float_rgb_r3_actual_reproduced':b['full_gbrpf32le_sha256']==cs['r3']['input_video']['sha256'],'full_float_rgb_r2_base16_equals_r3':c['full_gbrpf32le_sha256']==b['full_gbrpf32le_sha256'],'ffmpeg_version_tuples_equal':a['libraries']==b['libraries']==c['libraries'],'sample_rgb24_equal':{f:a['samples'][f]['rgb24_sha256']==b['samples'][f]['rgb24_sha256'] for f in ['0','55','83','140']}}
assert r['decode_conversion']['full_native_yuv_equal'];assert r['decode_conversion']['full_float_rgb_r2_actual_reproduced'];assert r['decode_conversion']['full_float_rgb_r3_actual_reproduced'];assert r['decode_conversion']['full_float_rgb_r2_base16_equals_r3']
(OUT/'RESULTS.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'within_host':{k:{'arms':v['arms_available'],'paired':v['all_available_arms_paired']} for k,v in r['within_host'].items()},'cross_host':r['cross_host'],'quantization':{k:v['same_size_lanczos_quantization_matches_samples'] for k,v in r['sample_quantization_checks'].items()}},ensure_ascii=False,indent=2))
