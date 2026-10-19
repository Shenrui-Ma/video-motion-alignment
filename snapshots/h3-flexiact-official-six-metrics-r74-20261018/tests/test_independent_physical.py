import copy,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime/physical'));import evaluate
from independent_adapter import independent_targets

def pose(missing=False,malformed=False):
 import numpy as np
 frames=[]
 for i in range(158):
  xy=np.zeros((17,2));xy[5],xy[6],xy[11],xy[12]=[-.4,0],[.4,0],[-.3,1],[.3,1]
  for j in [7,8,9,10]:xy[j]=[np.sin(i*.075+j*.7),np.cos(i*.113+j*.2)]
  c=np.ones(17)
  if missing:c[11:13]=0
  frames.append({'frame':i,'time_s':i/24,'selected_person':0,'persons':[{'coco17_xy':xy.tolist(),'coco17_score':c.tolist()}]})
 if malformed:frames[0]['persons'][0]['coco17_xy']=[[0,0]]
 return {'video':{'width':1152,'height':768,'container_frame_count':158,'fps':24},'frames':frames}
class IndependentTests(unittest.TestCase):
 def test_bad_native_does_not_hide_forced(self):
  s,a,b=pose(),pose(True),pose();old=evaluate.evaluate(s,a,b);self.assertTrue(all(v['status']=='unknown_visibility' for v in old['confidence_results'].values()));new=independent_targets(evaluate.evaluate,s,{'native':a,'forced':b});self.assertTrue(all(v['status']=='unknown_visibility' for v in new['native']['confidence_results'].values()));self.assertTrue(all(v['status']=='measured' for v in new['forced']['confidence_results'].values()))
 def test_bad_source_keeps_both_unknown(self):
  r=independent_targets(evaluate.evaluate,pose(True),{'native':pose(),'forced':pose()});self.assertTrue(all(v['status']=='unknown_visibility' for x in r.values() for v in x['confidence_results'].values()))
 def test_healthy_targets_equal_original(self):
  s,a,b=pose(),pose(),pose();old=evaluate.evaluate(s,a,b);new=independent_targets(evaluate.evaluate,s,{'native':a,'forced':b})
  for name,oldname in [('native','native'),('forced','automatic')]:
   for conf,record in old['confidence_results'].items():
    for before,after in zip(record['rows'],new[name]['confidence_results'][conf]['rows']):self.assertEqual(before['diagnostics'][oldname],after['diagnostic']);self.assertNotIn('common_support',after)
 def test_malformed_stays_technical_error(self):
  with self.assertRaises(ValueError):independent_targets(evaluate.evaluate,pose(),{'native':pose(malformed=True)})
 def test_no_input_mutation_or_duplicate_sample(self):
  s,a=pose(),pose();before=copy.deepcopy((s,a));r=independent_targets(evaluate.evaluate,s,{'forced':a});self.assertEqual((s,a),before);self.assertEqual(list(r),['forced']);self.assertNotIn('paired_lag_summary',r['forced'])
if __name__=='__main__':unittest.main()
