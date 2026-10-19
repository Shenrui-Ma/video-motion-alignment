"""Small CPU tensors exercise independent parent/input/prefix comparisons."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions')]
from execution_contract import PARENT_PRODUCER, file_record
from H3X0Readout.core import tensor_signature
from verify_parent_payloads import signature, compare_clean_inputs, compare_prefix


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class ActualParentPayloads(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'new';self.parent=Path(self.tmp.name)/'old'
        self.root.mkdir();self.parent.mkdir();self.inventory={}
        run='r59_fixture_visible_only'
        self.case={'run_id':run,'parent_run':'r57_fixture_native','seed':123,'parent_root':str(self.parent),
                   'parent_conditioning':'parent_condition.json','parent_file_inventory':'parent_files.json','parent_noise':'parent_noise.json'}
        values=[]
        for i in range(6):
            tensor=torch.arange(8,dtype=torch.float32).reshape(2,4)+i
            relative='tensors/'+str(i)+'.pt'
            for base in (self.root,self.parent):
                path=base/'audit'/relative;path.parent.mkdir(parents=True,exist_ok=True);torch.save(tensor,path)
            self.inventory['audit/'+relative]=file_record(self.parent/'audit'/relative)
            values.append(dict(signature(tensor),tensor_file=relative))
        condition={'prompt':'P1','input_video':{},'native_vae_calls':[{'prepared_frames':values[0],'latent':values[1]}],
                   'qwen_presentation':[{'actual_sampled_frames':values[2]}],'tokenization_before_vision_expansion':{},
                   'conditioning_embedding':values[3],'token_tags':values[4], 'target_latent_shapes':[],
                   'packed_layout':{'position_ids':values[5]}}
        write(self.root/'parent_condition.json',condition);write(self.root/'audit'/(run+'_conditioning.json'),condition)
        tensors=[torch.arange(4,dtype=torch.float32),torch.arange(2,dtype=torch.float32)]
        hashes=[signature(x) for x in tensors];sig={'seed':123,'shapes':[[4],[2]]}
        payload={'signature':sig,'tensors':tensors,'hashes':hashes}
        current=self.root/'audit'/(run+'_noise_noise.pt');old=self.parent/'audit/parent_noise.pt'
        torch.save(payload,current);torch.save(payload,old);self.inventory['audit/parent_noise.pt']=file_record(old)
        write(self.root/'audit'/(run+'_noise.json'),{'signature':sig,'actual_noise_streams':hashes,'cache_file':str(current)})
        write(self.root/'parent_noise.json',{'signature':sig,'actual_noise_streams':hashes,'cache_file':str(PARENT_PRODUCER/'audit/parent_noise.pt')})
        write(self.root/'parent_files.json',self.inventory)

    def tearDown(self): self.tmp.cleanup()

    def test_six_clean_tensors_and_initial_AV_noise_equal(self):
        result=compare_clean_inputs(self.root,self.case)
        self.assertEqual(len(result['clean_tensor_pairs']),6)
        self.assertTrue(result['actual_clean_inputs_equal'])
        self.assertTrue(result['initial_video_audio_noise_equal'])
        self.assertFalse(torch.cuda.is_initialized())

    def test_changed_current_reference_payload_rejected(self):
        torch.save(torch.zeros((2,4)),self.root/'audit/tensors/1.pt')
        with self.assertRaisesRegex(ValueError,'clean tensor signature'):
            compare_clean_inputs(self.root,self.case)

    def test_changed_archived_payload_rejected_even_if_manifest_unchanged(self):
        torch.save(torch.zeros((2,4)),self.parent/'audit/tensors/1.pt')
        with self.assertRaisesRegex(ValueError,'parent payload changed'):
            compare_clean_inputs(self.root,self.case)

    def test_changed_actual_noise_rejected(self):
        path=self.root/'audit'/(self.case['run_id']+'_noise_noise.pt')
        value=torch.load(path,weights_only=True);value['tensors'][1]+=1;torch.save(value,path)
        with self.assertRaisesRegex(ValueError,'noise stream signature'):
            compare_clean_inputs(self.root,self.case)

    def test_independent_prefix_compares_actual_tensors(self):
        value={'video':torch.ones(2,3),'audio':torch.ones(2,2)}
        record={'step_zero_based':3,'file':'x0_step003.pt',**{k:tensor_signature(v) for k,v in value.items()}}
        relative='audit/x0/'+self.case['parent_run']+'/x0_step003.pt';path=self.parent/relative
        path.parent.mkdir(parents=True);torch.save(value,path);inventory={relative:file_record(path)}
        self.assertTrue(compare_prefix(self.case,inventory,record,3,value)['actual_video_audio_tensor_equal'])
        changed=copy.deepcopy(value);changed['audio']+=1
        with self.assertRaisesRegex(ValueError,'Native prefix differs'):
            compare_prefix(self.case,inventory,record,3,changed)


if __name__=='__main__':unittest.main()
