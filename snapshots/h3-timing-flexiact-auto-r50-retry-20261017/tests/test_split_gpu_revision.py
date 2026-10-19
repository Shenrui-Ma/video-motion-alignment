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
from gpu_release_gate import wait_own_child_released
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
    def test_wrong_device_rejected(self):
        with self.assertRaises(ValueError):self.admit(uuid=t.MAIN_UUID)
    def test_missing_or_stale_main_rejected_duplicate_allowed(self):
        self.admit(rows=self.rows+self.rows)
        for rows,parent in [([],None),(self.rows,dict(self.parent,start_ticks=9))]:
            with self.assertRaises(ValueError):self.admit(rows=rows,parent=parent)
    def test_other_own_GPU_uses_decoder_slot_and_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'two owned GPU cards'):
            self.admit(rows=self.rows+[{'gpu_uuid':'GPU-third','pid':300}])
    def test_other_user_on_unrelated_gpu_allowed(self):
        lookup=lambda pid:self.parent if pid==100 else {'uid':os.getuid()+1}
        self.assertEqual(t.validate_separate_decoder(self.parent,t.DECODER_UUID,self.gpu,self.rows+[{'gpu_uuid':'GPU-other','pid':300}],lookup)['uuid'],t.DECODER_UUID)
    def test_measured_free_memory_allows_existing_load(self):
        self.admit(gpu=dict(self.gpu,memory_free_mib=7752,memory_used_mib=70000,utilization_percent=99))
        with self.assertRaises(t.ResourceUnavailable):self.admit(gpu=dict(self.gpu,memory_free_mib=7751))
    def test_exited_child_release_allows_foreign(self):
        child={'returncode':0,'process':self.parent}
        result=wait_own_child_released(t.DECODER_UUID,child,lambda _:None,compute_pids=lambda:[999])
        self.assertTrue(result['original_generation_absent'])
        with self.assertRaises(RuntimeError):wait_own_child_released(t.DECODER_UUID,child,lambda _:self.parent,compute_pids=lambda:[100])
    def test_response_must_bind_dedicated_GPU_and_release(self):
        request={'parent':self.parent};admission=self.admit()
        response={'status':'complete','request_sha256':'x','decoder_released_before_pose':True,'decoder_admission':admission,'after_decoder_release':{'schema':'h3-own-decoder-release-v1','gpu_uuid':t.DECODER_UUID,'child_identity':self.parent,'original_generation_absent':True,'nvml_pid_absent':True,'pid_reused':False},'decoder':{'returncode':0,'process':self.parent},'pose_process':{'returncode':0}}
        t.validate_response(response,request,'x')
        bad=copy.deepcopy(response);bad['after_decoder_release']['gpu_uuid']=t.MAIN_UUID
        with self.assertRaisesRegex(ValueError,'device differs'):t.validate_response(bad,request,'x')
    def test_start_reserves_decoder_even_for_registered_peer(self):
        queue={'queue_running':[],'queue_pending':[]};admission={'scope':'own_user_video_jobs','permitted_compute_processes':[]}
        with patch.object(t,'admission_document',return_value=admission),patch.object(service,'proc_uid',return_value=os.getuid()):
            service.check_admission(admission,[],queue)
            with self.assertRaisesRegex(RuntimeError,'Unexpected own compute identity'):
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
        for name in ('load_snapshot','install_fallback_guard','write_video'):
            for node in ast.walk(previous[name]):
                if isinstance(node,ast.Attribute) and node.attr=='co_resident_admission':node.attr='separate_decoder_admission'
            self.assertEqual(ast.dump(previous[name]),ast.dump(current[name]),name)

if __name__=='__main__':unittest.main()
