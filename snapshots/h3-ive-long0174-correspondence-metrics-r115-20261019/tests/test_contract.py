import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from common import ARMS,PAIR_CHECKS,read,sha,canonical,verify_graphs,verify_gate,verify_banks,relative,verify_release
P=R.parent/'h3-timing-ive-long0174-correspondence-r115-20261019'


def fixture():
    cfg=read(R/'configs/contract.draft.json');rt=read(P/'configs/runtime.json');historical=read(P/'design/HISTORICAL_NATIVE.json')
    cfg.update(producer_runtime_sha256=sha(P/'configs/runtime.json'),producer_seal_sha256='testseal',
        historical_native_gate_sha256=sha(P/'design/HISTORICAL_NATIVE_GATE.json'))
    owner={'pid':123,'gpu_uuid':rt['gpu_uuid'],'port':rt['port'],
        'identity':{'uid':1016,'start_ticks':'12345','cmdline':cfg['producer_remote']+'/scripts/service_entry.py'}}
    prefix=[{'step_zero_based':i,'model_call_one_based':i+1,'video':True,'audio':True,
        'parent_file_sha256':'a'*64,'current_file_sha256':'b'*64} for i in range(6)]
    pair={'schema':'r115-two-new-arm-runtime-gate-v1','passed':True,'checks':dict.fromkeys(PAIR_CHECKS,True),
        'source_id':'long_0174','runtime_profile_sha256':cfg['producer_runtime_sha256'],'runtime_profile':rt,
        'producer_seal_sha256':'testseal','historical_native':historical,
        'historical_native_gate_sha256':cfg['historical_native_gate_sha256'],'historical_cross_host_prefix_equality_required':False,
        'new_run_ids':[cfg['runs'][a] for a in ARMS],
        'runs':{'native':{**copy.deepcopy(historical['run']),'historical_parent':True,'same_host_strict_comparison':False}},
        'banks':{},'paired_bank_collection_sha256':'banks','condition_tensor_files':[{}]*6,
        'prefix_tensor_comparison':prefix,'service_owner':owner,'valid_frames':145,'total_frames':158,'fps':24,
        'evaluation_crop_xywh':[16,8,1280,720],'first_allowed_prediction_divergence_index':6}
    for i,arm in enumerate(ARMS):
        run=cfg['runs'][arm];pair['runs'][arm]={'run_id':run,'NFE':20,'Euler_updates':20,'routed_blocks':450,'valid_frames':145,
            'prefix_scope':'self_file_integrity' if i==0 else 'equal_to_first_new_arm',
            'video':{'file':cfg['producer_remote']+'/output/'+run+'_00001_.mp4','sha256':'testvideo',
                     'properties':{'width':1312,'height':736,'avg_frame_rate':'24/1','nb_read_frames':'158'}}}
        pair['banks'][run]={'passed':True,'collection_sha256':'banks'}
    return cfg,pair


def fixture_read(path):
    p=Path(path)
    mapping={'producer_runtime.json':P/'configs/runtime.json','HISTORICAL_NATIVE.json':P/'design/HISTORICAL_NATIVE.json'}
    return read(mapping.get(p.name,p))


class ContractTests(unittest.TestCase):
    def verify(self,p,c):
        with patch('common.read',side_effect=fixture_read):return verify_gate(p,c)
    def test_actual_graphs_same_inputs(self):
        c,_=fixture();verify_graphs({a:read(P/'configs/graphs'/(c['runs'][a]+'.json')) for a in ARMS},c)
    def test_prompt_change_rejected(self):
        c,_=fixture();g={a:read(P/'configs/graphs'/(c['runs'][a]+'.json')) for a in ARMS};g[ARMS[1]]['5']['inputs']['prompt']='changed'
        with self.assertRaises(ValueError):verify_graphs(g,c)
    def test_actual_roles_existing_native_and_two_new(self):
        c,p=fixture();self.assertEqual(set(self.verify(p,c)),{'native',*ARMS})
    def test_failed_new_prefix_rejected(self):
        c,p=fixture();p['prefix_tensor_comparison'][4]['audio']=False
        with self.assertRaises(ValueError):self.verify(p,c)
    def test_cross_host_prefix_not_required(self):
        c,p=fixture();self.verify(p,c)
        self.assertNotIn('first_six_predictions',c)
    def test_changed_historical_video_rejected(self):
        c,p=fixture();p['runs']['native']['video']['sha256']='other'
        with self.assertRaises(ValueError):self.verify(p,c)
    def test_new_native_role_rejected(self):
        c,p=fixture();p['new_run_ids'].insert(0,'unrequested_new_native')
        with self.assertRaises(ValueError):self.verify(p,c)
    def test_missing_gate_check_rejected(self):
        c,p=fixture();p['checks'].pop('paired_all50_bank_metadata_indices_mask')
        with self.assertRaises(ValueError):self.verify(p,c)
    def test_failed_extra_check_rejected(self):
        c,p=fixture();p['checks']['unexpected_failure']=False
        with self.assertRaises(ValueError):self.verify(p,c)
    def test_valid_support_rejected_if_158(self):
        c,p=fixture();p['valid_frames']=158
        with self.assertRaises(ValueError):self.verify(p,c)
    def test_wrong_service_uid_rejected(self):
        c,p=fixture();p['service_owner']['identity']['uid']=1004
        with self.assertRaises(ValueError):self.verify(p,c)
    def test_bad_bank_collection_rejected(self):
        c,p=fixture();p['paired_bank_collection_sha256']='other'
        with self.assertRaises(ValueError):self.verify(p,c)
    def test_exact_release_and_gate_binding(self):
        c,p=fixture();owner=p['service_owner']
        complete={'passed':True,'GPU_released':True,'jobs':p['new_run_ids'],'remaining':[],'runtime_gate_sha256':'gate'}
        release={'passed':True,'process_absent':True,'CUDA_allocation_absent':True,'owner':owner}
        cleanup={'pid':123,'process_absent':True,'own_compute_absent':True};started={'owner':owner}
        verify_release(p,complete,release,started,cleanup,'gate',c)
        complete['runtime_gate_sha256']='other'
        with self.assertRaises(ValueError):verify_release(p,complete,release,started,cleanup,'gate',c)
    def test_live_gpu_rejected(self):
        c,p=fixture();owner=p['service_owner']
        with self.assertRaises(ValueError):verify_release(p,{'passed':True,'GPU_released':False,'jobs':p['new_run_ids'],'remaining':[]},
            {},{},{},'gate',c)
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
