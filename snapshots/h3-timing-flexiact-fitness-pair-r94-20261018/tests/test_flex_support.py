import ast,importlib.util,json,math,sys,unittest
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from r94_contract import read,registry,sha,expected_graph
import test_first_pair

class FlexSupportTests(unittest.TestCase):
 def test_original_science_inputs_retained(self):
  jobs,order=registry(ROOT)
  for run in order:
   c=jobs[run]['case'];old=read(ROOT/c['parent_graph']);new=read(ROOT/'configs/graphs'/f'{run}.json')
   for node in ('1','2','3','4','41','7','8','9','10','11','12','13','23'):self.assertEqual(old[node],new[node])
   for key in ('width','height','length','semantic_fps','phase_frames','ref_image','ref_video'):self.assertEqual(old['5']['inputs'][key],new['5']['inputs'][key])
   self.assertEqual(old['6']['inputs']['noise_seed'],new['6']['inputs']['noise_seed'])
   self.assertEqual(new['50']['inputs']['end_frame'],146)
   self.assertEqual(c['evaluation_indices'],list(range(0,147,3)))
   self.assertEqual(new['22']['inputs']['file'],c['video'])
 def test_reference_image_is_loaded_and_hashed(self):
  jobs,order=registry(ROOT)
  for run in order:
   c=jobs[run]['case'];self.assertEqual(sha(ROOT/'inputs'/c['portrait']),c['portrait_sha256'])
   self.assertEqual(read(ROOT/'configs/graphs'/f'{run}.json')['21']['inputs']['image'],c['portrait'])
 def test_position_bin_boundary_mapping(self):
  spec=importlib.util.spec_from_file_location('r94layout',ROOT/'extensions/H3TemporalRouter/layout.py');layout=importlib.util.module_from_spec(spec);spec.loader.exec_module(layout)
  self.assertEqual(layout.event_latent_range(0,146,47),(0,44));self.assertEqual(sum(layout.frame_spans(47)[:44]),149);self.assertEqual(sum(layout.frame_spans(47)),158)
  rows=864;refs=[{'kind':'image','index':0,'latent_t':1,'latent_h':48,'latent_w':72,'frame_rows':rows,'ref_audio_t':0},{'kind':'video','index':1,'latent_t':47,'latent_h':48,'latent_w':72,'frame_rows':rows,'ref_audio_t':0}]
  meta={'text_len':80,'context_shape':[1,80,5120],'refs':refs};segments=[(0,80,'text'),(80,944,'ref_img'),(944,944+47*rows,'ref_img'),(944+47*rows,944+47*rows+526,'audio'),(944+47*rows+526,944+94*rows+526,'video')]
  plan=layout.validate_layout(meta,SimpleNamespace(signature=(80,47,48,72,263),seq_len=segments[-1][1],segments=segments),0,146)
  self.assertEqual(plan['latent_interval_half_open'],[0,44]);self.assertEqual(plan['position_bin_coverage_inclusive'],[0,148]);self.assertEqual(plan['reference_image_segments'],[[80,944]])
 def test_pure_padding_queries_unchanged_by_route(self):
  import torch
  torch.set_num_threads(1);torch.manual_seed(12)
  q,k,v=[torch.randn(1,2,197,4) for _ in range(3)]
  def attention(q,k,v):
   logits=q@k.transpose(-1,-2)/2;return logits.softmax(-1)@v,logits.logsumexp(-1)
  plan={'query_interval_half_open':[0,88],'reference_video_segment':[94,188],'latent_interval_half_open':[0,44],'frame_rows':2}
  f=test_first_pair.MathematicsTests.functions(ROOT/'extensions/H3TemporalRouter/core.py')['route_attention']
  base=f(q,k,v,2,plan,mode='native',attention=attention);changed=f(q,k,v,2,plan,mode='mass_preserve',attention=attention)
  self.assertTrue(torch.equal(base[:,88:],changed[:,88:]));self.assertFalse(torch.equal(base[:,:88],changed[:,:88]))
if __name__=='__main__':unittest.main(verbosity=2)
