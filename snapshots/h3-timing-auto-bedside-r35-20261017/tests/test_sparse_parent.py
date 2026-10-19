import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import torch
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'extensions'),str(R/'scripts')]
from H3AutomaticWindowRouter import pair_gate as g

class SparseParentTests(unittest.TestCase):
 def test_signature_only_is_explicit_and_rejects_shape_dtype_bytes(self):
  x=torch.arange(24,dtype=torch.float32).reshape(1,3,8)
  expected=g.signature_without_bytes(g.readout.tensor_signature(x))
  s=SimpleNamespace(guider=SimpleNamespace(original_conds={'positive':[{'cross_attn':x}]}))
  record=g.check_parent_embedding(s,{}, {'conditioning_embedding':expected})
  self.assertTrue(record['actual_signature_equal']);self.assertIsNone(record['actual_tensor_equal']);self.assertFalse(record['historical_tensor_available'])
  for y in (x+1,x.double(),x.reshape(1,4,6)):
   s.guider.original_conds['positive'][0]['cross_attn']=y
   with self.assertRaises(ValueError):g.check_parent_embedding(s,{}, {'conditioning_embedding':expected})
 def test_early_on_never_waits_for_historical_005(self):
  for first in (1,4,5,10,None):
   gate=g.HistoricalPairGate();gate.records={i:{} for i in (5,10,15,19)}
   s=SimpleNamespace(audit={'counterfactual':{}})
   if first is not None:gate.decision(s,first,{'chosen_full':True})
   gate.done={n for n in gate.records if first is None or n<=first};gate.finish(s)
   expected=first is not None and first<5
   self.assertEqual(s.audit['counterfactual']['native_preservation']['prefix_evidence']=='prefix_unavailable_due_to_early_intervention',expected)
   if first is not None:self.assertFalse(gate.native_comparable(first+1))
 def test_missing_eligible_old_checkpoint_rejected(self):
  gate=g.HistoricalPairGate();gate.records={5:{}};gate.first_on=10
  with self.assertRaises(ValueError):gate.finish(SimpleNamespace(audit={'counterfactual':{}}))
 def test_no_future_native_requalification_after_off(self):
  gate=g.HistoricalPairGate();s=SimpleNamespace(audit={'counterfactual':{}})
  gate.decision(s,4,{'chosen_full':True});gate.decision(s,10,{'chosen_full':False})
  self.assertEqual(gate.first_on,4);self.assertFalse(gate.native_comparable(10))

if __name__=='__main__':unittest.main()
