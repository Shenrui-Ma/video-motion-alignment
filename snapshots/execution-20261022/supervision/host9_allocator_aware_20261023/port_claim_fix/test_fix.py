import ast,os,socket,tempfile,json,time,unittest,fcntl
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
HERE=Path(__file__).parent
class Tests(unittest.TestCase):
 def test_listener_reuse_and_live_listener_protection(self):
  a=socket.socket();a.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);a.bind(('127.0.0.1',0));port=a.getsockname()[1];a.listen()
  c=socket.create_connection(('127.0.0.1',port));conn,_=a.accept();conn.close();c.close()
  b=socket.socket();b.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
  with self.assertRaises(OSError):b.bind(('127.0.0.1',port))
  a.close();b.bind(('127.0.0.1',port));b.close()
 def run_claim(self,pid):
  source=(HERE/'host_worker.py').read_text();node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='select_gpu')
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);root=d/'root';root.mkdir();tmp=d/'tmp';tmp.mkdir()
   uuid='GPU-test';(root/'shared_gpu_authorization.json').write_text(json.dumps({'allow_shared':True,'gpu_uuid':uuid,'minimum_free_mib':25000}))
   def P(s):return d/str(s).lstrip('/')
   for i in [pid,os.getpid()]:
    p=P('/proc/'+str(i));p.mkdir(parents=True,exist_ok=True);(p/'stat').write_text(' '.join(['0']*21+['123']))
   claim=tmp/('h3-20261022-claim-'+uuid+'.json');claim.write_text(json.dumps({'pid':pid,'start_ticks':'123','unix':time.time()}))
   env={'Path':P,'ROOT':root,'os':os,'json':json,'time':time,'fcntl':fcntl,'subprocess':SimpleNamespace(check_output=lambda cmd,**kw: '' if 'compute-apps' in str(cmd) else '0, GPU-test, 40000, 0')}
   exec(compile(ast.Module(body=[node],type_ignores=[]),'select_gpu','exec'),env)
   realopen=open
   def opened(p,*a,**k):return realopen(P(p) if isinstance(p,str) and p.startswith('/tmp/') else p,*a,**k)
   with patch('builtins.open',opened):return env['select_gpu']()
 def test_self_claim_reusable(self):self.assertTrue(self.run_claim(os.getpid()))
 def test_other_live_claim_protected(self):self.assertFalse(self.run_claim(os.getpid()+100))
if __name__=='__main__':unittest.main()
