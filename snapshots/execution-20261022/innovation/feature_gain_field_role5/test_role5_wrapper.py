"""Actual frozen wrapper + dense CPU attention, not a generated video result."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import torch
from .attention import FeatureConfig,make_classes
from .audit import check_role5
from .frozen import load_frozen
from . import test_feature_attention as support
from .test_feature_attention import dense


class WrapperRole5Tests(unittest.TestCase):
    def test_complete_wrapper_shadow_audit_and_fault_injections(self):
        torch.set_num_threads(1);core=load_frozen().core;State,Block=make_classes(core)
        q,k,v,heads,plan=support.FeatureAttentionTests().data(frames=15,spatial=2,lo=0,hi=15,h=2,d=4)
        layout=object();inputs={'v':v}
        def attention_pytorch():pass
        def original(args):
            return args['transformer_options']['optimized_attention_override'](
                attention_pytorch,q,k,inputs['v'],heads,skip_reshape=True)
        with tempfile.TemporaryDirectory() as tmp,mock.patch.object(core,'flash_attention_lse',dense):
            state=State({},'mass_preserve',.25,0,0,0,50,0,50,0,20,'role5_full_cpu',tmp,feature_config=FeatureConfig())
            with mock.patch.object(state,'plan_for',return_value=plan):
                for step in range(20):
                    for block in range(50):
                        inputs['v']=v*(1+.01*block)+torch.sin(v*(1+.03*step))*.2
                        args={'layout':layout,'transformer_options':{'block_index':block,
                              'minimax_h3_layout':layout,'sample_sigmas':torch.linspace(1,0,21)}}
                        Block(state,block)(args,{'original_block':original})
            raw=(Path(tmp)/'role5_full_cpu.json').read_bytes();audit=json.loads(raw)
            outcome=check_role5(audit)
            self.assertEqual(outcome['blocks'],1000);self.assertEqual(outcome['shadow_calls'],9)
            self.assertEqual(outcome['shadow_anchors'],15);self.assertEqual(outcome['seam_records_checked'],4000)
            self.assertEqual(set(state.shadow_anchors),{8,25,42})
            self.assertTrue(all(x['last_step']==19 for x in state.shadow_anchors.values()))
            self.assertEqual(len(state.anchors),50)
            if os.environ.get('H3_ROLE5_CPU_FIXTURE_DIR'):
                out=Path(os.environ['H3_ROLE5_CPU_FIXTURE_DIR']);out.mkdir(exist_ok=True,parents=True)
                (out/'full_complete.json').write_bytes(raw)
                (out/'audit_result.json').write_text(json.dumps(outcome,indent=2)+'\n')
            broken=copy.deepcopy(audit);broken['feature_forward_summaries'][0]['layers'][8]['neighbor_previous'][6]+=1
            with self.assertRaisesRegex(ValueError,'previous indices'):check_role5(broken)
            broken=copy.deepcopy(audit);broken['feature_forward_summaries'][9]['layers'][8]['shadow']['anchor_temporal'][6]*=2
            with self.assertRaisesRegex(ValueError,'shadow anchor changed'):check_role5(broken)
            broken=copy.deepcopy(audit);broken['feature_forward_summaries'][1]['layers'][8]['attention_calls']=7
            with self.assertRaisesRegex(ValueError,'total attention'):check_role5(broken)
            self.assertEqual(json.loads(raw),audit)


if __name__=='__main__':unittest.main()
