import unittest,sys,copy,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'scripts'),str(R/'extensions')]
from verify_completed import check_record_semantics,check_owner_evidence,check_submission
from bridge_values import pose_values,scan_values
import service

class EvidenceTests(unittest.TestCase):
 def test_record_corruption(self):
  cap=json.loads((R/'configs/parent_captures.json').read_text());row=copy.deepcopy(cap['captures'][0]);case={'run_id':row['run_id'],'seed':row['seed']}
  check_record_semantics(row,cap,case)
  for key,value in [('schema','bad'),('seed',1),('audio_scale',1),('step_zero_based',19),('run_id','other'),('snapshot_kind','sampler_final')]:
   bad=copy.deepcopy(row);bad[key]=value
   with self.assertRaises(ValueError,msg=key):check_record_semantics(bad,cap,case)
 def test_actual_historical_final_records(self):
  for name in ('parent_captures.json',):
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
  pose=json.loads((R/'configs/source.pose.json').read_text());pose.setdefault('statistics',{}).update(detector_s=0,pose_s=0,elapsed_s=0);other=copy.deepcopy(pose);other['video']['path']='elsewhere';other['statistics']['elapsed_s']=0
  self.assertEqual(pose_values(pose),pose_values(other))
  other['frames'][0]['time_s']=1
  self.assertNotEqual(pose_values(pose),pose_values(other))
  scan={'scan_seconds':10,'edited_pose_sha256':'old','windows':[{'lag':3}],'source_pose_sha256':'bound'}
  other=copy.deepcopy(scan);other.update(scan_seconds=20,edited_pose_sha256='new');self.assertEqual(scan_values(scan),scan_values(other))
  other['windows'][0]['lag']=2;self.assertNotEqual(scan_values(scan),scan_values(other))

if __name__=='__main__':unittest.main()
