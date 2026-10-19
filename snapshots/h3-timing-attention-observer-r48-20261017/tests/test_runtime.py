import copy,importlib,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import service,job,launch_remote,run_queue,start_controller
from r46_contract import identity_schema

class RuntimeTests(unittest.TestCase):
    def owner(self,pid=10):return {'pid':pid,'identity':{'uid':1016,'start_ticks':str(pid*10),'cmdline':'owned'}}
    def test_created_owner_only_current_supervisor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'processes').mkdir();old=self.owner();new=self.owner(11)
            supervisor={'pid':9,'identity':{'uid':1016,'start_ticks':'90','cmdline':'supervisor'},'service_pid':10,'service_identity':old['identity'],'service_record':old}
            (root/'processes/supervisor_9.json').write_text(json.dumps(supervisor))
            (root/'processes/service.json').write_text(json.dumps(new))
            with patch.object(service,'stop') as stop:
                self.assertFalse(launch_remote.cleanup_created_owner(root,9,supervisor['identity'])['stopped']);stop.assert_not_called()
                (root/'processes/service.json').write_text(json.dumps(old))
                launch_remote.cleanup_created_owner(root,9,supervisor['identity']);stop.assert_called_once_with(expected_record=old)
    def test_no_child_no_stop(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(service,'stop') as stop:
            self.assertFalse(launch_remote.cleanup_created_owner(tmp,9,{})['stopped']);stop.assert_not_called()
    def test_old_controller_cannot_submit_to_new_generation(self):
        with self.assertRaises(RuntimeError):job.require_generation(self.owner(11),self.owner(10))
    def test_order_no_retry_or_rewrite(self):
        self.assertEqual(run_queue.remaining(['a','b'],['a']),['b'])
        with self.assertRaises(ValueError):run_queue.remaining(['a','b'],['b'])
    def test_peer_int_tick_schema_rejected(self):
        peer={'pid':23,'identity':{'uid':1016,'start_ticks':2624449931,'cmdline_sha256':'a'*64}}
        with self.assertRaises(ValueError):service.check_admission({'scope':'own_user_video_jobs','permitted_compute_processes':[peer]},[],{'queue_running':[],'queue_pending':[]})
    def test_precuda_command_and_fixed_node_only(self):
        cmd=service.command();self.assertIn(str(ROOT/'scripts/service_entry.py'),cmd)
        self.assertIn('H3AttentionStateProbe',cmd);self.assertNotIn('H3StaticWindowRouter',cmd);self.assertNotIn('ComfyUI-KJNodes',cmd)
    def test_all_imports_no_cuda_or_service(self):
        for name in ['preflight','r46_contract','build_manifest','verify_completed','lease_watchdog','supervise_service','service_entry']:
            importlib.import_module(name)
        import torch
        self.assertFalse(torch.cuda.is_initialized())

if __name__=='__main__':unittest.main()
