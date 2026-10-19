"""Postrun rejects incomplete generation evidence before media decoding/export."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'analysis/postrun')]
import export_case as export
from execution_contract import sha


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))


class PostrunEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.run='r59_fixture_visible_only'
        save(self.root/'deploy_manifest.json',{'files':{}});save(self.root/'configs/protocol.json',{})
        self.graph={'1':{'inputs':{},'class_type':'Fixture'}};save(self.root/'configs/graphs'/(self.run+'.json'),self.graph)
        self.owner={'pid':70,'identity':{'uid':42,'start_ticks':'100','cmdline':'comfy'}};save(self.root/'processes/service.json',self.owner)
        self.jobs={self.run:{'arm':'visible_only','case':{'run_id':self.run},'graph_sha256':sha(self.root/'configs/graphs'/(self.run+'.json'))}}
        job={'status':'success','service_pid':70,'service_identity':self.owner['identity'],'graph_sha256':self.jobs[self.run]['graph_sha256'],'prompt_id':'abcdef'}
        self.history={'prompt':[0,'abcdef',self.graph],'status':{'status_str':'success','completed':True},
                      'outputs':{'14':{'images':[{'type':'output','subfolder':'','filename':self.run+'_00001_.mp4'}]}}}
        save(self.root/'logs'/(self.run+'_job.json'),job);save(self.root/'logs'/(self.run+'_history.json'),self.history)
        self.gate={'status':'pass','producer_manifest_sha256':sha(self.root/'deploy_manifest.json'),'protocol_sha256':sha(self.root/'configs/protocol.json'),
                   'planned_denominator':15,'registered_arms':4,'service_record':self.owner,'candidate_science_preserved':True,'runtime_integrity_only':True,
                   'cases':[{'run':self.run,'arm':'visible_only','updates':20,
                             'independent_parent_inputs':{'actual_clean_inputs_equal':True,'initial_video_audio_noise_equal':True},
                             'independent_native_prefix':[{'actual_video_audio_tensor_equal':True}]}]}
        self.path=self.root/'gate.json';save(self.path,self.gate)

    def tearDown(self):self.tmp.cleanup()

    def check(self):
        with patch.object(export,'registry',return_value=(self.jobs,[self.run])):
            return export.verify_gate(self.root,self.run,self.path)

    def test_complete_gate_releases_exact_output_path(self):
        _,output,_=self.check();self.assertEqual(output,self.root/'output'/(self.run+'_00001_.mp4'))

    def test_partial_denominator_rejected(self):
        self.gate['planned_denominator']=1;save(self.path,self.gate)
        with self.assertRaisesRegex(ValueError,'incomplete registry'):self.check()

    def test_missing_independent_parent_proof_rejected(self):
        self.gate['cases'][0].pop('independent_parent_inputs');save(self.path,self.gate)
        with self.assertRaisesRegex(ValueError,'parent payload'):self.check()

    def test_output_from_another_case_rejected(self):
        self.history['outputs']['14']['images'][0]['filename']='another_00001_.mp4';save(self.root/'logs'/(self.run+'_history.json'),self.history)
        with self.assertRaisesRegex(ValueError,'output run differs'):self.check()

    def test_incomplete_actual_history_rejected(self):
        self.history['status']['completed']=False;save(self.root/'logs'/(self.run+'_history.json'),self.history)
        with self.assertRaisesRegex(ValueError,'history incomplete'):self.check()

    def test_online_observer_has_CPU_priority(self):
        save(self.root/'logs/controller_state.json',{'current':self.run})
        request=self.root/'audit/observations/task/request.json';save(request,{'run_id':self.run})
        self.assertTrue(export.observed_pending(self.root))
        save(request.parent/'response.json',{})
        self.assertFalse(export.observed_pending(self.root))


if __name__=='__main__':unittest.main()
