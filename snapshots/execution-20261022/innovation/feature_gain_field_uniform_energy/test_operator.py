"""Compare real original/new operators on shared, exogenous QKV trajectories."""
import unittest
import torch
from feature_gain_field.attention import FeatureConfig as OriginalConfig, feature_attention as original_attention
from .attention import FeatureConfig,feature_attention
from .frozen import load_frozen
from . import test_feature_attention as attention_cases


class OperatorTests(unittest.TestCase):
    def test_same_inputs_preserve_field_candidate_states_and_match_energy(self):
        torch.set_num_threads(1)
        core=load_frozen().core
        args=attention_cases.FeatureAttentionTests().data(frames=7,spatial=5,lo=0,hi=7,h=3,d=8)
        q,k,v,h,plan=args;torch.manual_seed(19);noise=torch.randn_like(v)
        states=[None,None];saw_changed=False
        for step in range(4):
            outputs=[];records=[];updates=[]
            for method,config,state in zip((original_attention,feature_attention),(OriginalConfig(),FeatureConfig()),states):
                record={};update={}
                outputs.append(method(q,k,v+step*.18*noise,h,plan,attention=attention_cases.dense,aligned_attention=core._aligned_attention,
                    config=config,controller_state=state,controller_state_out=update,step_index=step,layer_index=3,
                    diagnostics=record));records.append(record);updates.append(update['next_state'])
            states=updates;old,new=records
            self.assertTrue(torch.equal(old['alpha'],new['candidate_alpha']))
            self.assertTrue(torch.equal(old['bin_energy'],new['bin_energy']))
            for name in ('anchor_temporal','anchor_complement','initialized','anchor_step'):
                self.assertTrue(torch.equal(states[0][name],states[1][name]))
            self.assertLess(abs(float(old['applied_energy']-new['applied_energy'])),
                5e-7*max(float(old['applied_energy']),1e-20))
            mask=new['uniform_energy']['modifiable_mask']
            if bool(mask.any()):
                self.assertTrue(torch.equal(new['alpha'][mask],new['alpha'][mask][0].expand(int(mask.sum()))))
                saw_changed|=not torch.equal(old['alpha'],new['alpha'])
            self.assertEqual(new['attention_calls'],5)
            if step==0:self.assertTrue(torch.equal(outputs[0],outputs[1]))
        self.assertTrue(saw_changed)


if __name__=='__main__':unittest.main()
