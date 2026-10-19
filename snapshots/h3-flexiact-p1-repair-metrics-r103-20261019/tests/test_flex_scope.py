import copy,json,tempfile,sys,unittest,base64
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import common as c
import render_native as native
import render_pair as pair
import test_consumer

class FlexScope(unittest.TestCase):
 def test_native_sampling_and_image_checks(self):
  f=test_consumer.GateTests();f.setUp()
  for edit in [lambda g:g['runs']['native'].update(evaluation_indices=list(range(49))),lambda g:g['runs']['native'].update(evaluation_fps=24),lambda g:g['checks'].pop('native_reference_geometry')]:
   v=copy.deepcopy(f.g);edit(v)
   with self.assertRaises(ValueError):c.verify_gate(v,f.source,f.owner)
 def test_source_identity_and_layout_contract(self):
  for p in c.config()['sources']:
   self.assertEqual(p['geometry'],dict(width=1152,height=768,frames=158,fps=24));self.assertEqual(p['valid_frames'],147);self.assertEqual(p['evaluation_indices'],list(range(0,147,3)));self.assertEqual(p['crop_xywh'],[0,0,1152,768]);self.assertEqual(c.sha(c.ROOT/p['portrait']['file']),p['portrait']['sha256'])
  self.assertEqual(c.info('human2animal_2__game_man_4')['original_task']['group'],'official_assets_crosspair_extension')
  self.assertEqual(c.info('chest__game_girl_1')['reference_image_expected']['expected_DiT_visual_patch_tokens'],135)
 def test_native_and_pair_html_embed_original_portrait(self):
  for module,mode,columns in [(native,'Native-only',['source','native']),(pair,'Native+fixed guidance',['source','native','forced'])]:
   with tempfile.TemporaryDirectory() as temp:
    d=Path(temp);(d/'movie.mp4').write_bytes(b'SYNTHETIC DISPLAY FIXTURE');p=copy.deepcopy(c.info(c.SOURCES[0]));p.update(display_task='合成展示回归，非实验结果',prompt='SYNTHETIC FIXTURE',valid_frames=18)
    m=dict(mode=mode,columns=columns,videos=[dict(file='movie.mp4',sha256=c.sha(d/'movie.mp4'))],contact_sheets=[])
    (d/'PRESENTATION.json').write_text(json.dumps(m));out=d/'fixture.html'
    with patch.object(module,'info',return_value=p):module.publish(c.SOURCES[0],d,out)
    text=out.read_text();expected=base64.b64encode((c.ROOT/p['portrait']['file']).read_bytes()).decode()
    self.assertIn(expected,text);self.assertIn('目标角色参考图',text);self.assertIn('FlexiAct',text);self.assertNotIn('IVEBench',text)
if __name__=='__main__':unittest.main()
