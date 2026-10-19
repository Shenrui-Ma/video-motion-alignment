import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'analysis/postrun')]
import r119_contract as c
import verify_pair as verify

class BasketballContract(unittest.TestCase):
    def test_single_native_then_guided(self):
        jobs,order=c.registry()
        self.assertEqual(len(order),2)
        self.assertEqual([jobs[x]['arm'] for x in order],['native','forced'])
        for run in order:c.validate_job(run)

    def test_native_only_prompt_admin_changes_relative_R110(self):
        s=c.read(ROOT/'configs/scientific_contract.json');case=s['cases'][0]
        old=c.read(ROOT/case['parent_graph']);new=c.read(ROOT/'configs/graphs'/(case['run_id']+'.json'))
        changed=[]
        self.assertEqual(set(old),set(new))
        for node in old:
            self.assertEqual(old[node]['class_type'],new[node]['class_type'])
            self.assertEqual(set(old[node]['inputs']),set(new[node]['inputs']))
            changed += [(node,k) for k in old[node]['inputs'] if old[node]['inputs'][k]!=new[node]['inputs'][k]]
        allowed={('5','prompt'),('5','run_id'),('51','source_run_id'),('6','pair_id'),('14','filename_prefix')}
        allowed |= {(n,'run_id') for n in ('6','50','51','52')}
        allowed |= {('5','audit_dir'),('6','audit_dir'),('50','audit_dir'),('51','source_audit_dir'),('52','output_dir')}
        self.assertEqual(set(changed),allowed)

    def test_geometry_and_partial_last_bin(self):
        case=c.read(ROOT/'configs/scientific_contract.json')['cases'][0]
        self.assertEqual(c.latent_shapes(case)['video'],(1,24,32,46,82))
        self.assertEqual(c.routing_layout(case)['latent_interval_half_open'],[0,32])
        self.assertEqual(c.routing_layout(case)['pixel_interval_inclusive'],[0,104])
        self.assertEqual(c.routing_layout(case)['pure_pad_bins'],[])

    def test_prompt_is_verbatim_official_edit_instruction(self):
        science=c.read(ROOT/'configs/scientific_contract.json')
        for case in science['cases']:
            self.assertEqual(c.PROMPT,case['original_task']['edit_prompt'])
            graph=c.read(ROOT/'configs/graphs'/(case['run_id']+'.json'))
            self.assertEqual(graph['5']['inputs']['prompt'],case['original_task']['edit_prompt'])
        self.assertEqual(c.PROMPT,'Replace the basketball with a neon-lit ball')
        self.assertIn('Source opening already crops the head',c.read(ROOT/'design/SOURCE_ACCEPTANCE.json')['source_observation'])

    def test_expected_visual_inputs_and_noise(self):
        e=c.read(ROOT/'design/EXPECTED_SOURCE_SIGNATURES.json')
        condition={k:copy.deepcopy(e[k]) for k in ('input_video','native_vae_calls','qwen_presentation')}
        condition['pair_snapshot']={'actual':{k:copy.deepcopy(e[k]) for k in ('references','target_latent_shapes','target_latent_dtypes')}}
        noise={'signature':copy.deepcopy(e['noise_signature']),'actual_noise_streams':copy.deepcopy(e['actual_noise_streams'])}
        self.assertTrue(all(verify.source_inputs_match(condition,noise,ROOT).values()))
        condition['native_vae_calls'][0]['prepared_frames']['shape'][1]+=16
        self.assertFalse(verify.source_inputs_match(condition,noise,ROOT)['prepared_RGB_and_clean_VAE_match_R110_source'])
        noise['actual_noise_streams'][0]['sha256']='changed'
        self.assertFalse(verify.source_inputs_match(condition,noise,ROOT)['initial_AV_noise_matches_R110_source'])

    def test_reference_packed_geometry(self):
        e=c.read(ROOT/'design/EXPECTED_SOURCE_SIGNATURES.json')
        segments=[[0,99,'text'],[99,30275,'ref_img'],[30275,30631,'audio'],[30631,60807,'video']]
        packed={'segments':segments,'seq_len':60807}
        condition={'native_vae_calls':e['native_vae_calls'],'target_latent_shapes':e['target_latent_shapes'],'packed_layout':packed,'pair_snapshot':{'actual':{'references':e['references'],'target_latent_shapes':e['target_latent_shapes'],'packed_layout':copy.deepcopy(packed)}}}
        plan={'reference_image_segments':[],'reference_video_segment':segments[1][:2],'target_video_segment':segments[3][:2]}
        self.assertTrue(verify.reference_geometry_matches(condition,{},plan))
        plan['reference_video_segment'][0]+=1
        self.assertFalse(verify.reference_geometry_matches(condition,{},plan))

    def test_numerical_kernels_byte_equal(self):
        for path,row in c.read(ROOT/'configs/runtime_kernel_hashes.json').items():
            self.assertEqual(c.sha(ROOT/path),row['parent_sha256'])
            self.assertTrue(row['byte_equal'])

    def test_source_files_reuse_R110(self):
        source=c.definitions()[0]['source']
        for key in ('video','original','provenance'):
            self.assertEqual(c.sha(ROOT/'inputs'/source[key]),source[key+'_sha256'])

if __name__=='__main__':unittest.main()
