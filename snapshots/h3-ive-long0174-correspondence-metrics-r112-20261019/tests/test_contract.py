import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from common import ARMS,PAIR_CHECKS,RUN_CHECKS,read,sha,canonical,verify_graphs,verify_gate,verify_banks,relative
P=R.parent/'h3-timing-ive-long0174-correspondence-r112-20261019'


def fixture():
    cfg=read(R/'configs/contract.draft.json');cfg.update(producer_runtime_sha256=sha(P/'configs/runtime.json'),
        producer_seal_sha256='testseal',fixed_binding=read(P/'design/R107_FIXED_BINDING.json'),
        fixed_producer_remote=read(R.parent/'h3-ive-long0174-guidance-metrics-r107-20261019/configs/contract.json')['producer_remote'])
    prior=read(cfg['historical_evidence']['R107_GATE']['file']);native=prior['runs']['native'];fixed=prior['runs']['forced']
    owner={'pid':123,'identity':{'uid':1004,'start_ticks':'12345'}}
    prefix=[{'step_zero_based':i,'model_call_one_based':i+1,'video':True,'audio':True,
        'parent_file_sha256':x['sha256'],'current_file_sha256':'testcurrent'+str(i)} for i,x in enumerate(cfg['first_six_predictions'])]
    pair={'schema':'r112-four-run-runtime-gate-v1','passed':True,'checks':dict.fromkeys(PAIR_CHECKS,True),
        'source_id':'long_0174','runtime_profile_sha256':cfg['producer_runtime_sha256'],'runtime_profile':read(P/'configs/runtime.json'),
        'producer_seal_sha256':'testseal','source_cpu_seal_sha256':cfg['producer_cpu_seal']['sha256'],
        'runs':{'native':native,'fixed':fixed},'banks':{},'paired_bank_collection_sha256':'banks',
        'prefix_tensor_comparison':copy.deepcopy(prefix),'service_owner':owner,'valid_frames':145,'total_frames':158,'fps':24,
        'evaluation_crop_xywh':[16,8,1280,720],'first_allowed_prediction_divergence_index':6,'run_gate_receipts':[]}
    gates={}
    for arm in ARMS:
        run=cfg['runs'][arm];row={'run_id':run,'NFE':20,'Euler_updates':20,'routed_blocks':450,'valid_frames':145,
            'video':{'file':cfg['producer_remote']+'/output/'+run+'_00001_.mp4','sha256':'testvideo',
                     'properties':{'width':1312,'height':736,'avg_frame_rate':'24/1','nb_read_frames':'158'}}}
        banks={'passed':True,'collection_sha256':'banks'};pair['runs'][arm]=row;pair['banks'][run]=banks
        pair['run_gate_receipts'].append({'run_id':run,'sha256':'testgate','file':'test'})
        gates[arm]={'schema':'r112-run-runtime-gate-v1','passed':True,'run_id':run,'arm':arm,'checks':dict.fromkeys(RUN_CHECKS,True),
            'runs':{'native':native,'fixed':fixed,arm:row},'banks':banks,'service_owner':owner,'runtime_profile':pair['runtime_profile'],
            'runtime_profile_sha256':pair['runtime_profile_sha256'],'prefix_tensor_comparison':copy.deepcopy(prefix),
            'valid_frames':145,'total_frames':158,'fps':24,'evaluation_crop_xywh':[16,8,1280,720],'first_allowed_prediction_divergence_index':6,
            'fixed_comparison':{'passed':True,'binding':cfg['fixed_binding'],'checks':{'fixed_exact_release':True}}}
    return cfg,pair,gates


class ContractTests(unittest.TestCase):
    def test_actual_graphs_same_scientific_inputs(self):
        cfg,_,_=fixture();verify_graphs({a:read(P/'configs/graphs'/(cfg['runs'][a]+'.json')) for a in ARMS},read(P/'design/R107_GRAPH.json'),cfg)
    def test_prompt_change_rejected(self):
        cfg,_,_=fixture();g={a:read(P/'configs/graphs'/(cfg['runs'][a]+'.json')) for a in ARMS};g[ARMS[1]]['5']['inputs']['prompt']='changed'
        with self.assertRaises(ValueError):verify_graphs(g,read(P/'design/R107_GRAPH.json'),cfg)
    def test_gate_fixture_passes(self):
        c,p,g=fixture();self.assertEqual(set(verify_gate(p,g,c)),{'native','fixed',*ARMS})
    def test_failed_prefix_rejected(self):
        c,p,g=fixture();g[ARMS[0]]['prefix_tensor_comparison'][4]['audio']=False
        with self.assertRaises(ValueError):verify_gate(p,g,c)
    def test_wrong_historical_sha_rejected(self):
        c,p,g=fixture();p['runs']['native']['video']['sha256']='other'
        with self.assertRaises(ValueError):verify_gate(p,g,c)
    def test_unchecked_gate_rejected(self):
        c,p,g=fixture();g[ARMS[1]]['checks'].pop('frozen_bank_actual_files')
        with self.assertRaises(ValueError):verify_gate(p,g,c)
    def test_wrong_support_rejected(self):
        c,p,g=fixture();p['valid_frames']=158
        with self.assertRaises(ValueError):verify_gate(p,g,c)
    def test_cross_service_rejected(self):
        c,p,g=fixture();g[ARMS[1]]['service_owner']={'pid':456}
        with self.assertRaises(ValueError):verify_gate(p,g,c)
    def test_bad_collection_rejected(self):
        c,p,g=fixture();p['paired_bank_collection_sha256']='other'
        with self.assertRaises(ValueError):verify_gate(p,g,c)
    def test_safe_paths(self):
        self.assertEqual(str(relative('banks/fixed_one_bin/block_00/bank.json')),'banks/fixed_one_bin/block_00/bank.json')
        for p in ['/tmp/evil','../evil','banks/../../evil']:
            with self.assertRaises(ValueError):relative(p)


class BankTests(unittest.TestCase):
    def create(self,folder):
        cfg=read(R/'configs/contract.draft.json');pair={'banks':{}}
        a=np.tile(np.arange(943,dtype='<i8'),(2,42,1));mask=a>=0
        def digest(x,t):return hashlib.sha256(canonical({'shape':list(x.shape),'dtype':t})+x.tobytes()).hexdigest()
        for arm in ARMS:
            run=cfg['runs'][arm];gate={'capture_step':5,'blocks':[],'files':[]};blocks={}
            for block in range(50):
                d=folder/'banks'/arm/f'block_{block:02d}';d.mkdir(parents=True)
                meta={'block':block,'source_step':5,'spatial_grid':[23,41],
                    'geometry':{'batch':1,'heads':56,'total_bins':47,'valid_bins':43,'frame_rows':943,'head_dim':128}}
                body={'schema':'r112-frozen-correspondence-bank-v1','metadata':meta,'indices_sha256':digest(a,'torch.int64'),'masks_sha256':digest(mask,'torch.bool')}
                manifest=dict(body,bank_sha256=hashlib.sha256(canonical(body)).hexdigest())
                np.savez_compressed(d/'indices.npz',forward=a[0].astype('<i4'),backward=a[1].astype('<i4'))
                (d/'bank.json').write_text(json.dumps(dict(manifest,storage={'file':'indices.npz','sha256':sha(d/'indices.npz')})))
                gate['blocks'].append({'block':block,**manifest});blocks[str(block)]=manifest['bank_sha256']
                for name in ('bank.json','indices.npz'):
                    gate['files'].append({'file':cfg['producer_remote']+'/audit/correspondence_banks/'+run+f'/block_{block:02d}/'+name,
                        'sha256':sha(d/name),'bytes':(d/name).stat().st_size})
            pair['banks'][run]=gate;pair['paired_bank_collection_sha256']=hashlib.sha256(canonical(blocks)).hexdigest()
        return cfg,pair
    def test_complete_compact_banks_and_corruption(self):
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t);c,p=self.create(folder);self.assertEqual(len(verify_banks(folder,p,c)[ARMS[0]]),50)
            file=folder/'banks/matched_one_bin/block_25/indices.npz';file.write_bytes(file.read_bytes()+b'corrupt')
            with self.assertRaises(ValueError):verify_banks(folder,p,c)
    def test_missing_bank_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t);c,p=self.create(folder);p['banks'][c['runs'][ARMS[0]]]['blocks'].pop()
            with self.assertRaises(ValueError):verify_banks(folder,p,c)

if __name__=='__main__':unittest.main()
