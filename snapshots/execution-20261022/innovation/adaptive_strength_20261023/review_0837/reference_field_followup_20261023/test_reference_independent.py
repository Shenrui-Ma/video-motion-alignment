"""Independent small NumPy oracles. No real input data or generated metrics."""
import sys, unittest, tempfile, zipfile, io
from pathlib import Path
import numpy as np
sys.path.insert(0,sys.argv.pop(1))
import core, run
FOLDS=[{'train':[0,2,4,6],'test':[1,3,5,7]},{'train':[1,3,5,7],'test':[0,2,4,6]}]
def case(rows):
 t=len(rows);return np.broadcast_to(rows[None,:,None,:],(1,t,8,t)).copy(),np.array([[i*3,i*3] for i in range(t)]),np.ones(t,dtype=bool)
class Independent(unittest.TestCase):
 def test_heldout_never_enters_template_radius_or_weights(self):
  rng=np.random.default_rng(19);p=rng.random((1,7,8,7));p/=p.sum(-1,keepdims=True);_,s,v=case(np.eye(7))
  a=core.analyze_reference(p,s,v,FOLDS);q=p.copy();q[:,:,1::2]=1/7;b=core.analyze_reference(q,s,v,FOLDS)
  for k in ['template','training_loo_residual','training_radius','linear_weights','linear_singular_values']:
   np.testing.assert_array_equal(a[k][:,0],b[k][:,0])
  self.assertFalse(np.array_equal(a['heldout_distances'][:,0],b['heldout_distances'][:,0]))
 def test_test_radius_is_not_used_for_acceptance(self):
  p,s,v=case(np.eye(7));p[:,:,1::2]=1/7;a=core.analyze_reference(p,s,v,FOLDS)
  self.assertEqual(a['training_radius'][0,0],0);self.assertGreater(a['heldout_max_radius_descriptive'][0,0],0)
  self.assertTrue(np.all(a['candidate_count'][0,0]==0))
 def test_periodic_aliases_keep_all_ties(self):
  rows=np.eye(6)[np.arange(6)%2];p,s,v=case(rows);a=core.analyze_reference(p,s,v,FOLDS)
  self.assertTrue(np.all(a['candidate_count']==3));self.assertTrue(np.all(a['nearest_mask'].sum(-1)==3))
  self.assertGreater(a['nearest_max_abs_time_error'].min(),0)
 def test_permuted_unique_dictionary_is_time_identifiable(self):
  rows=np.eye(7)[[2,5,1,6,0,3,4]];p,s,v=case(rows);a=core.analyze_reference(p,s,v,FOLDS)
  self.assertTrue(np.all(a['candidate_count']==1));self.assertEqual(a['nearest_max_abs_time_error'].max(),0)
  np.testing.assert_allclose(a['linear_heldout_error'],0,atol=1e-12)
 def test_dense_loop_distances_radius_and_all_resolutions(self):
  rng=np.random.default_rng(8);p=rng.random((1,7,8,7));p/=p.sum(-1,keepdims=True);_,s,v=case(np.eye(7));a=core.analyze_reference(p,s,v,FOLDS)
  tr=[0,2,4,6];te=[1,3,5,7];template=np.array([sum(p[0,t,k] for k in tr)/4 for t in range(7)])
  radius=max(np.linalg.norm(np.sqrt(p[0,t,k])-np.sqrt(sum(p[0,t,l] for l in tr if l!=k)/3)) for t in range(7) for k in tr)
  distances=np.array([[[np.linalg.norm(np.sqrt(p[0,t,k])-np.sqrt(template[j])) for j in range(7)] for k in te] for t in range(7)])
  np.testing.assert_allclose(a['heldout_distances'][0,0],distances,atol=1e-15);self.assertAlmostEqual(a['training_radius'][0,0],radius)
  for di,delta in enumerate(a['resolutions']):
   val=min(np.linalg.norm(np.sqrt(template[i])-np.sqrt(template[j])) for i in range(7) for j in range(7) if abs(s[i,0]-s[j,0])>=delta)
   self.assertAlmostEqual(a['minimum_separation_curve'][0,0,di],val)
 def test_generated_member_never_deserialized(self):
  p,s,v=case(np.eye(7))
  with tempfile.TemporaryDirectory() as tmp:
   f=Path(tmp)/'x.npz';np.savez(f,qrn_kn=p,qrw_kw=p,valid_bins=v,physical_frame_spans_inclusive=s,spatial_ids=np.arange(8),qn_kn=np.array([object()],dtype=object))
   a=run.decode_reference(f);self.assertEqual(set(a),run.ALLOWED_KEYS)
if __name__=='__main__':unittest.main()
