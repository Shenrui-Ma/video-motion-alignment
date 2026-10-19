import unittest,sys,copy,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'scripts'),str(R/'extensions')]
from verify_completed import check_record_semantics,check_owner_evidence,check_submission
from bridge_values import pose_values,scan_values
import service

class EvidenceTests(unittest.TestCase):
 def test_record_corruption(self):
  cap=json.loads((R/'configs/normal_captures.json').read_text());row=copy.deepcopy(cap['captures'][0]);case={'run_id':row['run_id'],'seed':row['seed']}
  check_record_semantics(row,cap,case)
  for key,value in [('schema','bad'),('seed',1),('audio_scale',1),('step_zero_based',0),('run_id','other'),('snapshot_kind','sampler_final')]:
   bad=copy.deepcopy(row);bad[key]=value
   with self.assertRaises(ValueError,msg=key):check_record_semantics(bad,cap,case)
 def test_actual_historical_final_records(self):
  for name in ('normal_captures.json','bad_captures.json'):
   cap=json.loads((R/'configs'/name).read_text());row=cap['final_sampler_result'];case={'run_id':row['run_id'],'seed':row['seed']}
   check_record_semantics(row,cap,case)
   bad=copy.deepcopy(row);bad['sigma_video']=cap['sigmas_video'][19]
   with self.assertRaisesRegex(ValueError,'capture sigma'):check_record_semantics(bad,cap,case)
 def test_submission_binding(self):
  job={'status':'success','name':'case','graph_sha256':'abc','prompt_id':'one'};history={'prompt':[0,'one',{}]}
  check_submission(job,history,'case','abc')
  for key,value in [('status','queued'),('name','other'),('graph_sha256','new'),('prompt_id','two')]:
   bad=dict(job,**{key:value})
   with self.assertRaises(ValueError):check_submission(bad,history,'case','abc')
 def test_owner_generation(self):
  owner={'pid':41,'gpu_uuid':service.GPU,'port':service.PORT,'cache_none':False,'command':service.command(False),'identity':{'uid':1016,'start_ticks':'123','cmdline':str(service.CORE/'main.py')+' '+str(service.RUN)}}
  jobs=[{'service_pid':41,'service_identity':copy.deepcopy(owner['identity'])}]*2
  cleanup={'pid':41,'service_record':copy.deepcopy(owner),'process_absent':True,'own_compute_absent':True,'child_compute_absent':True}
  check_owner_evidence(owner,jobs,cleanup)
  bad=copy.deepcopy(cleanup);bad['service_record']['identity']['start_ticks']='old'
  with self.assertRaisesRegex(ValueError,'stale cleanup'):check_owner_evidence(owner,jobs,bad)
  bad=copy.deepcopy(jobs);bad[1]['service_pid']=40
  with self.assertRaisesRegex(ValueError,'mixed service'):check_owner_evidence(owner,bad,cleanup)
 def test_bridge_value_domains(self):
  pose=json.loads((R/'configs/bridge_pose.json').read_text());other=copy.deepcopy(pose);other['video']['path']='elsewhere';other['statistics']['elapsed_s']=0
  self.assertEqual(pose_values(pose),pose_values(other))
  other['frames'][0]['time_s']=1
  self.assertNotEqual(pose_values(pose),pose_values(other))
  scan={'scan_seconds':10,'edited_pose_sha256':'old','windows':[{'lag':3}],'source_pose_sha256':'bound'}
  other=copy.deepcopy(scan);other.update(scan_seconds=20,edited_pose_sha256='new');self.assertEqual(scan_values(scan),scan_values(other))
  other['windows'][0]['lag']=2;self.assertNotEqual(scan_values(scan),scan_values(other))

class PrelaunchTests(unittest.TestCase):
 def test_gpu_evidence_missing_or_mismatched_refused(self):
  import tempfile
  from prelaunch_gates import check,sha
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'configs').mkdir();(root/'audit').mkdir();(root/'configs/protocol.json').write_text('{}')
   with self.assertRaises(FileNotFoundError):check(root)
   kernel={'schema':'h3-r27-kernel-gate-v1','passed':True,'NFE':0,'protocol_sha256':sha(root/'configs/protocol.json'),'source_sha256':{},'cases':[{'actual_shape':True,'shape':[1,56,100,128],'plan':{'latent_interval_half_open':[0,42]},'passed':True,'checks':{'fixture':True}}]}
   bridge={'schema':'r27-known-endpoint-gate-v1','passed':True,'NFE':0,'model_forward_calls':0,'protocol_sha256':kernel['protocol_sha256'],'source_sha256':{},'checks':{'fixture':True}}
   kp=root/'audit/gpu_dynamic_union_gate.json';bp=root/'audit/known_endpoint_bridge.json';kp.write_text(json.dumps(kernel));bp.write_text(json.dumps(bridge))
   evidence=root/'audit/measurement.json';evidence.write_text('{}')
   resource={'schema':'r27-root-resource-admission-v1','root_approved':True,'gpu_uuid':'GPU-REDACTED','kernel_gate_sha256':sha(kp),'known_endpoint_gate_sha256':sha(bp),'model_resident_measured_bytes':50*2**30,'routing_increment_bound_bytes':5*2**30,'decoder_peak_reserved_bytes':6*2**30,'total_memory_bytes':80*2**30,'estimated_combined_bytes':61*2**30,'required_free_before_decoder_mib':12288,'scope':'single GPU isolated exec; runtime exact-parent admission remains mandatory','evidence':[{'file':str(evidence),'sha256':sha(evidence)}]*2}
   rp=root/'audit/resource_admission.json';rp.write_text(json.dumps(resource));check(root)
   for key,value in [('root_approved',False),('kernel_gate_sha256','stale'),('estimated_combined_bytes',1),('routing_increment_bound_bytes',30*2**30)]:
    rp.write_text(json.dumps(dict(resource,**{key:value})))
    with self.assertRaises(ValueError,msg=key):check(root)

if __name__=='__main__':unittest.main()
