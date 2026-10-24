"""Run the unmodified durable queue poll against deterministic CPU-only clocks/API."""
import copy, importlib.util, json, os
from pathlib import Path
from types import SimpleNamespace
import tempfile, unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
V2 = HERE.parents[1] / 'v2/package'
def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
q=load('original_queue',V2/'gpu7/queue/durable_comfy_queue.py')
bind=load('progress_binding',HERE/'progress_binding.py')

class Clock:
    def __init__(self, path, update):self.t=0.;self.path=path;self.update=update
    def monotonic(self):return self.t
    def sleep(self,seconds):
        self.t+=seconds
        if self.t>20000:raise AssertionError('Test exceeded bounded simulated time')
        if self.update(self.t):
            self.path.parent.mkdir(parents=True,exist_ok=True)
            self.path.write_text(json.dumps({'completed_forward_calls':int(self.t//60)}))
            ns=int((1000000000+self.t)*1e9);os.utime(self.path,ns=(ns,ns))

class FakeAPI:
    def __init__(self,clock,complete_at):self.clock=clock;self.complete_at=complete_at
    def call(self,path):
        if path.startswith('/history/'):
            if self.complete_at is not None and self.clock.t>=self.complete_at:
                return {'prompt-1':{'status':{'completed':True,'status_str':'success'}}}
            return {}
        if path=='/queue':return {'queue_running':[[0,'prompt-1']], 'queue_pending':[]}
        raise AssertionError(path)

def poll(root, *, bound=True, timeout=1800, update=lambda t:False, complete_at=None):
    file=root/'audit/router/job__a1.json';clock=Clock(file,update)
    runner=q.Runner.__new__(q.Runner)
    runner.args=SimpleNamespace(stall_timeout=timeout,poll_seconds=60,missing_prompt_grace=120,
        restart_after_seconds=120,restart_command=None,max_service_restarts=0)
    runner.api=FakeAPI(clock,complete_at);runner.save=lambda:None
    events=[];runner.log=lambda event,**fields:events.append((clock.t,event,fields))
    state={'prompt_id':'prompt-1','attempt_id':'job__a1'};job={'id':'job'}
    if bound:job['progress_file']=str(file)
    with patch.object(q.time,'monotonic',clock.monotonic),patch.object(q.time,'sleep',clock.sleep):
        outcome,history=runner.poll(job,state)
    return outcome,clock.t,state,events

def lane_fixture(base,gpu=7):
    base=base.resolve()
    lane=base/f'gpu{gpu}';lane.mkdir(parents=True)
    old=f'/data4/research-user/h3_runs/interval_short0177_20261024_v2/gpu{gpu}'
    package=V2/f'gpu{gpu}'
    cfg=json.loads((package/'CONFIG.json').read_text().replace(old,str(lane)))
    cfg['allowed_root']=str(base);(lane/'CONFIG.json').write_text(json.dumps(cfg))
    for arm in cfg['arms']:
        for kind in ('manifests','graphs'):
            filename=(arm if kind=='manifests' else 'interval_short_0177_'+arm)+'.json'
            value=json.loads((package/kind/filename).read_text().replace(old,str(lane)))
            if kind=='manifests':value['jobs'][0]['progress_file']=str(lane/'audit/router'/('interval_short_0177_'+arm+'__a1.json'))
            target=lane/kind/filename;target.parent.mkdir(exist_ok=True);target.write_text(json.dumps(value))
    return lane

class PollTest(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_reproduces_missing_binding_false_stall(self):
        result,at,state,_=poll(self.root,bound=False,timeout=900,update=lambda t:True,complete_at=1500)
        self.assertEqual((result,at,state['status']),('stalled',960.,'waiting_stalled'))
    def test_bound_progress_survives_old_900_seconds(self):
        result,at,_,events=poll(self.root,timeout=900,update=lambda t:t%120==0,complete_at=4800)
        self.assertEqual((result,at),('completed',4800.));self.assertGreater(sum(e[1]=='progress' for e in events),30)
    def test_cold_loading_within_1800_budget_then_sampling(self):
        result,at,_,_=poll(self.root,update=lambda t:t>=1200 and t%120==0,complete_at=2400)
        self.assertEqual((result,at),('completed',2400.))
    def test_old_900_budget_rejects_same_cold_load(self):
        result,at,state,_=poll(self.root,timeout=900,update=lambda t:t>=1200,complete_at=2400)
        self.assertEqual((result,at,state['status']),('stalled',960.,'waiting_stalled'))
    def test_cold_load_without_progress_still_stalls(self):
        result,at,state,_=poll(self.root)
        self.assertEqual((result,at,state['status']),('stalled',1860.,'waiting_stalled'))
    def test_true_stall_after_sampling_still_stalls(self):
        result,at,state,_=poll(self.root,update=lambda t:t<=600)
        self.assertEqual((result,at,state['status']),('stalled',2460.,'waiting_stalled'))
    def test_api_failure_record_is_immediate(self):
        clock=Clock(self.root/'unused',lambda t:False);runner=q.Runner.__new__(q.Runner)
        runner.api=SimpleNamespace(call=lambda p:{'prompt-1':{'status':{'status_str':'error'}}})
        with patch.object(q.time,'monotonic',clock.monotonic):
            result,_=runner.poll({'id':'job'},{'prompt_id':'prompt-1'})
        self.assertEqual(result,'failed')

class BindingTest(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_all_three_lanes_six_bindings(self):
        total=0
        for gpu in (5,6,7):total+=len(bind.validate_progress_bindings(lane_fixture(self.root,gpu))['fresh_attempts'])
        self.assertEqual(total,6)
    def change_manifest(self,lane,change):
        p=lane/'manifests/native.json';v=json.loads(p.read_text());change(v['jobs'][0]);p.write_text(json.dumps(v))
    def test_old_v2_path_rejected(self):
        lane=lane_fixture(self.root)
        self.change_manifest(lane,lambda j:j.update(progress_file='/data4/research-user/h3_runs/interval_short0177_20261024_v2/gpu7/audit/router/interval_short_0177_native__a1.json'))
        with self.assertRaises(ValueError):bind.validate_progress_bindings(lane)
    def test_wrong_attempt_path_rejected(self):
        lane=lane_fixture(self.root)
        self.change_manifest(lane,lambda j:j.update(progress_file=j['progress_file'].replace('__a1','__a2')))
        with self.assertRaises(ValueError):bind.validate_progress_bindings(lane)
    def test_missing_binding_rejected(self):
        lane=lane_fixture(self.root);self.change_manifest(lane,lambda j:j.pop('progress_file'))
        with self.assertRaises(ValueError):bind.validate_progress_bindings(lane)
    def test_existing_attempt_file_rejected(self):
        lane=lane_fixture(self.root);p=lane/'audit/router/interval_short_0177_native__a1.json';p.parent.mkdir(parents=True);p.write_text('{}')
        with self.assertRaises(ValueError):bind.validate_progress_bindings(lane)
    def test_graph_old_audit_dir_rejected(self):
        lane=lane_fixture(self.root);p=lane/'graphs/interval_short_0177_native.json';g=json.loads(p.read_text());g['50']['inputs']['audit_dir']='/old/audit/router';p.write_text(json.dumps(g))
        with self.assertRaises(ValueError):bind.validate_progress_bindings(lane)
    def test_graph_old_run_id_rejected(self):
        lane=lane_fixture(self.root);p=lane/'graphs/interval_short_0177_native.json';g=json.loads(p.read_text());g['50']['inputs']['run_id']='old__a1';p.write_text(json.dumps(g))
        with self.assertRaises(ValueError):bind.validate_progress_bindings(lane)
    def test_symlink_audit_directory_rejected(self):
        lane=lane_fixture(self.root);(self.root/'other').mkdir();(lane/'audit').mkdir();(lane/'audit/router').symlink_to(self.root/'other',target_is_directory=True)
        with self.assertRaises(ValueError):bind.validate_progress_bindings(lane)

if __name__=='__main__':unittest.main()
