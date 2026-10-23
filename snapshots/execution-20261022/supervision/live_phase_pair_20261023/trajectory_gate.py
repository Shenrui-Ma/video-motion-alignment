"""Bind an actual completed live trajectory and its two observations to one video."""
from pathlib import Path
import hashlib,json,math

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def bind(root,method,history,assets):
 root=Path(root);cp=root/'contracts'/(method+'_contract.json');contract=json.loads(cp.read_text());tid=contract['trajectory_id'];op=root/'audit/live_phase'/tid/'OBSERVATION.json';o=json.loads(op.read_text());h=history
 assert h['status']['completed'] is True and h['status']['status_str']=='success'
 assert h['prompt'][2]==json.loads((root/'graphs'/(method+'_graph.json')).read_text())
 assert o['status']=='complete' and o['science_contract_sha256']==sha(cp)
 for k,v in [('callback_count',20),('actual_model_forward_count',20),('completed_blocks',1000),('extra_model_forward_calls',0)]:assert type(o[k]) is int and o[k]==v,k
 assert o['trajectory_id']==tid and o['case']==contract['case'] and o['method']==method
 assert o['original_result_returned_without_copy'] is True and o['final_raw_result']['finite'] is True
 assert math.isfinite(o['sampling_seconds']) and o['sampling_seconds']>0
 assert o['sample_sigmas_video']==contract['sigmas_video']
 assert o['noise']['sha256']==contract['noise_tensor_sha256']
 assert [c['step_zero_based'] for c in o['captures']]==[9,19]
 assert len({c['qk_sha256'] for c in o['captures']})==2
 for c in o['captures']:
  assert c['layer_zero_based']==25
  for k,hk in [('state_file','state_file_sha256'),('qk_file','qk_sha256')]:
   p=Path(c[k]).resolve();assert p.is_relative_to((root/'audit/live_phase'/tid).resolve());assert sha(p)==c[hk]
  x=c['forward_identity'];expected={'trajectory_id':tid,'case':contract['case'],'method':method,'science_contract_sha256':sha(cp),'step_zero_based':c['step_zero_based'],'layer_zero_based':25,'state_file_sha256':c['state_file_sha256'],'sample_sigmas_video':contract['sigmas_video'],'noise_sha256':contract['noise_tensor_sha256']}
  assert all(x[k]==v for k,v in expected.items())
  for k in ['packed_x','raw_packed_x0']:assert x[k]['finite'] is True and x[k]['dtype']=='torch.float32'
 outputs=[(root/'output'/v.get('subfolder','')/v['filename']).resolve() for n in h['outputs'].values() for v in n.get('images',[]) if v.get('type')=='output' and v['filename'].endswith('.mp4')]
 assert len(outputs)==1
 video=outputs[0];assert video.is_relative_to((root/'output'/tid).resolve()) and video.stat().st_size>0
 for p,expected in assets.items():assert sha(root/p)==expected,p
 return {'schema':'h3-live-phase-trajectory-gate-v1','passed':True,'cohort':'phase_calibration_pair','case':contract['case'],'method':method,'trajectory_id':tid,'science_contract_sha256':sha(cp),'callback_count':20,'actual_model_forward_count':20,'completed_blocks':1000,'extra_model_forward_calls':0,'actual_video_file':str(video),'actual_video_sha256':sha(video),'actual_video_bytes':video.stat().st_size,'observation_manifest':str(op),'observation_manifest_sha256':sha(op),'captures':o['captures'],'sampling_seconds':o['sampling_seconds'],'mean_sampling_step_seconds':o['sampling_seconds']/20,'actual_history_graph_sha256':sha(root/'graphs'/(method+'_graph.json')),'runtime_assets':assets}
