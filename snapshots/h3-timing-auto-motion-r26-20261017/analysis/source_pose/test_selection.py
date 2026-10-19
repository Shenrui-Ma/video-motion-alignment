import importlib.util,json,unittest
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('selection',P/'select_clips.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Test(unittest.TestCase):
 def test_nms(self):
  e=[{'frame':i,'strength':v} for i,v in [(10,1),(11,3),(18,1),(19,2),(30,1)]]
  self.assertEqual([x['frame'] for x in m.nms(e,0,40,8,5)],[11,19,30])
 def test_no_border_events(self):self.assertEqual(m.nms([{'frame':4,'strength':1},{'frame':36,'strength':1}],0,40,8,5),[])
 def test_inbounds_ambiguous(self):
  xy=np.ones((2,17,2))*100;cf=np.ones((2,17));amb=np.array([False,True]);v,a,c=m.masks(xy,cf,amb,.3);self.assertTrue(a[0]);self.assertFalse(a[1]);xy[0,9,0]=1312;v,a,c=m.masks(xy,cf,amb,.3);self.assertFalse(c[0][0])
 def test_constant_selects_earliest(self):
  pr=json.loads((P.parents[1]/'configs/source_selection_protocol.json').read_text());xy=np.stack([np.arange(17)*15+100,np.arange(17)*7+100],1).tolist();raw={'frames':[{'frame':i,'selection_ambiguous':False,'selected_person':0,'persons':[{'coco17_xy':xy,'coco17_score':[1.]*17}]} for i in range(160)],'statistics':{}}
  r=m.analyze(raw,pr);self.assertEqual(r['selected']['start_frame'],0);self.assertEqual(r['selected']['visibility_tier'],2);self.assertEqual(r['selected']['reversal_event_count'],0)
 def test_missing_is_unknown(self):
  pr=json.loads((P.parents[1]/'configs/source_selection_protocol.json').read_text());raw={'frames':[{'frame':i,'selection_ambiguous':False,'selected_person':None,'persons':[]} for i in range(141)],'statistics':{}};r=m.analyze(raw,pr);self.assertEqual(r['selected']['visibility_tier'],0);self.assertEqual(r['selected']['status'],'UNKNOWN_support')
 def test_known_geometric_reversal(self):
  pr=json.loads((P.parents[1]/'configs/source_selection_protocol.json').read_text());n=41
  xy=np.tile(np.array([[100.+i*10,200.+i*5] for i in range(17)])[None],(n,1,1));cf=np.ones((n,17));amb=np.zeros(n,dtype=bool)
  theta=np.deg2rad(80.-10.*np.abs(np.arange(n)-20))
  xy[:,7]=xy[:,5]+100*np.stack([np.cos(theta),np.sin(theta)],1);xy[:,9]=xy[:,7]+np.array([60.,0.])
  events=m.signals(xy,cf,amb,pr)
  self.assertTrue(any(abs(e['frame']-20)<=1 and 0 in e['reversing_bone_indices'] for e in events))
if __name__=='__main__':unittest.main()
