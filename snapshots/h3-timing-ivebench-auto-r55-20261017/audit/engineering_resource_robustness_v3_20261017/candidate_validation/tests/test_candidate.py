"""CPU-only candidate contract tests. Mocks all GPU calls; R55 modules load the integrated producer."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
TMP = HERE / 'test_tmp'
TMP.mkdir(exist_ok=True)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def function(text, name):
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return '\n'.join(text.splitlines()[node.lineno - 1:node.end_lineno])


class Clock:
    def __init__(self): self.now = 0.; self.sleeps = []
    def __call__(self): return self.now
    def sleep(self, value): self.sleeps.append(value); self.now += value


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=TMP)
        self.root = Path(self.temp.name)
        self.audit = self.root / 'audit/observations/test'
        self.audit.mkdir(parents=True)
        self.parent = {'pid': 100, 'uid': os.getuid(), 'start_ticks': 1, 'cmdline_sha256': 'a'*64}
        self.child = {'pid': 200, 'uid': os.getuid(), 'start_ticks': 2, 'cmdline_sha256': 'b'*64}

    def tearDown(self): self.temp.cleanup()

    def modules(self):
        for name in ('r50', 'r55'):
            base = Path(json.loads((HERE/'SOURCE_SNAPSHOTS.json').read_text())[name]['source_root']) if name == 'r55' else HERE / name / 'overlay'
            t = load(name+'_transport', base/'extensions/H3AutomaticWindowRouter/transport.py')
            t.ROOT = self.root
            release = load(name+'_release', base/'scripts/gpu_release_gate.py')
            yield name, t, release

    def gpu(self, t):
        return {'uuid': t.DECODER_UUID, 'memory_used_mib': 0,
                'memory_free_mib': 80000, 'utilization_percent': 0}

    def admitted(self, t, extra=()):
        rows = [{'gpu_uuid': t.MAIN_UUID, 'pid': self.parent['pid']}, *extra]
        return t.validate_separate_decoder(self.parent,t.DECODER_UUID,self.gpu(t),rows,
                   lookup=lambda pid: self.parent if pid==100 else {'pid':pid,'uid':os.getuid()+1})

    def wait(self, t, clock, check, name, **kwargs):
        return t.wait_decoder_admission(self.parent,clock=clock,sleep=clock.sleep,
                   check=check,is_alive=lambda _:True,audit_path=self.audit/(name+'.jsonl'),**kwargs)

    def test_busy_then_recovers_and_records_actual_snapshot(self):
        for name,t,_ in self.modules():
            with self.subTest(name=name):
                clock=Clock();count=[0]
                busy={'gpu_uuid':t.DECODER_UUID,'pid':300}
                def check(parent,uuid):
                    count[0]+=1
                    return self.admitted(t, [busy] if count[0]<3 else [])
                result=self.wait(t,clock,check,name)
                self.assertEqual(result['owned_GPU_cards'],[t.MAIN_UUID])
                self.assertEqual(clock.now,2)
                events=[json.loads(x) for x in (self.audit/(name+'.jsonl')).read_text().splitlines()]
                self.assertEqual([x['status'] for x in events],['waiting','waiting','admitted'])
                self.assertEqual(events[0]['snapshot']['processes'][1]['pid'],300)

    def test_timeout_is_bounded(self):
        for name,t,_ in self.modules():
            clock=Clock()
            def check(*_): raise t.ResourceUnavailable('busy',{'compute_rows':[{'pid':77}]})
            with self.assertRaises(TimeoutError): self.wait(t,clock,check,name,timeout=3)
            self.assertEqual(clock.now,3)
            self.assertEqual(len(clock.sleeps),3)

    def test_parent_identity_change_is_hard_failure(self):
        for name,t,_ in self.modules():
            clock=Clock()
            def check(parent,uuid):
                return t.validate_separate_decoder(parent,uuid,self.gpu(t),
                    [{'gpu_uuid':t.MAIN_UUID,'pid':100}],lookup=lambda _:dict(parent,start_ticks=99))
            with self.assertRaisesRegex(ValueError,'stale/reused/missing'):
                self.wait(t,clock,check,name)
            self.assertEqual(clock.sleeps,[])
            event=json.loads((self.audit/(name+'.jsonl')).read_text())
            self.assertEqual(event['status'],'hard_failure')
            self.assertEqual(event['snapshot']['actual_parent']['start_ticks'],99)

    def test_data_binding_error_is_hard_failure(self):
        for name,t,_ in self.modules():
            clock=Clock()
            def check(*_): raise ValueError('endpoint changed')
            with self.assertRaisesRegex(ValueError,'endpoint changed'):
                self.wait(t,clock,check,name)
            self.assertEqual(clock.sleeps,[])

    def test_third_owned_gpu_waits_without_admission(self):
        for _,t,_ in self.modules():
            rows=[{'gpu_uuid':t.MAIN_UUID,'pid':100},{'gpu_uuid':'GPU-third','pid':300}]
            lookup=lambda pid:self.parent if pid==100 else dict(self.child,pid=pid)
            with self.assertRaisesRegex(t.ResourceUnavailable,'second owned GPU slot'):
                t.validate_separate_decoder(self.parent,t.DECODER_UUID,self.gpu(t),rows,lookup=lookup)

    def test_unrelated_user_on_other_gpu_is_allowed(self):
        for _,t,_ in self.modules():
            result=self.admitted(t,[{'gpu_uuid':'GPU-unrelated','pid':300}])
            self.assertEqual(result['planned_owned_GPUs'],sorted([t.MAIN_UUID,t.DECODER_UUID]))

    def test_foreign_process_after_exit_does_not_discard_decode(self):
        for name,t,release in self.modules():
            clock=Clock()
            result=release.wait_own_child_released(t.DECODER_UUID,{'returncode':0,'process':self.child},
                lambda _:None,clock=clock,sleep=clock.sleep,compute_pids=lambda:[300],audit_path=self.audit/(name+'.jsonl'))
            self.assertTrue(result['original_generation_absent'])
            self.assertTrue(result['nvml_pid_absent'])
            self.assertEqual(result['other_compute_pids'],[300])
            self.assertEqual(clock.sleeps,[])
            self.assertNotIn('idle',result)

    def test_pid_reuse_records_new_generation_and_never_kills(self):
        for _,t,release in self.modules():
            replacement=dict(self.child,start_ticks=900,cmdline_sha256='c'*64)
            result=release.wait_own_child_released(t.DECODER_UUID,{'returncode':0,'process':self.child},
                lambda _:replacement,compute_pids=lambda:[200])
            self.assertTrue(result['pid_reused'])
            self.assertFalse(result['nvml_pid_absent'])
            self.assertEqual(result['current_reused_identity'],replacement)
            self.assertEqual(result['other_compute_pids'],[200])

    def test_same_generation_with_changed_command_is_still_live(self):
        for _,t,release in self.modules():
            with self.assertRaisesRegex(RuntimeError,'original decoder generation remains'):
                release.wait_own_child_released(t.DECODER_UUID,{'returncode':0,'process':self.child},
                    lambda _:dict(self.child,cmdline_sha256='c'*64),compute_pids=lambda:[200])

    def test_own_nvml_tail_waits_while_other_users_continue(self):
        for _,t,release in self.modules():
            clock=Clock();rows=iter([[200,300],[200,300],[300]])
            result=release.wait_own_child_released(t.DECODER_UUID,{'returncode':0,'process':self.child},
                lambda _:None,clock=clock,sleep=clock.sleep,compute_pids=lambda:next(rows))
            self.assertEqual(clock.now,.5)
            self.assertTrue(result['nvml_pid_absent'])
            self.assertEqual(result['other_compute_pids'],[300])

    def test_own_nvml_tail_timeout_preserves_snapshot(self):
        for name,t,release in self.modules():
            clock=Clock()
            with self.assertRaises(TimeoutError):
                release.wait_own_child_released(t.DECODER_UUID,{'returncode':0,'process':self.child},
                    lambda _:None,timeout=1,clock=clock,sleep=clock.sleep,compute_pids=lambda:[200,300],audit_path=self.audit/(name+'.jsonl'))
            self.assertEqual(clock.now,1)
            event=json.loads((self.audit/(name+'.jsonl')).read_text().splitlines()[-1])
            self.assertEqual(event['compute_pids'],[200,300])

    def test_response_contract_both_interfaces(self):
        for _,t,release in self.modules():
            proof=release.wait_own_child_released(t.DECODER_UUID,{'returncode':0,'process':self.child},lambda _:None,compute_pids=lambda:[300])
            request={'parent':self.parent,'request_id':'x'}
            response={'status':'complete','request_id':'x','request_sha256':'s','decoder_released_before_pose':True,
                'decoder_admission':self.admitted(t),'after_decoder_release':proof,
                'decoder':{'process':self.child,'returncode':0},'pose_process':{'returncode':0}}
            t.validate_response(response,request,'s')
            response['after_decoder_release']=dict(proof,original_generation_absent=False)
            with self.assertRaises(ValueError):t.validate_response(response,request,'s')

    def test_query_ambiguity_and_headroom_are_retryable(self):
        for _,t,_ in self.modules():
            main={'gpu_uuid':t.MAIN_UUID,'pid':100}
            for rows in ([],[main,main]):
                with self.assertRaises(t.ResourceUnavailable):
                    t.validate_separate_decoder(self.parent,t.DECODER_UUID,self.gpu(t),rows,lookup=lambda _:self.parent)
            with self.assertRaises(t.ResourceUnavailable):
                t.validate_separate_decoder(self.parent,t.DECODER_UUID,dict(self.gpu(t),memory_free_mib=40000),[main],lookup=lambda _:self.parent)

    def test_source_snapshots_and_numerics_unchanged(self):
        records=json.loads((HERE/'SOURCE_SNAPSHOTS.json').read_text())
        for name,record in records.items():
            for rel,expected in record['files'].items():
                before=(HERE/name/'before'/rel).read_text();after=(HERE/name/'overlay'/rel).read_text()
                self.assertEqual(hashlib.sha256(before.encode()).hexdigest(),expected['before_sha256'])
                self.assertEqual(hashlib.sha256(after.encode()).hexdigest(),expected['after_sha256'])
                self.assertEqual(hashlib.sha256((Path(record['source_root'])/rel).read_bytes()).hexdigest(),expected['after_sha256' if name == 'r55' else 'before_sha256'])
                ast.parse(after)
            rel='scripts/decode_live_child.py'
            before=(HERE/name/'before'/rel).read_text();after=(HERE/name/'overlay'/rel).read_text()
            for fn in ('load_snapshot','install_fallback_guard','write_video'):
                self.assertEqual(function(before,fn),function(after,fn))
            self.assertEqual(before[before.index('    from compatibility_bootstrap import install, install_video_compat'):],
                             after[after.index('    from compatibility_bootstrap import install, install_video_compat'):])
            rel='scripts/gpu_release_gate.py'
            self.assertEqual(function((HERE/name/'before'/rel).read_text(),'wait_after_child'),
                             function((HERE/name/'overlay'/rel).read_text(),'wait_after_child'))

    def test_exact_patches_reconstruct_overlays(self):
        git=shutil.which('git')
        self.assertIsNotNone(git,'existing git needed for patch verification')
        for name in ('r50','r55'):
            scratch=self.root/name
            shutil.copytree(HERE/name/'before',scratch)
            subprocess.run([git,'apply',str(HERE/name/'candidate.patch')],cwd=scratch,check=True,capture_output=True)
            for path in (HERE/name/'overlay').rglob('*.py'):
                self.assertEqual(path.read_bytes(),(scratch/path.relative_to(HERE/name/'overlay')).read_bytes())

    def test_observer_and_child_share_deadline_without_gpu_code_changes(self):
        for name in ('r50','r55'):
            observer=(HERE/name/'overlay/scripts/run_observer.py').read_text()
            decoder=(HERE/name/'overlay/scripts/decode_live_child.py').read_text()
            self.assertIn('H3_DECODER_RESOURCE_DEADLINE=str(resource_deadline)',observer)
            self.assertIn('decoder_budget=max(0,resource_deadline-time.monotonic())+180',observer)
            self.assertIn('execution_timeout=180',observer)
            self.assertIn('H3_DECODER_EXECUTION_MARKER',observer)
            self.assertEqual(decoder.count('t.wait_decoder_admission('),2)
            self.assertIn('request changed during resource wait',decoder)
            self.assertLess(observer.index('wait_own_child_released('),observer.index("env['CUDA_VISIBLE_DEVICES']=''"))
            self.assertNotIn('after_decoder_admission',observer)

    def supervised_fake(self,t,name,*,resource_ready,finish,marker_override=None):
        clock=Clock();folder=self.audit/name;folder.mkdir();marker=folder/'start.json'
        entry=self.child;state={'killed':False};owner=self.parent
        class FakeProcess:
            pid=entry['pid'];returncode=None
            def poll(self):
                if self.returncode is not None:return self.returncode
                if clock.now>=resource_ready and not marker.exists():
                    value={'schema':'h3-child-execution-start-v1','identity':entry,'started_monotonic':clock.now}
                    if marker_override:value.update(marker_override)
                    marker.write_text(json.dumps(value))
                if clock.now>=finish:self.returncode=0
                return self.returncode
        proc=FakeProcess()
        def terminate(process,identity):
            if process.poll() is None:state['killed']=True;process.returncode=-15
        def alive(value):
            return value==owner or value==entry and proc.returncode is None
        with patch.object(t,'time',types.SimpleNamespace(monotonic=clock,sleep=clock.sleep)), \
             patch.object(t,'identity',lambda pid:entry if pid==entry['pid'] else owner), \
             patch.object(t,'alive',alive),patch.object(t,'terminate_owned',terminate), \
             patch.object(t.subprocess,'Popen',return_value=proc):
            try:
                result=t.run_child(['fake-decoder'],{},folder,'decoder',780,owner,
                    execution_started_path=marker,execution_timeout=180)
            except Exception as error:result=error
        return result,clock,state

    def test_resource_wait_over_180s_then_decode_is_allowed(self):
        for name,t,_ in self.modules():
            result,clock,state=self.supervised_fake(t,name,resource_ready=300,finish=330)
            self.assertIsInstance(result,dict)
            self.assertEqual(result['returncode'],0)
            self.assertEqual(json.loads(json.dumps(result,allow_nan=False)),result)
            self.assertIn('execution_start',result)
            self.assertEqual(result['execution_start']['identity'],self.child)
            self.assertGreater(clock.now,300)
            self.assertFalse(state['killed'])

    def test_execution_has_independent_180s_limit(self):
        for name,t,_ in self.modules():
            result,clock,state=self.supervised_fake(t,name,resource_ready=300,finish=700)
            self.assertIsInstance(result,TimeoutError)
            self.assertIn('execution timeout',str(result))
            self.assertGreaterEqual(clock.now,480)
            self.assertLess(clock.now,481)
            self.assertTrue(state['killed'])

    def test_execution_marker_wrong_generation_is_hard_failure(self):
        for name,t,_ in self.modules():
            result,clock,state=self.supervised_fake(t,name,resource_ready=2,finish=30,
                marker_override={'identity':dict(self.child,start_ticks=999)})
            self.assertIsInstance(result,ValueError)
            self.assertIn('identity differs',str(result))
            self.assertTrue(state['killed'])

    def test_execution_marker_stale_time_is_hard_failure(self):
        for name,t,_ in self.modules():
            result,clock,state=self.supervised_fake(t,name,resource_ready=2,finish=30,
                marker_override={'started_monotonic':-1})
            self.assertIsInstance(result,ValueError)
            self.assertIn('time invalid',str(result))
            self.assertTrue(state['killed'])

    def test_late_query_cannot_admit_cuda_after_deadline(self):
        for name,t,_ in self.modules():
            clock=Clock()
            def check(*_):clock.now=4;return self.admitted(t)
            with self.assertRaises(TimeoutError):self.wait(t,clock,check,name,timeout=3)


if __name__=='__main__': unittest.main()
