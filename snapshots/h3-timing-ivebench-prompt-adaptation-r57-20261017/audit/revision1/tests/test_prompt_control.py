"""Falsifiable preparation checks; no model, CUDA or remote service."""
import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r57_contract as c
import preflight,service,materialize_inputs

class PromptControl(unittest.TestCase):
 def test_exact_five_template_from_official_metadata(self):
  science=c.read(ROOT/'configs/scientific_contract.json')
  self.assertEqual([x['source_id'] for x in science['cases']],list(c.SOURCES))
  for case in science['cases']:
   self.assertEqual(case['prompt'],c.TEMPLATE.format(**case['original_task']))
   self.assertEqual((ROOT/case['prompt_file']).read_text(),case['prompt'])
   self.assertEqual(c.sha(ROOT/case['prompt_file']),case['prompt_sha256'])
 def test_actual_parent_only_prompt_scientific_change(self):
  jobs,order=c.registry(ROOT)
  for run in order:
   row=c.validate_job(run);g=c.read(ROOT/'configs/graphs'/f'{run}.json');case=row['case']
   expected=c.expected_graph(ROOT,case)
   self.assertEqual(g,expected)
   self.assertEqual(g['6']['inputs']['noise_seed'],2026101701)
   self.assertNotIn('21',g);self.assertNotIn('ref_image',g['5']['inputs'])
   parent=c.read(ROOT/case['parent_graph'])
   for node in ['1','2','3','4','7','8','9','10','11','12','13','22','23','41']:self.assertEqual(g[node],parent[node],node)
 def test_noise_mutation_rejected(self):
  case=c.read(ROOT/'configs/scientific_contract.json')['cases'][0];run=case['run_id'];g=c.expected_graph(ROOT,case);g['6']['inputs']['noise_seed']+=1
  real=c.read
  def tamper(path):return g if str(path).endswith('/configs/graphs/'+run+'.json') else real(path)
  with patch.object(c,'read',side_effect=tamper):
   with self.assertRaisesRegex(ValueError,'actual graph changed'):c.validate_job(run)
 def test_unknown_case_rejected(self):
  with self.assertRaisesRegex(ValueError,'unknown case'):c.validate_job('r57_unknown_native')
 def test_wrong_parent_hash_rejected(self):
  real=c.sha
  with patch.object(c,'sha',side_effect=lambda p:'0'*64 if str(p).endswith('/configs/parents/short_0210/graph.json') else real(p)):
   with self.assertRaisesRegex(ValueError,'parent graph differs'):c.registry()
 def test_actual_parent_input_proofs(self):
  proof=c.verify_parent_metadata();self.assertEqual(proof['actual_input_bindings'],20)
 def test_valid_prefixes_and_native_route(self):
  s=c.read(ROOT/'configs/scientific_contract.json');self.assertEqual([r['valid_frame_count'] for r in s['cases']],[87,86,74,78,89]);self.assertEqual(s['routed_blocks_per_job'],0)
  self.assertEqual(s['geometry'],{'width':1312,'height':736,'frames':90,'fps':24})
 def test_runtime_native_same_startup_settings(self):
  args=service.command();self.assertNotIn('--reserve-vram',args);self.assertNotIn('--fast',args)
  self.assertIn('--use-pytorch-cross-attention',args);self.assertIn('--enable-triton-backend',args)
  self.assertNotIn('H3AutomaticWindowRouter',args)
 def test_pending_blocks_actual_launch(self):
  with self.assertRaisesRegex(ValueError,'root must verify'):preflight.check(ROOT,live=True)
 def test_mac_input_materialization_refused(self):
  with self.assertRaisesRegex(ValueError,'remote materialization'):materialize_inputs.materialize(ROOT)
 def test_paired_noise_requires_actual_signature(self):
  folder=ROOT/'configs/parents/short_0210'
  reference=c.read(folder/'r54_short_0210_shared_conditioning.json');noise=c.read(folder/'r54_short_0210_seed2026101701_native_noise.json')
  self.assertTrue(all(c.paired_input_checks(reference,reference,noise,noise).values()))
  changed=copy.deepcopy(noise);changed['actual_noise_streams'][0]['sha256']='0'*64
  self.assertFalse(c.paired_input_checks(reference,reference,changed,noise)['initial_AV_noise_equal_P0'])
 def test_paired_reference_rejects_latent_change_but_accepts_text_change(self):
  folder=ROOT/'configs/parents/short_0210';reference=c.read(folder/'r54_short_0210_shared_conditioning.json');noise=c.read(folder/'r54_short_0210_seed2026101701_native_noise.json')
  changed=copy.deepcopy(reference);changed['prompt']='new P1';changed['conditioning_embedding']['sha256']='0'*64
  self.assertTrue(c.paired_input_checks(changed,reference,noise,noise)['reference_equal_P0'])
  changed['native_vae_calls'][0]['latent']['sha256']='0'*64
  self.assertFalse(c.paired_input_checks(changed,reference,noise,noise)['reference_equal_P0'])
 def test_unsafe_input_name_rejected(self):
  with self.assertRaisesRegex(ValueError,'unsafe input'):c.input_path(ROOT,'../x')
 def test_frozen_source_mutation_rejected(self):
  real=preflight.sha
  with patch.object(preflight,'sha',side_effect=lambda p:'0'*64 if str(p).endswith('design/P1_TEMPLATE.txt') else real(p)):
   with self.assertRaisesRegex(ValueError,'source/design freeze'):preflight.check(ROOT)
if __name__=='__main__':unittest.main()
