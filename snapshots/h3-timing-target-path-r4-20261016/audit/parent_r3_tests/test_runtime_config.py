"""CPU-only graph, rebasing, admission and path-guard contracts."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
REMOTE='/data5/researcher/h3_runs/timing_spatial_r3_20261016'
sys.path.insert(0,str(ROOT/'extensions'))
from H3EventAudit import audit_root
from H3X0Readout.core import CAPTURE_STEPS
spec=importlib.util.spec_from_file_location('r3_service_contract',ROOT/'scripts/service.py')
service=importlib.util.module_from_spec(spec);spec.loader.exec_module(service)
ARMS=('native','full_6to14','dynamic_6to14','spatial_6to14')


def graph(name):return json.loads((ROOT/'configs'/('r3_s05_'+name+'.json')).read_text())


def strip_admin(g):
    g=copy.deepcopy(g)
    for n,k in [('6','run_id'),('50','run_id'),('51','run_id'),('52','run_id'),('14','filename_prefix')]:
        if n in g:g[n]['inputs'][k]='ADMIN'
    return g


class RuntimeConfigTests(unittest.TestCase):
    def test_formal_graph_differences_are_mode_node_and_admin_only(self):
        base=strip_admin(graph('native'))
        for name in ARMS:
            other=strip_admin(graph(name));other['50']['inputs']['mode']=base['50']['inputs']['mode'];other['50']['class_type']=base['50']['class_type']
            self.assertEqual(other,base)
        self.assertEqual(graph('spatial_6to14')['50']['class_type'],'H3SpatialMarginalRouter')
        self.assertEqual(graph('dynamic_6to14')['50']['inputs']['mode'],'dynamic_residual')

    def test_formal_frozen_geometry_sigmas_window_capture(self):
        for name in ARMS:
            g=graph(name)
            self.assertEqual(g['6']['inputs']['noise_seed'],2026101311)
            self.assertEqual([g['5']['inputs'][x] for x in ('width','height','length')],[1312,736,141])
            self.assertEqual(g['5']['inputs']['semantic_fps'],2);self.assertEqual(g['5']['inputs']['phase_frames'],0)
            self.assertEqual(len(g['9']['inputs']['sigmas'].split(',')),21)
            self.assertEqual(g['8']['inputs']['sampler_name'],'euler')
            self.assertEqual([g['50']['inputs'][x] for x in ('step_start','step_end','block_start','block_end','start_frame','end_frame','alpha','radius','time_offset')],[6,15,0,50,50,65,1.,0,0])
            self.assertEqual(g['7']['inputs']['model'],['52',0]);self.assertEqual(g['52']['inputs']['model'],['50',0])
        self.assertEqual(CAPTURE_STEPS,(5,6,7,8,9,10,15,19))

    def test_benchmark_bypasses_x0_and_keeps_only_expected_scientific_changes(self):
        b=strip_admin(graph('spatial_bench2'));f=strip_admin(graph('spatial_6to14'))
        self.assertNotIn('52',b);self.assertEqual(b['7']['inputs']['model'],['50',0])
        self.assertEqual(b['9']['inputs']['sigmas'],'1,0.995633187773,0')
        self.assertEqual([b['50']['inputs'][x] for x in ('step_start','step_end')],[0,2])
        f.pop('52');f['7']['inputs']['model']=['50',0];f['9']=copy.deepcopy(b['9']);f['50']['inputs']['step_start']=0;f['50']['inputs']['step_end']=2
        self.assertEqual(b,f)

    def test_graph_links_and_paths(self):
        for name in (*ARMS,'spatial_bench2'):
            g=graph(name)
            for node in g.values():
                for key,value in node['inputs'].items():
                    if isinstance(value,list):self.assertIn(value[0],g);self.assertIsInstance(value[1],int)
                    if key.endswith('dir'):
                        self.assertTrue(value.startswith(REMOTE+'/'))
                        with patch.object(Path,'mkdir'):
                            self.assertEqual(str(audit_root(value)),value)

    def test_exact_event_path_guard_rejects_other_roots_and_escapes(self):
        bad=['relative/audit','/data5/researcher/h3_runs/timing_spatial_r3_20261016_bad/audit','/data5/researcher/h3_runs/timing_autoresearch_20261016/audit',REMOTE+'/../escaped', '/tmp/timing_spatial_r3_20261016/audit']
        for path in bad:
            with self.subTest(path=path),patch.object(Path,'mkdir'),self.assertRaises(ValueError):audit_root(path)

    def test_host_constants_whitelist_and_sealed_queue(self):
        self.assertEqual(str(service.RUN),REMOTE);self.assertEqual(service.PORT,8464)
        self.assertEqual(service.GPU,'GPU-REDACTED')
        self.assertEqual(str(service.CORE),'/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI')
        self.assertEqual(service.PYTHON,'/home/researcher/miniconda3/envs/comfyui/bin/python')
        command=service.command();self.assertIn('H3SpatialMarginalRouter',command);self.assertIn('--use-pytorch-cross-attention',command)
        self.assertNotIn('--use-sage-attention',command)
        queue=json.loads((ROOT/'configs/queue.json').read_text())
        self.assertTrue(queue['sealed']);self.assertEqual(queue['jobs'],['r3_s05_spatial_bench2',*['r3_s05_'+n for n in ARMS]])
        admission=json.loads((ROOT/'configs/admission.json').read_text())
        self.assertEqual(admission,{'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})

    def test_admission_no_blanket_permission_and_other_users_not_interfered_with(self):
        a={'scope':'own_user_video_jobs','permitted_compute_processes':[]};empty={'queue_running':[],'queue_pending':[]}
        service.check_admission(a,[],empty)
        with self.assertRaises(RuntimeError):service.check_admission(a,[{'gpu_uuid':service.GPU,'pid':100}],empty)
        with patch.object(service,'proc_uid',return_value=service.os.getuid()),patch.object(service,'external_identity',return_value={'uid':service.os.getuid()}),self.assertRaises(RuntimeError):
            service.check_admission(a,[{'gpu_uuid':'GPU-other','pid':100}],empty)
        with patch.object(service,'proc_uid',return_value=service.os.getuid()+1):
            service.check_admission(a,[{'gpu_uuid':'GPU-other','pid':100}],empty)

    def test_models_match_recorded_old9_provenance(self):
        parent=json.loads((ROOT/'configs/parent_runtime_provenance.json').read_text())
        hashes=json.loads((ROOT/'configs/model_hashes_host9.json').read_text())
        self.assertEqual(len(parent['models']),4)
        for name,record in parent['models'].items():self.assertEqual(record['prior_full_sha256'],hashes[name]['sha256'])
        self.assertEqual(len(json.loads((ROOT/'configs/parent_core_hashes.json').read_text())),9)


if __name__=='__main__':unittest.main()
