import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import cgroup_memory as c

class CgroupCapacity(unittest.TestCase):
 def setUp(self):self.policy=json.loads((ROOT/'configs/cgroup_policy.json').read_text())
 def value(self,current=25*c.GIB):
  return {'uid':1004,'observed_unix':1,'host_available_bytes':200*c.GIB,'effective_headroom_bytes':100*c.GIB-current,'ancestors':[{'path':'/user.slice','current_bytes':current,'high_bytes':100*c.GIB,'max_bytes':112*c.GIB,'events':{'high':100852630,'max':0,'oom':0,'oom_kill':0},'stat':dict.fromkeys(('file','shmem','active_file','inactive_file','file_mapped','file_dirty','file_writeback','anon'),0),'pressure':{'some':{'avg10':0.0},'full':{'avg10':0.0}}}]}
 def test_historical_high_events_are_accepted(self):self.assertTrue(c.admit(self.value(),self.policy)['admitted'])
 def test_exact64_boundary_and_below(self):
  c.admit(self.value(36*c.GIB),self.policy)
  with self.assertRaises(RuntimeError):c.admit(self.value(36*c.GIB+1),self.policy)
 def test_effective_tighter_ancestor_rejected(self):
  value=self.value();child=copy.deepcopy(value['ancestors'][0]);child.update(path='/user.slice/child',high_bytes=88*c.GIB,max_bytes=None);value['ancestors'].append(child)
  with self.assertRaises(RuntimeError):c.admit(value,self.policy)
 def test_parent_uid_and_limit_fail_closed(self):
  for key in ('uid','parent','high','max'):
   value=self.value()
   if key=='uid':value['uid']=1016
   elif key=='parent':value['ancestors'][0]['path']='/different'
   else:value['ancestors'][0][key+'_bytes']=None
   with self.assertRaises(RuntimeError):c.admit(value,self.policy)
 def test_events_increment_and_reset_are_descriptive(self):
  old=self.value();now=copy.deepcopy(old);now['ancestors'][0]['events']['high']+=7
  self.assertEqual(c.delta(now,old)['paths']['/user.slice']['events_delta']['high'],7)
  now['ancestors'][0]['events']['high']=0
  self.assertTrue(c.delta(now,old)['paths']['/user.slice']['counter_reset_detected'])
 def test_unknown_observation_does_not_raise(self):
  with patch.object(c,'snapshot',side_effect=OSError('temporary')):self.assertFalse(c.observe(ROOT)['sample_available'])
 def test_full_ancestry_and_finite_minimum(self):
  with tempfile.TemporaryDirectory() as temp:
   r=Path(temp);proc=r/'membership';proc.write_text('0::/user.slice/user-1004.slice/session.scope\n');mount=r/'cgroup';meminfo=r/'meminfo';meminfo.write_text('MemAvailable: 209715200 kB\n')
   for rel,high,maximum,current in [('', 'max','max',50*c.GIB),('user.slice',100*c.GIB,112*c.GIB,25*c.GIB),('user.slice/user-1004.slice','max','max',1),('user.slice/user-1004.slice/session.scope','max','max',1)]:
    d=mount/rel;d.mkdir(parents=True,exist_ok=True)
    for name,value in [('current',current),('high',high),('max',maximum),('events','high 900\noom 0\n'),('stat','file 0\nanon 0\nshmem 0\nactive_file 0\ninactive_file 0\nfile_mapped 0\nfile_dirty 0\nfile_writeback 0\n'),('pressure','some avg10=0.00 avg60=0.00 avg300=7.07 total=9999\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=33\n')]:
     (d/('memory.'+name)).write_text(str(value))
   result=c.snapshot(proc,mount,meminfo)
   self.assertEqual(len(result['ancestors']),4);self.assertEqual(result['effective_headroom_bytes'],75*c.GIB);self.assertEqual(result['limiting_path'],'/user.slice');self.assertEqual(result['limiting_kind'],'high')
   for name in ('current','high','max','events'):(mount/('memory.'+name)).unlink()
   missing_root=c.snapshot(proc,mount,meminfo);self.assertEqual(missing_root['effective_headroom_bytes'],75*c.GIB);self.assertIsNone(missing_root['ancestors'][-1]['current_bytes'])
   self.assertEqual(c.delta(missing_root,missing_root)['paths']['/']['current_bytes_change'],None)
 def test_limits_and_invalid_pressure(self):
  self.assertIsNone(c.limit('max'));self.assertEqual(c.limit('123'),123)
  with self.assertRaises(ValueError):c.limit('-1')
  with self.assertRaises(ValueError):c.pressure('full avg10=nan total=2')

if __name__=='__main__':unittest.main()
