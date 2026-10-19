import gc
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import uuid

import torch

from fork_support import make_case, execute, ROOT
from H3OneStepForkAudit.core import restore_uuid, readout


class ForkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def test_exact_six_probes_and_archives(self):
        with tempfile.TemporaryDirectory() as d:
            case=make_case(Path(d));s,g,noise,w=case
            result=execute(case)
            self.assertTrue(torch.equal(result,torch.zeros_like(noise)))
            self.assertEqual(s.audit['status'],'complete')
            self.assertEqual(s.audit['completed_calls'],300)
            self.assertEqual(s.audit['routed_calls'],0)
            self.assertEqual(s.audit['fork']['sampler_callbacks'],0)
            self.assertEqual(s.audit['fork']['euler_updates'],0)
            self.assertEqual([(r['source_euler_index'],r['eval_euler_index'],r['branch']) for r in s.audit['fork']['predictions']],
                [(n,n+1,b) for n in [6,10,14] for b in ['replay_full','fork_native']])
            for pair in s.audit['fork']['pairs']:
                self.assertTrue(pair['full_next_input_exact'] and pair['full_next_endpoint_exact'])
                a=torch.load(pair['u_full']['file'],weights_only=True)['packed']
                b=torch.load(pair['u_native']['file'],weights_only=True)['packed']
                self.assertFalse(torch.equal(a,b))
            for row in s.audit['fork']['predictions']:
                saved=torch.load(row['file'],weights_only=True)
                self.assertEqual(readout.tensor_signature(saved['packed']),row['packed_signature'])
                self.assertEqual(hashlib.sha256(Path(row['file']).read_bytes()).hexdigest(),row['file_sha256'])

    def test_noop_equal_next_states_and_predictions(self):
        with tempfile.TemporaryDirectory() as d:
            case=make_case(Path(d),same=True);execute(case);f=case[0].audit['fork']
            for pair in f['pairs']:
                self.assertEqual(pair['u_full']['packed_signature'],pair['u_native']['packed_signature'])
            for i in range(0,6,2):
                self.assertEqual(f['predictions'][i]['packed_signature'],f['predictions'][i+1]['packed_signature'])

    def test_mutations_fail_closed(self):
        for fail in ['double_forward','rng','input','sigma','condition','grid','endpoint']:
            with self.subTest(fail=fail),tempfile.TemporaryDirectory() as d:
                case=make_case(Path(d),fail=fail)
                with self.assertRaises(ValueError):execute(case)
                self.assertEqual(case[0].audit['status'],'failed')
                self.assertLessEqual(len(case[0].audit['fork']['predictions']),1)
            del case;gc.collect()

    def test_input_gate_prevents_new_nfe(self):
        with tempfile.TemporaryDirectory() as d:
            case=make_case(Path(d));case[0].source.input_data[6][0].add_(0.01)
            with self.assertRaisesRegex(ValueError,'next-input'):execute(case)
            self.assertEqual(case[0].audit['completed_forward_calls'],0)

    def test_callback_and_materialization_guards(self):
        for bad in ['callback','extra_conds']:
            with self.subTest(bad=bad),tempfile.TemporaryDirectory() as d:
                case=make_case(Path(d))
                if bad=='extra_conds':case[0].extra_conds_calls=2
                with self.assertRaises(ValueError):execute(case,callback=(lambda *a:None) if bad=='callback' else None)

    def test_uuid_only_restore_and_protocol(self):
        with tempfile.TemporaryDirectory() as d:
            case=make_case(Path(d));s,g,_,_=case
            old=str(g.original_conds['positive'][0]['uuid'])
            g.original_conds['positive'][0]['uuid']=uuid.uuid4()
            row=restore_uuid(g,s.source);self.assertEqual(row['restored_source_uuid'],old)
            g.original_conds['positive'][0]['tag']+=1
            with self.assertRaisesRegex(ValueError,'beyond UUID'):restore_uuid(g,s.source)
        self.assertEqual(hashlib.sha256((ROOT/'configs/protocol.json').read_bytes()).hexdigest(),
                         '48b89d1b0118e742ef057647b2aea41fde9ae1f78d4f2b5e4051822253750770')

if __name__=='__main__':unittest.main()
