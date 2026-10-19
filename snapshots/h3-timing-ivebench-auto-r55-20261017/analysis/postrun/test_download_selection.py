import unittest
import consume
class DownloadSelectionTests(unittest.TestCase):
 def test_exact_limit_and_raw_tensors(self):
  n=20*1024*1024;rows={'small.json':{'bytes':10,'sha256':'a'},'limit.json':{'bytes':n,'sha256':'b'},'large.json':{'bytes':n+1,'sha256':'c'},'small.pt':{'bytes':10,'sha256':'d'}}
  self.assertEqual(set(consume.local_original(rows)),{'small.json','limit.json'})
  keep=consume.retained_original(rows,'/remote/archive')
  self.assertEqual({r['relative_file'] for r in keep},{'large.json','small.pt'})
  self.assertEqual(next(r for r in keep if r['relative_file']=='large.json'),dict(file='/remote/archive/large.json',relative_file='large.json',bytes=n+1,sha256='c'))
 def test_all_originals_accounted(self):
  rows={'a.json':{'bytes':1,'sha256':'a'},'b.json':{'bytes':999999999,'sha256':'b'},'c.pt':{'bytes':1,'sha256':'c'}}
  self.assertEqual(set(consume.local_original(rows))|{r['relative_file'] for r in consume.retained_original(rows,'/r')},set(rows))
