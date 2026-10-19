"""Independent CPU audit of two terminal predictions and passive readouts."""
import argparse,json,math,sys
from pathlib import Path
import torch
from r46_contract import ROOT,read,sha,require,registry,validate_job,identity_schema
sys.path.insert(0,str(ROOT/'extensions'))
from H3AttentionStateProbe.source import Source
from H3AttentionStateProbe.dependencies import readout
from H3AttentionStateProbe.probe import describe


def inside(root,path):
    path=Path(path);require(path.is_absolute() and path.resolve().is_relative_to(Path(root).resolve()) and not path.is_symlink(),'archive path escaped')
    return path


def validate_report(report,label,source):
    require(report['schema']=='r46-single-state-report-v1' and report['label']==label and report['status']=='complete','incomplete/wrong-state report')
    require(report['source_run']==source['source_run'] and report['seed']==source['seed'] and
            report['condition_sha256']==source['condition']['sha256'] and report['raw_input_signature']==source['raw_input']['packed_signature'], 'report source/input differs')
    require(report['DiT_NFE']==report['attempted_forwards']==report['completed_forwards']==1 and report['completed_blocks']==report['native_attention_calls']==50 and
            all(report[k]==0 for k in ['Euler_updates','ordinary_callbacks','VAE_calls','Qwen_calls','routed_calls']), 'terminal prediction counts differ')
    require(report['Native_AV_bitwise_equal'] is True and report['input_sigma_grid_condition_RNG_unchanged'] is True and
            report['original_UUID_restored'] is True and report['materialization_rng_unchanged'] is True, 'runtime exact gates incomplete')
    require(report['actual_sigma']==source['full_grid'][4] and report['full_grid']==source['full_grid'],'grid/sigma differs')
    head=report['output_head'];require(head['index']==4 and head['sigma']==source['full_grid'][4] and head['sigma_next']==source['full_grid'][5] and
        head['pdd_active'] is False and head['bank_size']==1 and head['shifts']==[12.,3.], 'actual output head gate differs')
    p=report['probe'];q=p['quality']
    require(p['block']==25 and p['heads']==[0,14,28,42] and p['queries_per_head']==1050 and q['status']=='PASS' and
            set(q['gates'])=={'finite','group_lse','subset_lse','probability_sum','query_lse_unchanged'} and all(v is True for v in q['gates'].values()) and q['additional_attention_calls']==43 and q['clamped'] is False,'probe quality/count differs')
    require(p['selected_original_QKV_output_exact'] is True and p['global_rng_unchanged'] is True and
            p['original_output_not_passed_to_statistics'] is True and p['full_QKV_copy'] is False,'passive probe gate differs')


def validate_payload(payload,report):
    require(set(payload)=={'q','reference_k','distribution','descriptors','mapping'},'unexpected probe payload (full QKV/output bank forbidden)')
    require(payload['q'].shape==(1,4,1050,128) and payload['reference_k'].shape==(1,4,39606,128) and
            payload['q'].dtype==payload['reference_k'].dtype==torch.bfloat16,'saved subset shape/dtype differs')
    for k in ('q','reference_k'):
        require(readout.tensor_signature(payload[k])==report['probe']['saved_tensor_signatures'][k],'raw saved subset differs')
    m=payload['mapping'];require(m==report['probe']['mapping'] and m['heads']==[0,14,28,42] and len(m['queries'])==1050,'mapping differs')
    require([(r['bin'],r['row'],r['col']) for r in m['queries']]==[(t,r,c) for t in range(42) for r in [2,6,11,16,20] for c in [4,12,20,28,36]],'query order differs')
    require(m['frame_intervals']==[[sum((1,4,4,4,4)[i%5] for i in range(t)),sum((1,4,4,4,4)[i%5] for i in range(t+1))-1] for t in range(42)],'nominal frame spans differ')
    for r in m['queries']:
        require(r['local_index']==r['bin']*943+r['row']*41+r['col'] and r['packed_index']==47986+r['local_index'] and
                r['source_frames_inclusive']==m['frame_intervals'][r['bin']],'packed row mapping differs')
    d=payload['distribution'];require(d['quality']==report['probe']['quality'],'quality differs')
    expected={'bin_lse':(1,4,1050,42),'probabilities':(1,4,1050,42),'reference_lse':(1,4,1050),
              'reduced_reference_lse':(1,4,1050),'full_lse':(1,4,1050),'reference_mass':(1,4,1050),
              'reference_output':(1,4,1050,128),'same_bin_output':(1,4,1050,128),
              'mass_weighted_readout_difference_l2':(1,4,1050),'mass_weighted_readout_difference_rms':(1,4,1050)}
    require(set(d)==set(expected)|{'quality'},'unexpected saved distribution fields')
    for key,shape in expected.items():require(tuple(d[key].shape)==shape and bool(torch.isfinite(d[key]).all()),'distribution shape/finite '+key)
    require(d['reference_output'].dtype==d['same_bin_output'].dtype==torch.bfloat16 and
            all(d[k].dtype==torch.float32 for k in expected if k not in ('reference_output','same_bin_output')),
            'saved statistic dtype differs')
    reduced=torch.logsumexp(d['bin_lse'],-1)
    require(float((reduced-d['reference_lse']).abs().max())<=0.005 and
            float((reduced-d['full_lse']).max())<=0.005 and
            float((d['probabilities'].sum(-1)-1).abs().max())<=2e-5, 'independent numerical bounds failed')
    require(torch.allclose(reduced,d['reduced_reference_lse'],atol=2e-5,rtol=0) and
            torch.allclose((d['bin_lse']-reduced[...,None]).exp(),d['probabilities'],atol=2e-5,rtol=2e-5) and
            torch.allclose((reduced-d['full_lse']).exp(),d['reference_mass'],atol=2e-5,rtol=2e-5),'stored probability formula differs')
    # GPU and CPU exp/reduction can differ at rounding level: independent numeric
    # recomputation uses frozen tolerances; exact bytes are protected by PT SHA.
    fresh=describe(d,m)
    for key,value in fresh.items():
        saved=payload['descriptors'][key]
        if isinstance(value,torch.Tensor):require(torch.allclose(value,saved,atol=2e-5,rtol=2e-5),'descriptor numeric differs '+key)
        elif isinstance(value,float):require(math.isclose(value,saved,abs_tol=2e-5,rel_tol=2e-5),'descriptor scalar differs '+key)
        else:require(value==saved,'descriptor field differs '+key)
    delta=d['reference_mass'][...,None]*(d['same_bin_output'].float()-d['reference_output'].float())
    require(torch.allclose(delta.norm(dim=-1),d['mass_weighted_readout_difference_l2'],atol=2e-5,rtol=2e-5) and
            torch.allclose(delta.square().mean(-1).sqrt(),d['mass_weighted_readout_difference_rms'],atol=2e-5,rtol=2e-5),'readout difference norm differs')


def check(root=ROOT,allow_resident=False):
    from preflight import check as preflight
    root=Path(root);preflight(root)
    owner=read(root/'processes/service.json');identity_schema(owner['identity'])
    records=[]
    for name in registry(root)[1]:
        binding=validate_job(name,root);label=binding['label'];source=Source(label,root)
        job=read(root/'logs'/f'{name}_job.json');history=read(root/'logs'/f'{name}_history.json')
        require(job['status']=='success' and job['name']==name and job['graph_sha256']==binding['graph_sha256'] and
                job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'],'submission/generation differs')
        require(history['status']['status_str']=='success' and history['status']['completed'] is True and
                history['prompt'][1]==job['prompt_id'] and history['prompt'][2]==read(root/'configs/graphs'/f'{name}.json'),'actual history/prompt differs')
        folder=root/'audit/probe'/label;report=read(folder/'report.json');validate_report(report,label,source.s)
        require(report['source_binding_sha256']==sha(root/'configs/sources.json') and report['protocol_sha256']==sha(root/'configs/SCIENCE_PROTOCOL.json'),'report source binding differs')
        require({x.name for x in folder.iterdir()}=={'attention.pt','endpoint_raw.pt','report.json'},'probe output inventory differs')
        att=inside(root,report['probe']['file']);ep=inside(root,report['endpoint_file'])
        require(att==folder/'attention.pt' and ep==folder/'endpoint_raw.pt' and sha(att)==report['probe']['file_sha256'] and sha(ep)==report['endpoint_sha256'],'output path/SHA differs')
        payload=torch.load(att,map_location='cpu',weights_only=True);validate_payload(payload,report)
        endpoint=torch.load(ep,map_location='cpu',weights_only=True);expected=source.endpoint()
        require(set(endpoint)=={'video','audio_raw'} and all(torch.equal(endpoint[k],v) for k,v in zip(['video','audio_raw'],expected)),'independent historical AV exact failed')
        records.append({'state':label,'report_sha256':sha(folder/'report.json'),'attention_sha256':sha(att),'endpoint_sha256':sha(ep),
                        'DiT_NFE':1,'Euler_updates':0,'historical_endpoint_independently_exact':True})
    if allow_resident:
        import service
        service.assert_owned(owner)
    else:
        cleanup=read(root/'processes/cleanup.json')
        require(cleanup['pid']==owner['pid'] and cleanup['service_record']==owner and cleanup['process_absent'] is True and
                cleanup['own_compute_absent'] is True,'exact generation cleanup incomplete')
    return {'passed':True,'states':records,'total_DiT_NFE':2,'Euler_updates':0,'VAE_Qwen_calls':0,
            'quality_scope':'internal attention descriptors only; no calibrated action-delay or novelty conclusion',
            'service_owner':owner,'resident':allow_resident}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--allow-resident',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args();result=check(a.root,a.allow_resident)
    if a.output:a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
