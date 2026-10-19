import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions')]
import verify_completed as v,prelaunch_gates as g
class EvidenceTests(unittest.TestCase):
 def test_production_bootstrap_dependencies_present(self):
  import ast,hashlib
  source=(ROOT/'scripts/compatibility_bootstrap.py').read_text();tree=ast.parse(source)
  names={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
  for name in ('int8_row_chunking','backend_dispatch_audit'):
   self.assertIn(name,names);p=ROOT/'scripts'/str(name+'.py');self.assertTrue(p.is_file())
   old=Path('/Users/researcher/DevProjects/h3-timing-forward-reverse-r30-20261017/scripts')/p.name
   if old.exists():self.assertEqual(p.read_bytes(),old.read_bytes())

 def test_actual_R27_final_and_step_metadata(self):
  c=json.loads((ROOT/'configs/parent_captures.json').read_text());case={'run_id':c['run_id'],'seed':2026101313}
  for row in c['captures']+[c['final_sampler_result']]:v.check_record_semantics(row,c,case)
  for key,bad in [('sigma_video',.3),('schema','bad'),('audio_scale',1),('geometry',{'width':1})]:
   row=copy.deepcopy(c['final_sampler_result']);row[key]=bad
   with self.assertRaises(ValueError):v.check_record_semantics(row,c,case)
 def test_submission_mixed_generation(self):
  job={'status':'success','name':'run','graph_sha256':'sha','prompt_id':'p'};history={'prompt':[0,'p',{}]};v.check_submission(job,history,'run','sha')
  for key,bad in [('status','running'),('name','other'),('graph_sha256','bad'),('prompt_id','stale')]:
   j=dict(job);j[key]=bad
   with self.assertRaises(ValueError):v.check_submission(j,history,'run','sha')
 def test_actual_inherited_kernel_layout(self):
  p=ROOT/'configs/inherited_actual87592_kernel.json'
  if not p.exists():self.skipTest('local parent evidence available only on Mac; remote actual prelaunch uses frozen paths')
  k=json.loads(p.read_text());c=json.loads((ROOT/'configs/parent_conditioning.json').read_text());g.check_kernel(k,c)
  x=copy.deepcopy(c);x['packed_layout']['seq_len']-=1
  with self.assertRaises(ValueError):g.check_kernel(k,x)
 def test_root_mutable_queue_requires_bool(self):
  import r37_contract as c
  from unittest.mock import patch
  original=c.read
  def mutate(p):
   x=original(p)
   if Path(p).name=='queue.json':x['finalize']=1
   return x
  with patch.object(c,'read',side_effect=mutate),self.assertRaises(ValueError):c.registry(ROOT)
class PathLedgerTests(unittest.TestCase):
 def test_actual_import_paths_reject_escape_and_symlink(self):
  import tempfile
  from H3StaticWindowRouter import transport as t
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'yes';p.write_text('x');self.assertEqual(t.inside(p,root),p)
   for bad in ('relative',root/'../outside'):
    with self.assertRaises(ValueError):t.inside(bad,root)
   (root/'link').symlink_to(p)
   with self.assertRaises(ValueError):t.inside(root/'link',root)
 def test_prefix_ledger_duplicate_or_order_is_rejected(self):
  expected=[(i,b) for i in range(20) for b in (('native','full') if i==4 else ('native',))]
  c={'branches':[{'physical_index':n,'branch':b} for n,b in expected]};g=copy.deepcopy(c['branches'])
  a={'routed_by_forward':[0]*5+[50]+[0]*15,'calls_by_block':[21]*50,'routed_by_block':[1]*50,'forward_summaries':[{'forward_index':i,'nfe_index':i,'physical_index':n,'branch':b,'active':b=='full','latent_bins':list(range(42)) if b=='full' else [],'completed_blocks':50,'routed_blocks':50 if b=='full' else 0} for i,(n,b) in enumerate(expected)]}
  v.check_branch_ledger(a,c,g)
  for bad in (g[:1]*5+g[5:],g[1:]+g[:1],g[:-1]):
   with self.assertRaises(ValueError):v.check_branch_ledger(a,c,bad)
  a['routed_by_forward'][4]=50
  with self.assertRaises(ValueError):v.check_branch_ledger(a,c,g)
if __name__=='__main__':unittest.main()
