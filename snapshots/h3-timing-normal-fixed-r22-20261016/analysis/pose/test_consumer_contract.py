"""Pure metadata tests: no transport, pose, tensor, dependency or GPU work."""
import copy,json,subprocess,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import consumer_r22 as c
from probe_completion import validate_binding,evaluate_documents,ROOT,RUN,SEAL

def fixture():
    identity=lambda n:{'uid':1016,'start_ticks':str(n),'cmdline':'python '+ROOT+'/task'+str(n)}
    s={'pid':1_000,'identity':identity(1_000),'port':8482,'gpu_uuid':'GPU-REDACTED'}
    b={'approved':True,'root':ROOT,'run_id':RUN,'manifest_sha256':SEAL,'sealed_file_count':48,'service_record':s,'role_records':{k:{'pid':1001+i,'identity':identity(1001+i)} for i,k in enumerate(('supervisor','watchdog','controller'))},'authorized_admission_sha256':['a'*64]}
    h={'status':{'status_str':'success','completed':True}};cleanup={'service_record':s,'process_absent':True,'own_compute_absent':True};ctl={'status':'all_queued_jobs_complete','completed':[RUN]}
    return b,s,h,cleanup,ctl,{},[]
class Tests(unittest.TestCase):
    def test_default_no_network_or_gpu(self):
        p=subprocess.run([sys.executable,str(Path(c.__file__))],capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(p.stdout)['status'],'prepared_only')
    def test_history_contract(self):c.self_test()
    def test_ready(self):self.assertEqual(evaluate_documents(*fixture())['status'],'ready')
    def test_wait_missing_cleanup_and_history(self):
        for i in (2,3,4):
            a=list(fixture());a[i]=None;self.assertEqual(evaluate_documents(*a)['status'],'waiting')
    def test_error_does_not_get_success(self):
        a=list(fixture());a[2]={'status':{'status_str':'error'}};self.assertEqual(evaluate_documents(*a)['status'],'failed')
    def test_wrong_identity_rejected(self):
        a=list(fixture());a[1]=copy.deepcopy(a[1]);a[1]['identity']['start_ticks']='wrong'
        with self.assertRaises(ValueError):evaluate_documents(*a)
    def test_live_owned_or_driver_residual_waits(self):
        a=list(fixture());a[5]={'1000':a[1]['identity']};self.assertEqual(evaluate_documents(*a)['status'],'waiting')
        a=list(fixture());a[6]=[{'pid':1000}];self.assertEqual(evaluate_documents(*a)['status'],'waiting')
    def test_reused_pid_is_never_treated_as_ours(self):
        a=list(fixture());a[5]={'1000':{'uid':1015,'start_ticks':'new','cmdline':'unrelated'}};a[6]=[{'pid':1000}]
        r=evaluate_documents(*a);self.assertEqual(r['status'],'ready');self.assertTrue(r['roles']['service']['PID_reused_by_unrelated_process'])
    def test_unapproved_or_wrong_source_seed_binding(self):
        b=fixture()[0];b['approved']=False
        with self.assertRaises(ValueError):validate_binding(b)
        b=fixture()[0];b['run_id']='r18_s05_full_6to11'
        with self.assertRaises(ValueError):validate_binding(b)
if __name__=='__main__':unittest.main()
