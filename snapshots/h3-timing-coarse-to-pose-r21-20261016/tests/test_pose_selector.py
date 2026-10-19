import ast,copy,hashlib,importlib.util,json,pathlib,sys,unittest
from pose_test_support import measurement
R=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'extensions'))
from H3CoarsePoseObserverRouter.selector import select,pose_select
from H3CoarsePoseObserverRouter.observer import next_decision

def obs(lag):return {'accepted':lag is not None,'best':{'lag_frames':lag}}
def pure(path,name):
 tree=ast.parse(path.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name);scope={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),scope);return scope[name]
class SelectorTest(unittest.TestCase):
 def test_prefix_no_warm_start(self):
  for n in range(6):self.assertFalse(select(n,None,obs(24),False)['chosen_full'])
  self.assertFalse(select(6,None,obs(3),False)['chosen_full'])
 def test_all_early_lags_exact_R12(self):
  old=pure(R/'configs/r12_observer_reference.py','next_decision')
  for prev in (False,True):
   for lag in list(range(-24,25))+[None]:
    for n in range(6,10):
     actual=select(n,None,obs(lag),prev);self.assertEqual((actual['chosen_full'],actual['reason']),old(obs(lag),prev))
 def test_hysteresis_sequences(self):
  for lags,wanted in [([3,4,3,3],[False,True,True,True]),([4,None,3,3],[True,False,False,False]),([4,3,0,3],[True,True,False,False])]:
   prev=False;actual=[]
   for n,lag in enumerate(lags,6):
    dec=select(n,None,obs(lag),prev);prev=dec['chosen_full'];actual.append(prev)
   self.assertEqual(actual,wanted)
 def test_late_exact_R19_and_reentry(self):
  spec=importlib.util.spec_from_file_location('old_select',R/'configs/r19_selector_reference.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
  cases=[([3]*4,()),([2,-2,0,1],()),([-3]*4,()),([4,4,2,4],()),([None]*4,()),([5]*4,['confounded']),([True]*4,()),([3.0]*4,())]
  for n in range(10,20):
   for values,reasons in cases:
    for prev in (True,False):
     actual=select(n,measurement(values,reasons),obs(10),prev);expected=old.select(n,measurement(values,reasons))
     self.assertEqual({k:v for k,v in actual.items() if k not in ('stage','previous_actual_full')},expected)
  self.assertFalse(select(10,measurement([None]*4),obs(10),True)['chosen_full'])
  self.assertTrue(select(11,measurement([3]*4),obs(-1),False)['chosen_full'])
 def test_bad_input_aborts(self):
  for n in (-1,20,10.,True):
   with self.assertRaises(ValueError):select(n,measurement([4]*4))
  for lag in (True,4.0,25,-25):
   with self.assertRaises(ValueError):select(6,None,obs(lag),False)
  with self.assertRaises(ValueError):select(6,None,None,False)
  for value in (None,{}, {'status':'failed'}, {'status':'complete'}):
   with self.assertRaises((ValueError,KeyError,TypeError)):select(10,value)
 def test_actual_historical_early_trace(self):
  rows=json.loads((R/'configs/r12_decisions.json').read_text())['rows'];prev=False
  for row in rows[6:10]:
   lag=row['internal_readouts']['native']['lag_frames'];dec=select(row['physical_index_zero_based'],None,obs(lag),prev)
   self.assertEqual(dec['chosen_full'],row['chosen_branch']=='full');self.assertEqual(dec['reason'],row['decision']['applied_reason']);prev=dec['chosen_full']
  rows=json.loads((R/'configs/parent_r14_feedback.json').read_text())['feedback']['observations'];prev=False
  for row in rows:
   if 6<=row['callback_index']<=9:
    self.assertEqual(len(row['observation']['curve']),49)
    dec=select(row['callback_index'],None,row['observation'],prev);self.assertFalse(dec['chosen_full']);prev=dec['chosen_full']
if __name__=='__main__':unittest.main()
