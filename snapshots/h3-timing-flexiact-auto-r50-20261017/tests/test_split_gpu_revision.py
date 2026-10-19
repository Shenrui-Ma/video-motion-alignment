"""Resource-only split: exact decoder math, two-card ownership, fail-closed gates."""
import ast
import copy
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts')]
from observer_import import t
from gpu_release_gate import wait_after_child
from prelaunch_gates import check_engineering_revision
import service

class SplitGPURevision(unittest.TestCase):
    def setUp(self):
        self.parent={'pid':100,'uid':os.getuid(),'start_ticks':1,'cmdline_sha256':'a'*64}
        self.gpu={'uuid':t.DECODER_UUID,'memory_used_mib':0,'memory_free_mib':81920,'utilization_percent':0}
        self.rows=[{'gpu_uuid':t.MAIN_UUID,'pid':100}]
        self.lookup=lambda pid:self.parent if pid==100 else {'pid':pid,'uid':os.getuid(),'start_ticks':2,'cmdline_sha256':'b'*64}
    def admit(self,gpu=None,rows=None,parent=None,uuid=None):
        return t.validate_separate_decoder(parent or self.parent,uuid or t.DECODER_UUID,gpu or self.gpu,self.rows if rows is None else rows,self.lookup)
    def test_exact_parent_main_and_empty_decoder_pass(self):
        result=self.admit();self.assertEqual(result['main_compute_parent'],self.parent)
        self.assertEqual(result['planned_owned_GPUs'],sorted([t.MAIN_UUID,t.DECODER_UUID]))
    def test_decoder_busy_or_wrong_device_rejected(self):
        for rows,uuid in [(self.rows+[{'gpu_uuid':t.DECODER_UUID,'pid':200}],None),(self.rows,t.MAIN_UUID)]:
            with self.assertRaises(ValueError):self.admit(rows=rows,uuid=uuid)
    def test_missing_duplicate_stale_main_rejected(self):
        for rows,parent in [([],None),(self.rows+self.rows,None),(self.rows,dict(self.parent,start_ticks=9))]:
            with self.assertRaises(ValueError):self.admit(rows=rows,parent=parent)
    def test_other_own_GPU_uses_decoder_slot_and_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'second owned GPU slot'):
            self.admit(rows=self.rows+[{'gpu_uuid':'GPU-third','pid':300}])
    def test_other_user_on_unrelated_gpu_allowed(self):
        lookup=lambda pid:self.parent if pid==100 else {'uid':os.getuid()+1}
        self.assertEqual(t.validate_separate_decoder(self.parent,t.DECODER_UUID,self.gpu,self.rows+[{'gpu_uuid':'GPU-other','pid':300}],lookup)['uuid'],t.DECODER_UUID)
    def test_idle_memory_and_utilization_limits(self):
        for change in [{'memory_free_mib':44999},{'memory_used_mib':1025},{'utilization_percent':1}]:
            with self.assertRaisesRegex(ValueError,'idle headroom'):self.admit(gpu=dict(self.gpu,**change))
    def test_exited_child_tail_wait_and_foreign_refusal(self):
        now=[0.];attempts=[ValueError('decoder GPU has active compute'),self.admit()]
        def idle(_):
            result=attempts.pop(0)
            if isinstance(result,Exception):raise result
            return result
        child={'returncode':0,'process':{'pid':200}}
        result=wait_after_child(t.DECODER_UUID,child,idle,lambda _:None,clock=lambda:now[0],sleep=lambda s:now.__setitem__(0,now[0]+s),compute_pids=lambda:[])
        self.assertTrue(result['strict_original_idle_assertion_passed'])
        with self.assertRaisesRegex(RuntimeError,'foreign GPU'):
            wait_after_child(t.DECODER_UUID,child,lambda _:self.admit(),lambda _:None,compute_pids=lambda:[999])
    def test_response_must_bind_dedicated_GPU_and_release(self):
        request={'parent':self.parent};admission=self.admit()
        response={'status':'complete','request_sha256':'x','decoder_released_before_pose':True,'decoder_admission':admission,'after_decoder_admission':{'idle':admission,'strict_original_idle_assertion_passed':True,'decoder_identity_absent':True},'decoder':{'returncode':0},'pose_process':{'returncode':0}}
        t.validate_response(response,request,'x')
        bad=copy.deepcopy(response);bad['after_decoder_admission']['idle']['uuid']=t.MAIN_UUID
        with self.assertRaisesRegex(ValueError,'placement differs'):t.validate_response(bad,request,'x')
    def test_start_reserves_decoder_even_for_registered_peer(self):
        queue={'queue_running':[],'queue_pending':[]};admission={'scope':'own_user_video_jobs','permitted_compute_processes':[]}
        with patch.object(t,'admission_document',return_value=admission),patch.object(service,'proc_uid',return_value=os.getuid()):
            service.check_admission(admission,[],queue)
            with self.assertRaisesRegex(RuntimeError,'decoder GPU has active compute'):
                service.check_admission(admission,[{'gpu_uuid':t.DECODER_UUID,'pid':200}],queue)
    def test_actual_science_exact_and_protocol_only_resources_changed(self):
        spec=check_engineering_revision(ROOT)
        self.assertGreaterEqual(len(spec['unchanged_scientific_files']),100)
        self.assertEqual(spec['single_GPU_assessment']['status'],'UNSUPPORTED_BY_STRICT_12GiB_GATE')
    def test_decoding_numerics_exact_except_admission_function_name(self):
        with tarfile.open(ROOT/'audit/revisions/producer_v1/sealed_producer.tar.gz') as tar:
            old=ast.parse(tar.extractfile('scripts/decode_live_child.py').read())
        new=ast.parse((ROOT/'scripts/decode_live_child.py').read_text())
        funcs=lambda tree:{n.name:n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        previous,current=funcs(old),funcs(new)
        for name in ('load_snapshot','install_fallback_guard','write_video','main'):
            for node in ast.walk(previous[name]):
                if isinstance(node,ast.Attribute) and node.attr=='co_resident_admission':node.attr='separate_decoder_admission'
            self.assertEqual(ast.dump(previous[name]),ast.dump(current[name]),name)

if __name__=='__main__':unittest.main()
