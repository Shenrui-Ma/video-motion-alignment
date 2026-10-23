import copy, hashlib, importlib.util, json, pathlib, sys, tempfile, unittest
from unittest import mock
import numpy as np
PACKAGE=pathlib.Path(sys.argv[1]);sys.argv=sys.argv[:1]
sys.path.insert(0,str(PACKAGE))
import core, run

class Independent(unittest.TestCase):
 def fixture(self,h=2,t=7,p=3):
  rng=np.random.default_rng(7391);valid=np.ones(t,dtype=bool);valid[2]=False
  a=rng.random((h,t,p,t));b=rng.random((h,t,p,t))
  for x in [a,b]:
   x[...,~valid]=0;x/=x.sum(-1,keepdims=True);x[:,~valid]=0
  return a,b,valid,np.column_stack([np.arange(t)*4,np.arange(t)*4+3])
 def test_dense_loop_oracle_noncontiguous_support(self):
  a,b,v,s=self.fixture();out=core.analyze(a,b,v,s);ids=np.flatnonzero(v)
  oracle=np.zeros((len(ids),len(ids)))
  for it,t in enumerate(ids):
   for ij,j in enumerate(ids):
    total=0.0
    for h in range(a.shape[0]):
     for p in range(a.shape[2]):
      for k in ids:total+=(np.sqrt(b[h,t,p,k])-np.sqrt(a[h,j,p,k]))**2
    oracle[it,ij]=total/(a.shape[0]*a.shape[2])
  np.testing.assert_allclose(out['squared_distances'],oracle,rtol=3e-15,atol=3e-16)
  expected=np.array([min(oracle[i,j] for j in range(len(ids)) if i!=j)-oracle[i,i] for i in range(len(ids))])
  np.testing.assert_allclose(out['off_diagonal_margin'],expected,rtol=3e-14,atol=3e-16)
 def test_static_and_pure_position_have_opposite_decisions(self):
  t=6;v=np.ones(t,dtype=bool);s=np.column_stack([np.arange(t),np.arange(t)])
  static=np.full((2,t,3,t),1/t);pos=np.broadcast_to(np.eye(t)[None,:,None,:],static.shape).copy()
  out=core.analyze(static,static,v,s);self.assertFalse(out['unique_correct'].any());self.assertTrue((out['nearest_count']==t).all())
  out=core.analyze(pos,pos,v,s);self.assertTrue(out['unique_correct'].all());self.assertTrue((out['off_diagonal_margin']>1).all())
 def test_periodic_roles_stay_ambiguous(self):
  t=10;v=np.ones(t,dtype=bool);s=np.column_stack([np.arange(t),np.arange(t)])
  a=np.zeros((2,t,3,t))
  for i in range(t):a[:,i,:,i%5]=1
  out=core.analyze(a,a,v,s);self.assertTrue((out['nearest_count']==2).all());self.assertFalse(out['unique_correct'].any())
 def test_joint_spatial_permutation_invariant_one_sided_changes(self):
  a,b,v,s=self.fixture();perm=[2,0,1];base=core.analyze(a,b,v,s)['squared_distances']
  both=core.analyze(a[:,:,perm],b[:,:,perm],v,s)['squared_distances']
  one=core.analyze(a,b[:,:,perm],v,s)['squared_distances']
  np.testing.assert_allclose(base,both,rtol=2e-15,atol=2e-16)
  self.assertGreater(float(np.max(np.abs(base-one))),1e-3)
 def test_key_permutation_invariance_and_row_permutation_not_hidden(self):
  a,b,v,s=self.fixture();ids=np.flatnonzero(v);perm=np.arange(len(v));perm[ids]=ids[::-1]
  base=core.analyze(a,b,v,s)['squared_distances'];other=core.analyze(a[...,perm],b[...,perm],v,s)['squared_distances']
  np.testing.assert_allclose(base,other,rtol=2e-15,atol=2e-16)
  a=np.broadcast_to(np.eye(6)[None,:,None,:],(2,6,3,6)).copy();v=np.ones(6,dtype=bool);s=np.column_stack([np.arange(6),np.arange(6)])
  swap=np.array([1,0,3,2,5,4]);o=core.analyze(a,a[:,swap],v,s)
  self.assertFalse(o['unique_correct'].any());np.testing.assert_array_equal(o['nearest_mask'].argmax(-1),swap)
 def test_generated_object_member_not_decoded(self):
  a,b,v,s=self.fixture()
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp)/'input.npz';np.savez(p,qrn_kn=a,qrw_kw=b,valid_bins=v,physical_frame_spans_inclusive=s,spatial_ids=np.arange(3),qn_kn=np.array([object()],dtype=object))
   loaded=run.decode_reference(p);self.assertEqual(set(loaded),set(run.ALLOWED_KEYS));self.assertEqual(loaded['qrn_kn'].shape,a.shape)
 def test_hash_rejection_precedes_array_decode_and_missing_is_empty(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp);st=d/'status.json';st.write_text(json.dumps({'status':'complete','results_written':True,'summary_sha256':'a'*64}))
   inp=d/'bad.npz';inp.write_bytes(b'not an archive')
   policy={'steps':[9,19],'upstream':{'status_sha256':run.sha(st),'summary_sha256':'a'*64,'npz_sha256':{'9':'0'*64,'19':'0'*64}},'decoded_npz_keys':list(run.ALLOWED_KEYS)}
   with mock.patch.object(run,'decode_reference',side_effect=AssertionError('decoded before hash')) as dec:
    with self.assertRaises(run.Invalid):run.preflight({'status':st,'9':inp,'19':inp},policy)
    self.assertFalse(dec.called)
   out=d/'out';status=run.execute(d/'missing.json',out,policy)
   self.assertEqual(status['status'],'pending');self.assertFalse(status['results_written']);self.assertEqual([x.name for x in out.iterdir()],['STATUS.json'])

if __name__=='__main__':unittest.main(verbosity=2)
