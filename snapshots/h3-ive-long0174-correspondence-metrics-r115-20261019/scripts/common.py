"""Independent bindings for the actual R115 videos, frozen banks and release."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPERATORS = ('fixed_one_bin', 'matched_one_bin')
ARMS = OPERATORS
RUN_ARMS = OPERATORS


def read(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')


def bound(path):
    return {'file': str(Path(path).resolve()), 'sha256': sha(path)}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def relative(path):
    p = Path(path)
    require(not p.is_absolute() and '..' not in p.parts, 'unsafe relative artifact path')
    return p


def all_checks(value, names):
    require(all(value.get(k) is True for k in names) and
            all(v is True for v in value.values()), 'actual required checks failed')



PAIR_CHECKS = ('producer_seal', 'same_service_runtime', 'fixed_one_bin_actual_execution',
    'matched_one_bin_actual_execution', 'same_six_condition_tensors',
    'same_initial_noise_and_sigma_grid', 'two_new_arms_AV_prefix_0_5_bitwise_equal',
    'paired_all50_bank_metadata_indices_mask', 'paired_bank_collection')


def verify_graphs(graphs, cfg):
    normalized=[]
    for arm in ARMS:
        graph=graphs[arm]
        require(graph['50']['inputs']['mode']==arm,'new operator mode differs')
        value=json.loads(json.dumps(graph).replace(cfg['runs'][arm], 'RUN'))
        value['50']['inputs']['mode']='COMPARED_OPERATOR'
        normalized.append(value)
    require(normalized[0]==normalized[1],'graphs differ beyond operator and run identity')


def verify_static():
    cfg=read(ROOT/'configs/contract.json')
    for name,digest in read(ROOT/'CONSUMER_FREEZE.json')['files'].items():
        require(sha(ROOT/relative(name))==digest,'consumer changed: '+name)
    for name,key in [('producer_deploy_manifest.json','producer_seal_sha256'),
                     ('producer_runtime.json','producer_runtime_sha256'),
                     ('HISTORICAL_NATIVE.json','historical_native_sha256'),
                     ('HISTORICAL_NATIVE_GATE.json','historical_native_gate_sha256')]:
        require(sha(ROOT/'configs'/name)==cfg[key],'producer binding changed: '+name)
    for section in ('historical_media','historical_evidence'):
        for name,item in cfg[section].items():
            require(sha(item['file'])==item['sha256'],'historical binding changed: '+name)
    verify_graphs({a:read(ROOT/'configs'/('graph_'+a+'.json')) for a in ARMS},cfg)
    return cfg


def verify_run_record(row, arm, cfg):
    require(row['run_id'] == cfg['runs'][arm], 'new run identity differs')
    require((row['NFE'], row['Euler_updates'], row['routed_blocks'], row['valid_frames']) ==
            (20,20,450,145), 'new run work or support differs')
    require(Path(row['video']['file']) == Path(cfg['producer_remote'])/'output'/(row['run_id']+'_00001_.mp4'),
            'unexpected generated output path')
    p = row['video']['properties']
    require((p['width'],p['height'],p['avg_frame_rate'],int(p['nb_read_frames'])) ==
            (1312,736,'24/1',158), 'generated output geometry differs')


def verify_prefix(rows):
    require(len(rows) == 6, 'six pre-intervention predictions required')
    for i,row in enumerate(rows):
        require(row['step_zero_based'] == i and row['model_call_one_based'] == i+1 and
                row['video'] is True and row['audio'] is True, 'actual AV prefix differs')
        for key in ('parent_file_sha256','current_file_sha256'):
            require(len(row[key])==64,'new prediction file binding absent')


def verify_geometry(gate):
    require((gate['valid_frames'],gate['total_frames'],gate['fps']) == (145,158,24)
            and gate['evaluation_crop_xywh'] == [16,8,1280,720]
            and gate['first_allowed_prediction_divergence_index'] == 6,
            'actual physical support or intervention start differs')


def verify_gate(pair, cfg):
    require(pair.get('schema')=='r115-two-new-arm-runtime-gate-v1' and pair.get('passed') is True,
            'actual R115 two-arm gate failed')
    all_checks(pair['checks'],PAIR_CHECKS);verify_geometry(pair)
    require(pair['source_id']=='long_0174' and pair['runtime_profile_sha256']==cfg['producer_runtime_sha256']
        and pair['producer_seal_sha256']==cfg['producer_seal_sha256'],'actual producer/runtime differs')
    require(pair['runtime_profile']==read(ROOT/'configs/producer_runtime.json'),'runtime metadata differs')
    require(set(pair['runs'])=={'native',*ARMS} and pair['new_run_ids']==[cfg['runs'][a] for a in ARMS],
            'exact two new operators and existing Native required')
    historical=read(ROOT/'configs/HISTORICAL_NATIVE.json')
    expected_native={**historical['run'],'historical_parent':True,'same_host_strict_comparison':False}
    require(pair['historical_native']==historical and pair['runs']['native']==expected_native and
            pair['historical_native_gate_sha256']==cfg['historical_native_gate_sha256'] and
            pair['historical_cross_host_prefix_equality_required'] is False,
            'existing Native provenance differs')
    require(expected_native['video']['sha256']==cfg['historical_media']['native']['sha256'],
            'existing Native bytes differ')
    runtime=pair['runtime_profile'];owner=pair['service_owner']
    require(owner['gpu_uuid']==runtime['gpu_uuid'] and owner['port']==runtime['port'] and
        owner['identity']['uid']==runtime['uid'] and
        str(Path(cfg['producer_remote'])/'scripts/service_entry.py') in owner['identity']['cmdline'],
        'new service identity differs')
    verify_prefix(pair['prefix_tensor_comparison'])
    require(len(pair['condition_tensor_files'])==6,'six condition tensor bindings required')
    require(set(pair['banks'])==set(cfg['runs'].values()),'two new bank collections required')
    for i,arm in enumerate(ARMS):
        row=pair['runs'][arm];verify_run_record(row,arm,cfg)
        require(row['prefix_scope']==('self_file_integrity' if i==0 else 'equal_to_first_new_arm'),
                'new-arm prefix scope differs')
        bank=pair['banks'][cfg['runs'][arm]]
        require(bank['passed'] is True and bank['collection_sha256']==pair['paired_bank_collection_sha256'],
                'paired frozen bank differs')
    return pair['runs']


def verify_banks(folder, pair, cfg):
    """Read all compact arrays; verify their bytes, reciprocals and common masks on CPU."""
    import numpy as np
    records={}
    def tensor_digest(array,dtype):
        return hashlib.sha256(canonical({'shape':list(array.shape),'dtype':dtype})+array.tobytes()).hexdigest()
    for arm in ARMS:
        run=cfg['runs'][arm]; gate=pair['banks'][run]; blocks={}; proofs=[]
        require(gate['capture_step']==5 and len(gate['blocks'])==50 and len(gate['files'])==100,
                'complete fifty-bank evidence required')
        for block in range(50):
            root=folder/'banks'/arm/f'block_{block:02d}'; meta=read(root/'bank.json'); data=root/'indices.npz'
            require(meta['storage']=={'file':'indices.npz','sha256':sha(data)}, 'stored bank bytes differ')
            base={k:v for k,v in meta.items() if k!='storage'}
            require(base=={k:v for k,v in gate['blocks'][block].items() if k!='block'}, 'bank metadata differs')
            require(gate['blocks'][block]['block']==block and meta['metadata']['block']==block
                    and meta['metadata']['source_step']==5 and meta['metadata']['spatial_grid']==[23,41],
                    'bank position provenance differs')
            g=meta['metadata']['geometry']
            require(g=={'batch':1,'heads':56,'total_bins':47,'valid_bins':43,'frame_rows':943,'head_dim':128},
                    'bank geometry differs')
            with np.load(data,allow_pickle=False) as z:
                require(set(z.files)=={'forward','backward'},'unexpected bank arrays')
                arrays=np.stack([z['forward'],z['backward']]).astype('<i8')
                require(all(np.issubdtype(z[x].dtype,np.integer) for x in z.files),'integer bank required')
            require(arrays.shape==(2,42,943) and np.all((arrays>=-1)&(arrays<943)),'bank indices outside support')
            for forward,backward in zip(*arrays):
                positions=np.arange(943); valid=forward>=0; reverse=backward>=0
                require(np.array_equal(backward[forward[valid]],positions[valid]) and
                        np.array_equal(forward[backward[reverse]],positions[reverse]),'nonreciprocal bank')
            require(tensor_digest(arrays,'torch.int64')==meta['indices_sha256'] and
                    tensor_digest(arrays>=0,'torch.bool')==meta['masks_sha256'], 'bank tensor digest differs')
            body={k:v for k,v in base.items() if k!='bank_sha256'}
            require(hashlib.sha256(canonical(body)).hexdigest()==meta['bank_sha256'],'bank content hash differs')
            blocks[str(block)]=meta['bank_sha256']; proofs.append({'block':block,'bank_sha256':meta['bank_sha256']})
            for name in ('bank.json','indices.npz'):
                original=str(Path(cfg['producer_remote'])/'audit/correspondence_banks'/run/f'block_{block:02d}'/name)
                matches=[x for x in gate['files'] if x['file']==original]
                require(len(matches)==1 and sha(root/name)==matches[0]['sha256'] and
                        (root/name).stat().st_size==matches[0]['bytes'],'bank file gate binding differs')
        require(hashlib.sha256(canonical(blocks)).hexdigest()==pair['paired_bank_collection_sha256'],
                'full bank collection digest differs')
        records[arm]=proofs
    require(records[ARMS[0]]==records[ARMS[1]],'paired bank arrays/masks differ')
    return records


def verify_release(pair,complete,release,started,cleanup,gate_sha,cfg):
    owner=pair['service_owner']
    require(complete.get('passed') is True and complete.get('GPU_released') is True and
            complete.get('jobs')==[cfg['runs'][a] for a in ARMS] and complete.get('remaining')==[],
            'completed two-run queue required')
    require(complete['runtime_gate_sha256']==gate_sha,'completed paired gate hash differs')
    require(release.get('passed') is True and release.get('process_absent') is True and
            release.get('CUDA_allocation_absent') is True,'exact release pending')
    require(release['owner']==started['owner']==owner,'service generation differs')
    require(cleanup['pid']==owner['pid'] and cleanup['process_absent'] is True
            and cleanup['own_compute_absent'] is True,'cleanup service mismatch')


def verify_job(folder,pair,cfg,arm):
    graph,job,history,router=[read(folder/(arm+'_'+n+'.json')) for n in ('graph','job','history','router')]
    for kind,key in [('job','job_sha256'),('history','history_sha256'),('router','router_file_sha256')]:
        require(sha(folder/(arm+'_'+kind+'.json'))==pair['runs'][arm][key],'actual evidence hash differs: '+kind)
    require(graph==read(ROOT/'configs'/('graph_'+arm+'.json')),'actual arm graph differs')
    run=cfg['runs'][arm];owner=pair['service_owner']
    require(job['status']=='success' and job['name']==run and job['graph_sha256']==sha(folder/(arm+'_graph.json'))
            and job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'],'actual arm job differs')
    require(history['status']['completed'] is True and history['status']['status_str']=='success'
            and history['prompt'][2]==graph and history['prompt'][1]==job['prompt_id'],'actual history differs')
    expected={'run_id':run,'mode':arm,'alpha':1.,'radius':0,'time_offset':0,
        'block_interval_half_open':[0,50],'step_interval_half_open':[6,15],'pixel_interval_inclusive':[0,144],
        'completed_forward_calls':20,'routed_calls':450,'routed_by_forward':[0]*6+[50]*9+[0]*5,'routed_by_block':[9]*50}
    require(all(router.get(k)==v for k,v in expected.items()),'actual intervention schedule differs')
    require(router['correspondence_bank_collection']['collection_sha256']==pair['paired_bank_collection_sha256']
            and router['correspondence_prefix_gate']['passed'] is True,'router frozen bank or prefix differs')


def verify_collection(folder):
    folder=Path(folder);cfg=verify_static();receipt=read(folder/'COLLECTION.json')
    require(receipt['passed'] is True and receipt['consumer_freeze_sha256']==sha(ROOT/'CONSUMER_FREEZE.json'),
            'consumer intake binding differs')
    require(receipt['roles']==['source','native',*ARMS], 'collected roles differ')
    for name,digest in receipt['files'].items():
        require(sha(folder/relative(name))==digest,'collected file changed: '+name)
    pair=read(folder/'PAIR_RUNTIME_GATE.json');verify_gate(pair,cfg)
    require(read(folder/'service.json')==pair['service_owner'],'service receipt changed')
    for arm in ARMS:
        verify_job(folder,pair,cfg,arm)
        require(sha(folder/(arm+'.mp4'))==pair['runs'][arm]['video']['sha256'],'new operator video differs')
    verify_release(pair,read(folder/'COMPLETE.json'),read(folder/'ROOT_EXIT_RECEIPT.json'),
        read(folder/'STARTED.json'),read(folder/'cleanup.json'),sha(folder/'PAIR_RUNTIME_GATE.json'),cfg)
    verify_banks(folder,pair,cfg)
    for role,item in cfg['historical_media'].items():
        require(sha(folder/(role+'.mp4'))==item['sha256'],'existing media bytes differ')
    return receipt
