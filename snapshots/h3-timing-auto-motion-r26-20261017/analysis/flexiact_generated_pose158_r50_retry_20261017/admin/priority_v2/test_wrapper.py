import shlex
import unittest
from local_entry import rewrite

class Wrapper(unittest.TestCase):
 def test_changes_only_exact_entry(self):
  p={'root_remote':'/run'}
  args=['env','CUDA_VISIBLE_DEVICES=','/python','/run/remote_one.py','--source','chest']
  got=rewrite(['ssh','host',shlex.join(args)],p)
  want=args.copy();want[3]='/run/admin/priority_v2/remote_entry.py'
  self.assertEqual(shlex.split(got[-1]),want)
 def test_other_commands_unchanged(self):
  for cmd in [['rsync','/run/remote_one.py'],['ssh','host','cat /run/remote_one.py.other']]:
   self.assertEqual(rewrite(cmd,{'root_remote':'/run'}),cmd)
if __name__=='__main__': unittest.main()
