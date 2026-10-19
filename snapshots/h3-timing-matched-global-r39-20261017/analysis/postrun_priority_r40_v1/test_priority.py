import ast,tempfile,unittest,types
from pathlib import Path
from priority import extra_pending,install
class Tests(unittest.TestCase):
    def test_pending_and_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)/'audit/observations/step000';d.mkdir(parents=True)
            self.assertFalse(extra_pending(tmp));(d/'request.json').touch()
            self.assertFalse(extra_pending(tmp));(d/'native.json').touch()
            self.assertTrue(extra_pending(tmp));(d/'response.json').touch()
            self.assertFalse(extra_pending(tmp));(d/'response.json').unlink();(d/'pose_complete.json').touch()
            self.assertFalse(extra_pending(tmp))
    def test_old_priority_preserved(self):
        m=types.SimpleNamespace(online_pending=lambda:True)
        install(m,lambda:False);self.assertTrue(m.online_pending())
        m=types.SimpleNamespace(online_pending=lambda:False)
        install(m,lambda:True);self.assertTrue(m.online_pending())
    def test_actual_locked_checks_before_after(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'postrun/remote_consume.py').read_text())
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='locked')
        for checks,expected_locks in [([True],0),([False,True],1),([False,False],1)]:
            with self.subTest(checks=checks):
                calls=[];f=types.SimpleNamespace(close=lambda:calls.append('closed'))
                fc=types.SimpleNamespace(LOCK_EX=1,LOCK_NB=2,flock=lambda *args:calls.append('flock'))
                values=iter(checks);ns={'online_pending':lambda:next(values),'Path':lambda _:types.SimpleNamespace(open=lambda _:f),'fcntl':fc}
                exec(compile(ast.Module(body=[node],type_ignores=[]),'<original locked>','exec'),ns)
                if any(checks):
                    with self.assertRaises(BlockingIOError):ns['locked']()
                else:self.assertIs(ns['locked'](),f)
                self.assertEqual(calls.count('flock'),expected_locks)
                if checks==[False,True]:self.assertIn('closed',calls)
if __name__=='__main__':unittest.main()
