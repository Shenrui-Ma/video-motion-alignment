"""Small JSON-only binding checks; no tensor/model/pose execution."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import intake_parent_metadata as m


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.archive=Path(self.tmp.name)
        self.case=json.loads((ROOT/'configs/protocol.json').read_text())['cases'][0]
        self.graph=json.loads((ROOT/'configs/parent_graphs'/(self.case['parent_run']+'.json')).read_text())
        self.inventory={}

    def put(self,name,value):
        p=self.archive/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(value));self.inventory[name]={'bytes':p.stat().st_size,'sha256':m.sha(p)}
        return p

    def fixture(self):
        run=self.case['parent_run']
        self.put(f'configs/graphs/{run}.json',self.graph)
        self.put(f'logs/{run}_history.json',{'status':{'completed':True,'status_str':'success'},'prompt':[0,'actual-id',self.graph]})
        self.put(f'logs/{run}_job.json',{'name':run,'status':'success','prompt_id':'actual-id','graph_sha256':self.inventory[f'configs/graphs/{run}.json']['sha256']})

    def check(self):return m.inspect_case(self.archive,self.case,self.graph,self.inventory)

    def test_empty_actual_archive_stays_pending(self):
        result=m.inspect(self.archive)
        self.assertEqual(result['status'],'WAITING_R49_ARCHIVE');self.assertFalse(result['production_ready'])
        self.assertEqual(len(result['runs']),5)

    def test_partial_actual_files_are_recorded_without_parent_ready(self):
        self.fixture();value=self.check()
        self.assertEqual(value['status'],'WAITING_ACTUAL_PARENT');self.assertEqual(len(value['files']),3)
        self.assertFalse(value['tensor_payloads_loaded_or_reverified']);self.assertFalse(value['production_ready'])

    def test_changed_or_unanchored_file_rejected(self):
        self.fixture();name=f"configs/graphs/{self.case['parent_run']}.json"
        original=(self.archive/name).read_bytes();(self.archive/name).write_bytes(original+b' ')
        with self.assertRaisesRegex(ValueError,'changed parent'):self.check()
        (self.archive/name).write_bytes(original);self.inventory.pop(name)
        with self.assertRaisesRegex(ValueError,'unanchored'):self.check()

    def test_wrong_actual_graph_or_submission_rejected(self):
        self.fixture();run=self.case['parent_run'];bad=copy.deepcopy(self.graph);bad['6']['inputs']['noise_seed']+=1
        self.put(f'configs/graphs/{run}.json',bad)
        with self.assertRaisesRegex(ValueError,'frozen per-source'):self.check()
        self.fixture();h=json.loads((self.archive/f'logs/{run}_history.json').read_text());h['prompt'][1]='other-id';self.put(f'logs/{run}_history.json',h)
        with self.assertRaisesRegex(ValueError,'submission mismatch'):self.check()

    def test_failed_history_rejected_not_pending(self):
        self.fixture();run=self.case['parent_run'];h=json.loads((self.archive/f'logs/{run}_history.json').read_text());h['status']['completed']=False;self.put(f'logs/{run}_history.json',h)
        with self.assertRaisesRegex(ValueError,'complete successfully'):self.check()

    def test_capture_schema_and_inventory_not_trusted_from_self_count(self):
        self.fixture();run=self.case['parent_run'];names=[f'x0_step{i:03d}.pt' for i in range(20)]
        value={'run_id':run,'status':'complete','callback_count':20,'seed':self.case['seed'],'geometry':self.case['geometry'],'capture_steps_zero_based':list(range(20)),
               'captures':[{'file':n} for n in names],'final_sampler_result':{'file':'sampler_final.pt'}}
        self.put(f'audit/x0/{run}/manifest.json',value)
        with self.assertRaisesRegex(ValueError,'tensor absent'):self.check()
        for name in names+['sampler_final.pt']:self.inventory[f'audit/x0/{run}/'+name]={'bytes':1,'sha256':'0'*64}
        result=self.check();self.assertEqual(len(result['tensor_inventory']),21);self.assertFalse(result['tensor_payloads_loaded_or_reverified'])
        value['captures'][19]['file']='x0_step018.pt';self.put(f'audit/x0/{run}/manifest.json',value)
        with self.assertRaisesRegex(ValueError,'21 captures'):self.check()

    def test_path_escape_rejected(self):
        for path in ('../outside.pt','/outside.pt'):
            with self.assertRaises(ValueError):m.safe(self.archive,path)

if __name__=='__main__':unittest.main()
