import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import torch

from fork_support import ROOT, make_case
from H3OneStepForkAudit.core import Source, SOURCE_RUN, readout


def write_source(path, source):
    snapshots=path/f'audit/counterfactual/{SOURCE_RUN}_snapshots'
    snapshots.mkdir(parents=True)
    (path/'analysis').mkdir()
    branch_rows=[];input_rows=[];files=[];nfe=0
    ref=next(iter(source.rows.values()))['reference_sha256']
    for n in range(20):
        for branch in (['native','full'] if 6<=n<15 else ['native']):
            row={'physical_index':n,'branch':branch,'nfe_index':nfe};nfe+=1
            if (n,branch) in source.rows and (n in [6,10,14] or branch=='native'):
                packed,original=source.endpoint(n,branch)
                row.update(original,sigma=source.c['full_grid'][n],sigma_next=source.c['full_grid'][n+1],
                    seed=source.c['seed'],condition_sha256=source.condition['sha256'],reference_sha256=ref)
                cut=torch.Size(source.shapes[0]).numel()
                video=packed[:,:,:cut].reshape(source.shapes[0]);audio=packed[:,:,cut:].reshape(source.shapes[1])*0.25
                filename=snapshots/f'step{n:03d}_{branch}.pt'
                torch.save({'video':video,'audio':audio,'metadata':dict(row)},filename)
                row.update(file=str(filename),file_sha256=hashlib.sha256(filename.read_bytes()).hexdigest())
                files.append(filename)
            branch_rows.append(row)
    for n in [6,10,14]:
        x,_=source.input(n)
        row={'physical_index':n,'sigma':source.c['full_grid'][n],'sigma_next':source.c['full_grid'][n+1],
            'full_grid':source.c['full_grid'],'seed':source.c['seed'],'condition_sha256':source.condition['sha256'],
            'reference_sha256':ref,'packed_signature':readout.tensor_signature(x),
            'coordinate_system':'raw sampler packed video/audio; no process_latent_out'}
        filename=snapshots/f'step{n:03d}_input_raw.pt'
        torch.save({'packed':x,'metadata':dict(row)},filename)
        row.update(file=str(filename),file_sha256=hashlib.sha256(filename.read_bytes()).hexdigest())
        input_rows.append(row);files.append(filename)
    c=dict(source.c,actual_model_nfe=29,callback_count=20,branches=branch_rows,inputs=input_rows,conditioning=source.condition)
    audit=path/f'audit/counterfactual/{SOURCE_RUN}.json'
    audit.write_text(json.dumps({'status':'complete','completed_calls':1450,'routed_calls':450,'counterfactual':c}))
    pair=path/'analysis/parent_pair_check.json'
    pair.write_text(json.dumps({'passed':True,'parent_final_video_audio_exact':True}))
    files.extend([audit,pair])
    manifest=path/'source_manifest.json'
    manifest.write_text(json.dumps({'schema':'h3-r13-source-binding-v1','status':'bound','source_root':str(path),
        'source_run':SOURCE_RUN,'files':{str(f.relative_to(path)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}))
    return manifest


class SourceConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def test_actual_archive_loader_and_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);case=make_case(p);manifest=write_source(p/'source',case[0].source)
            bound=Source(manifest)
            for n in [6,10,14]:
                x,_=bound.input(n)
                self.assertTrue(torch.equal(x,case[0].source.input(n)[0]))
                for step,branch in [(n,'native'),(n,'full'),(n+1,'native')]:
                    y,_=bound.endpoint(step,branch)
                    self.assertTrue(torch.equal(y,case[0].source.endpoint(step,branch)[0]))
            target=bound.root/f'audit/counterfactual/{SOURCE_RUN}_snapshots/step006_native.pt'
            with target.open('ab') as f:f.write(b'corrupt')
            with self.assertRaisesRegex(ValueError,'source changed'):bound.endpoint(6,'native')
            with self.assertRaisesRegex(ValueError,'file mismatch'):Source(manifest)

    def test_pending_binding_and_graph(self):
        sys.path.insert(0,str(ROOT/'scripts'))
        from preflight import check
        result=check(ROOT,require_source=False)
        self.assertTrue(result['validated'])
        # A deployed checkout may already be bound; test pending admission in
        # an isolated fixture instead of depending on deployment state.
        with tempfile.TemporaryDirectory() as temporary:
            pending = Path(temporary)
            for rel in ['configs/protocol.json', 'audit/parent_graph.json',
                        'configs/r13_s05_one_step_fork.json', 'configs/queue.json']:
                target = pending / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / rel).read_bytes())
            (pending / 'configs/source_manifest.json').write_text('{"status":"pending"}')
            with self.assertRaisesRegex(ValueError,'incomplete'):
                check(pending)
        from H3OneStepForkAudit import H3OneStepForkAudit
        self.assertEqual(H3OneStepForkAudit.RETURN_TYPES,('STRING',))
        self.assertTrue(H3OneStepForkAudit.OUTPUT_NODE)
        graph=json.loads((ROOT/'configs/r13_s05_one_step_fork.json').read_text())
        self.assertFalse(any(v['class_type'] in ['VAEDecode','SaveVideo','SamplerCustomAdvanced'] for v in graph.values()))

    def test_directory_import_has_no_sibling_sys_path_dependency(self):
        script = '''import importlib.util,sys,torch,os
from pathlib import Path
path=Path(sys.argv[1]); before=dict(os.environ); rng=torch.random.get_rng_state().clone()
spec=importlib.util.spec_from_file_location('/actual/path/H3OneStepForkAudit',path/'__init__.py')
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
assert module.NODE_CLASS_MAPPINGS['H3OneStepForkAudit'].RETURN_TYPES==('STRING',)
assert 'H3CounterfactualRouter' not in sys.modules
assert dict(os.environ)==before and torch.equal(rng,torch.random.get_rng_state())
print('directory import PASS')
'''
        result=subprocess.run([sys.executable,'-c',script,str(ROOT/'extensions/H3OneStepForkAudit')],
                              capture_output=True,text=True,check=True)
        self.assertIn('directory import PASS',result.stdout)

    def test_resource_and_source_path_escape(self):
        sys.path.insert(0,str(ROOT/'scripts'))
        import service
        self.assertEqual(service.PORT,8474)
        self.assertEqual(service.GPU,'GPU-REDACTED')
        self.assertIn('timing_one_step_fork_r13_20261016',str(service.RUN))
        with patch.object(service,'proc_uid',return_value=service.os.getuid()):
            with self.assertRaisesRegex(RuntimeError,'two GPUs'):
                service.check_admission({'permitted_compute_processes':[]},[
                    {'gpu_uuid':'other0','pid':100},{'gpu_uuid':'other1','pid':101}],
                    {'queue_running':[],'queue_pending':[]})
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);m=p/'m.json'
            m.write_text(json.dumps({'schema':'h3-r13-source-binding-v1','status':'bound','source_run':SOURCE_RUN,
                'source_root':str(p),'files':{'../../escaped':'bad'}}))
            with self.assertRaisesRegex(ValueError,'escape'):Source(m)

if __name__=='__main__':unittest.main()
