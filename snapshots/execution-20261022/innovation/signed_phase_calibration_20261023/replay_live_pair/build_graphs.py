"""Freeze two full original Euler trajectories, with a passive callback wrapper."""
import argparse,copy,hashlib,json,struct
from pathlib import Path

ROOT='/data/research-user/h3_inference_20261023/live_phase_pair_20261023'
CACHE='/data/research-user/h3_inference_20261023/run_uniform_energy/innovation_cache/short_0358/manifest.json'
CACHE_SHA='ad361d036ee933cc0a72ad549ce384c883f0025922d3ee5c586370029be963f2'
MODEL_SHA='9255f52b6677845ad238f20dfaafa94727053694127ab7f255c048f0f9365779'
NOISE='/data/research-user/h3_inference_20261023/signed_phase_calibration_20261023/inputs/original_noise.pt'
NOISE_SHA='5439f8f84b471b7d53e431b886c730fc7e78492b159ce7658e08a2bad046b310'
NOISE_TENSOR_SHA='564dd8a5d999279ffed272b8df53211610648f4e985d53e29feab5f94118eda8'
PLAN_SHA='d0a3b95f861b0392b1dcef2cdb7122209758a5d80f3130ae3e50fc1841b90d78'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def fp32(x):return struct.unpack('f',struct.pack('f',float(x)))[0]
def jsonsave(path,obj):Path(path).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')

def build(original,method,contract_path,contract_sha):
    if method not in ('native','global_weak'):raise ValueError('frozen pair only')
    expected={'mode':'native','alpha':1.,'radius':0,'time_offset':0,'start_frame':0,'end_frame':104,'block_start':0,'block_end':50,'step_start':6,'step_end':15}
    if original['50']['class_type']!='H3TemporalRouter' or any(original['50']['inputs'][k]!=v for k,v in expected.items()):raise ValueError('original native router differs')
    if original['41']['inputs']!={'model':['1',0],'shift_video':12.,'shift_audio':3.} or original['6']['inputs']['noise_seed']!=2026101701:raise ValueError('original seed/shifts differ')
    if original['8']!={'class_type':'KSamplerSelect','inputs':{'sampler_name':'euler'}}:raise ValueError('original sampler differs')
    if original['1']['inputs']!={'unet_name':'minimax_h3_ref2va_pruned_int8_convrot.safetensors','weight_dtype':'default'}:raise ValueError('original checkpoint/casting differs')
    if (original['5']['inputs']['width'],original['5']['inputs']['height'],original['5']['inputs']['length'])!=(1312,736,107):raise ValueError('original geometry differs')
    run='live_phase_short0358_'+method+'_20261023'
    graph={k:copy.deepcopy(original[k]) for k in ('1','3','4','41','8','9','10','11','12','13','14')}
    graph['5']={'class_type':'H3TrustedConditionCache','inputs':{'cache_manifest':CACHE,'manifest_sha256':CACHE_SHA}}
    graph['6']={'class_type':'H3HistoricalNoise','inputs':{'noise_file':NOISE,'noise_sha256':NOISE_SHA,'seed':2026101701}}
    route={**expected,'model':['41',0],'positive':['5',0],'schedule':'fixed','run_id':run,'audit_dir':ROOT+'/audit/router'}
    if method=='global_weak':route.update(mode='mass_preserve',alpha=.25,schedule='global_weak',step_start=0,step_end=20)
    graph['50']={'class_type':'H3StudySchedule','inputs':route}
    graph['52']={'class_type':'H3LivePhaseObservation','inputs':{'model':['50',0],'observation_contract':contract_path,'contract_sha256':contract_sha}}
    graph['7']={'class_type':'BasicGuider','inputs':{'model':['52',0],'conditioning':['5',0]}}
    graph['10']['inputs']['latent_image']=['5',1]
    graph['14']['inputs']['filename_prefix']=run+'/'+run
    diff={'status':'review_only_not_submitted','method':method,'trajectory_id':run,
          'exact_preserved_nodes':['1','3','4','41','8','9','11','12','13'],
          'sample_path':'original SamplerCustomAdvanced / BasicGuider / KSAMPLER(sample_euler); only passive SAMPLER_SAMPLE wrapper',
          'sampler10_only_change':{'latent_image':[['51',1],['5',1]]},
          'conditioning':'SHA-pinned original complete embedding/tags/positions/reference/zero target; no reencoding',
          'noise':'SHA-pinned original FP32 video+audio noise; no regeneration',
          'removed_old_writer_classes':['H3EventAuditReference','H3EventAuditNoise','H3PairConditionSnapshot','H3X0Readout'],
          'new_writer_paths':[route['audit_dir'],ROOT+'/audit/live_phase/'+run,ROOT+'/output/'+run],
          'old_graph_canonical_sha256':canonical(original),'new_graph_canonical_sha256':canonical(graph),
          'physical_model_forward_count':20,'extra_model_forward_count':0,'final_VAE_decode_only':True,
          'native_before_weak':'native complete audit/video and natural service exit required before weak',
          'new_video_needs_new_event_annotation':True}
    for node in diff['exact_preserved_nodes']:
        if graph[node]!=original[node]:raise AssertionError('frozen node changed')
    return graph,diff

def contract(original,method):
    run='live_phase_short0358_'+method+'_20261023'
    route={'mode':'native','alpha':1.,'active_steps':list(range(6,15)),'radius':0,'time_offset':0,'start_frame':0,'end_frame':104,'block_start':0,'block_end':50}
    if method=='global_weak':route.update(mode='mass_preserve',alpha=.25,active_steps=list(range(20)))
    return {'schema':'h3-live-phase-science-contract-v1','trajectory_id':run,'case':'short_0358','method':method,
            'output_dir':ROOT+'/audit/live_phase','seed':2026101701,'valid_frames':105,'frames':107,
            'target_shapes':[[1,24,32,46,82],[1,32,2,178]],'steps':[9,19],'layer':25,'heads':56,'probes':8,
            'sigmas_video':[fp32(x) for x in original['9']['inputs']['sigmas'].split(',')],
            'noise_tensor_sha256':NOISE_TENSOR_SHA,'noise_file_sha256':NOISE_SHA,
            'cache_manifest_sha256':CACHE_SHA,'model_checkpoint_sha256':MODEL_SHA,
            'calibration_plan_sha256':PLAN_SHA,'router':route,'actual_new_video_binding_required':True}

def main():
    p=argparse.ArgumentParser();p.add_argument('--original',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    original=json.loads(Path(a.original).read_text());out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    for method in ('native','global_weak'):
        c=contract(original,method);cp=out/(method+'_contract.json');jsonsave(cp,c)
        g,d=build(original,method,ROOT+'/contracts/'+cp.name,sha(cp));gp=out/(method+'_graph.json');jsonsave(gp,g)
        d.update(original_file_sha256=sha(a.original),contract_sha256=sha(cp),graph_sha256=sha(gp));jsonsave(out/(method+'_GRAPH_DIFF.json'),d)
if __name__=='__main__':main()
