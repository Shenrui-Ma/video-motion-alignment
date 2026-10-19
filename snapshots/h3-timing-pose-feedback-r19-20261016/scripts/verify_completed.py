"""CPU/read-only post-run gates. No inference or alteration of an existing run."""
import argparse,json,sys,os
from pathlib import Path
from observer_import import t,ROOT
RUN='r19_s05_pose_observer'

def check(root=ROOT):
 root=Path(root);os.environ['CUDA_VISIBLE_DEVICES']='';sys.path.insert(0,str(root/'extensions'))
 import torch
 torch.set_num_threads(1)
 from H3X0Readout.core import tensor_signature
 from H3PoseObserverRouter.selector import select
 t.admission_document(approved=True)
 audit=t.read_json(root/'audit/counterfactual'/f'{RUN}.json');c=audit['counterfactual'];mask=c['full_physical_indices'];K=len(mask);nfe=20+K
 t.require(audit['status']=='complete' and mask[:4]==[6,7,8,9] and len(set(mask))==K and sorted(mask)==mask,'invalid completed mask')
 t.require(4<=K<=14 and c['actual_model_nfe']==nfe and c['actual_euler_updates']==20 and c['callback_count']==20,'actual NFE/Euler/callback count')
 t.require(audit['completed_forward_calls']==nfe and audit['completed_calls']==50*nfe and audit['routed_calls']==50*K,'actual block count')
 t.require(audit['calls_by_forward']==[50]*nfe,'incomplete blocks')
 t.require(len(c['branches'])==nfe and len(c['steps'])==20 and len(c['measurements'])==10,'missing branch/step/measurement')
 history=t.read_json(root/'logs'/f'{RUN}_history.json');t.require(history['status']['status_str']=='success' and history['status']['completed'] is True and history['prompt'][2]==t.read_json(root/'configs'/f'{RUN}.json'),'actual Comfy history not success')
 branches={(row['physical_index'],row['branch']):row for row in c['branches']};measurements={m['physical_index']:m for m in c['measurements']}
 t.require(len(branches)==nfe and sorted(measurements)==list(range(10,20)),'duplicate archive identities')
 for index,step in enumerate(c['steps']):
  t.require(step['physical_index']==index and step['callback_observed_once'],'callback order')
  dec=select(index,measurements.get(index));t.require(dec['chosen_full']==(index in mask) and dec['reason']==step['decision']['reason'],'selector not reproduced')
  chosen=branches[index,'full' if index in mask else 'native'];t.require(step['chosen_raw_stream_signatures']==chosen['raw_stream_signatures'],'chosen endpoint binding')
  for branch in ('native','full') if index in mask else ('native',):
   row=branches[index,branch];t.require(t.sha(row['file'])==row['file_sha256'],'endpoint archive changed')
   t.require(row['global_rng_unchanged'] and row['condition_unchanged'] and row['full_grid_unchanged'],'branch invariant failed')
  if index>=10:
   m=measurements[index];r=t.read_json(m['request_file']);response=t.validate_response(t.read_json(m['response_file']),r,m['request_sha256'])
   t.require(t.sha(m['request_file'])==m['request_sha256'] and t.sha(m['response_file'])==m['response_sha256'],'request/response archive changed')
   t.require(r['endpoint_file_sha256']==branches[index,'native']['file_sha256'],'observer used wrong branch')
   for name in ('decode','pose','observer'):t.require(t.sha(response[name]['file'])==response[name]['sha256'],'observer output archive changed')
   t.require(t.read_json(response['observer']['file'])==m['observer'],'recorded observation differs')
   decode=t.read_json(response['decode']['file']);t.require(decode['status']=='complete' and decode['fallback_guard']['calls']==0 and decode['fallback_guard']['installed'],'decoder fallback/complete guard')
   t.require(decode['decoded_shape']==[141,736,1312,3] and decode['fps']==24 and len(decode['preencode_rgb24_frame_sha256'])==141,'decoder shape/timebase')
 t.require(all(g['pass'] for g in c['pair_gates']) and any(g['gate']=='G2_current_native010' for g in c['pair_gates']),'G1/G2/G3 failed')
 capture=t.read_json(root/'audit/x0'/RUN/'manifest.json');t.require(capture['status']=='complete' and capture['callback_count']==20,'passive recorder incomplete')
 t.require([r['step_zero_based'] for r in capture['captures']]==[5,6,7,8,9,10,11,12,15,19],'capture inventory')
 indices=[5,6,7,8,9,10,11,12,15,19];folder=root/'audit/x0'/RUN
 t.require(capture['capture_steps_zero_based']==indices and capture['expected_callback_count']==20,'declared capture contract')
 t.require(capture['sigmas_video']==c['full_grid'] and capture['seed']==c['seed']==2026101311 and capture['audio_scale']==4.0,'capture grid/seed/scaling')
 records=capture['captures']+[capture['final_sampler_result']]
 names=[r['file'] for r in records]
 t.require(names==[f'x0_step{i:03d}.pt' for i in indices]+['sampler_final.pt'] and sorted(p.name for p in folder.glob('*.pt'))==sorted(names),'actual unique tensor inventory')
 for record in records:
  path=t.inside(folder/record['file'],folder)
  value=torch.load(path,map_location='cpu',weights_only=True)
  metadata={k:v for k,v in record.items() if k not in ('file','capture_seconds')}
  t.require(set(value)=={'video','audio','metadata'} and value['metadata']==metadata,'capture metadata mismatch')
  for key,shape in (('video',(1,24,42,46,82)),('audio',(1,32,2,235))):
   v=value[key];t.require(v.dtype==torch.float32 and tuple(v.shape)==shape and bool(torch.isfinite(v).all()),'capture tensor finite/shape')
   t.require(tensor_signature(v)==record[key],'capture signature mismatch')
  t.require(record['normalization_stage']=='after_process_latent_out' and record['audio_scale']==4.0 and record['video_latent_scale_factor']==1.0,'capture normalization')
  if record['snapshot_kind']=='x0_estimate':
   n=record['step_zero_based'];chosen=branches[n,'full' if n in mask else 'native']
   t.require([tensor_signature(value['video']),tensor_signature(value['audio']*4)]==chosen['raw_stream_signatures'],'actual capture raw streams differ from chosen branch')
  else:
   raw=torch.load(root/'audit/counterfactual'/f'{RUN}_snapshots'/'sampler_final_raw.pt',map_location='cpu',weights_only=True)
   t.require(all(torch.equal(value[k],raw[k] if k=='video' else raw[k]*.25) for k in ('video','audio')),'actual final sampler archive differs')
 t.require(not torch.cuda.is_initialized(),'CPU verifier initialized CUDA')

 cleanup=t.read_json(root/'processes/cleanup.json');t.require(cleanup['process_absent'] and cleanup['own_compute_absent'] and cleanup['child_compute_absent'],'cleanup incomplete')
 manifest=t.read_json(root/'deploy_manifest_v1.json')
 for rel,row in manifest['files'].items():t.require(t.sha(root/rel)==row['sha256'],'deployed immutable file changed: '+rel)
 return {'status':'pass','mask':mask,'NFE':nfe,'Euler_updates':20,'observations':10,'new_method_claim':False,'runtime_integrity_only':True,'G2_current_bridge_recorded_runtime_assertion':True,'G1_G3_scope':'immutable runtime code asserted tensors during sampling; this verifier checks recorded passes and independently validates actual branch/capture files, not a second historical replay','cleanup_verified':True}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',default=str(ROOT));p.add_argument('--output');a=p.parse_args();result=check(a.root)
 if a.output:t.write_new(a.output,result)
 print(json.dumps(result,indent=2))
