import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'extensions'))
from H3EventAudit import H3EventAuditNoise, audit_root


class GraphContractTests(unittest.TestCase):
    def test_frozen_graphs_only_operator_and_audit_identity_changes(self):
        base=json.loads((ROOT/'configs/parent_full_graph.json').read_text())
        remote='/data5/researcher/h3_runs/timing_phase_rope_r17_20261016'
        for arm,delta in [('plus4',4.),('minus4',-4.),('zero',0.)]:
            rid=f'r17_s05_{arm}_a05_6to14'
            graph=json.loads((ROOT/'configs'/f'{rid}.json').read_text())
            expected=copy.deepcopy(base)
            for node in expected.values():
                for key,value in node['inputs'].items():
                    if isinstance(value,str):
                        node['inputs'][key]=value.replace('/data5/researcher/h3_runs/timing_spatial_r3_20261016',remote).replace('r3_s05_full_6to14',rid).replace('05_sam_1312x736_shared_v3','05_sam_1312x736_shared_r17').replace('05_sam_1312x736_2026101311_v3','05_sam_1312x736_2026101311_r17')
            expected['50']={'class_type':'H3PhaseRoPE','inputs':{'model':['41',0],'positive':['51',0],
                'delta_frames':delta,'alpha':.5,'start_frame':50,'end_frame':65,'block_start':0,
                'block_end':50,'step_start':6,'step_end':15,'run_id':rid,'audit_dir':remote+'/audit/phase_rope'}}
            self.assertEqual(graph,expected)
            # Execute the actual auxiliary node's path-validation entry, not a copied regex.
            with patch.object(Path,'mkdir'):
                noise=H3EventAuditNoise().get_noise(**graph['6']['inputs'])
                self.assertEqual(len(noise),1)
                self.assertEqual(str(audit_root(graph['5']['inputs']['audit_dir'])),remote+'/audit')
            self.assertEqual(graph['7']['inputs']['model'],['52',0])
            self.assertEqual(graph['52']['inputs']['model'],['50',0])

    def test_old_or_escaping_auxiliary_path_refused(self):
        for p in ['/tmp','/data5/researcher/h3_runs/timing_spatial_r3_20261016/audit',
                  '/data5/researcher/h3_runs/timing_phase_rope_r17_20261016/../bad']:
            with self.assertRaises(ValueError): audit_root(p)

    def test_parent_evidence_pins_and_queue(self):
        protocol=json.loads((ROOT/'configs/protocol.json').read_text())
        for name,digest in protocol['parent_evidence_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/'configs'/name).read_bytes()).hexdigest(),digest)
        q=json.loads((ROOT/'configs/queue.json').read_text())
        self.assertEqual(q,{'jobs':protocol['run_ids'],'sealed':True})


if __name__=='__main__': unittest.main()
