import json,re
from pathlib import Path
try:
    from .observer import LiveObservation
    from .noise import H3HistoricalNoise
    from .reconstruct import file_sha
except ImportError:
    from observer import LiveObservation
    from noise import H3HistoricalNoise
    from reconstruct import file_sha

def validate_contract(s):
    if s['case']!='short_0358' or s['method'] not in ('native','global_weak'):raise ValueError('first live pair is drinking native/full weak only')
    if s['seed']!=2026101701 or s['valid_frames']!=105 or s['frames']!=107 or s['target_shapes']!=[[1,24,32,46,82],[1,32,2,178]]:raise ValueError('frozen full geometry/seed differs')
    if s['steps']!=[9,19] or s['layer']!=25 or s['heads']!=56 or s['probes']!=8:raise ValueError('observation protocol differs')
    if not re.fullmatch(r'[a-z0-9_]+',s['trajectory_id']) or not Path(s['output_dir']).is_absolute():raise ValueError('safe isolated output required')
    r=s['router'];mode,alpha,steps=('native',1.,list(range(6,15))) if s['method']=='native' else ('mass_preserve',.25,list(range(20)))
    expected={'mode':mode,'alpha':alpha,'active_steps':steps,'radius':0,'time_offset':0,'start_frame':0,'end_frame':104,'block_start':0,'block_end':50}
    if r!=expected:raise ValueError('frozen control configuration differs')
    expected_assets={'cache_manifest_sha256':'ad361d036ee933cc0a72ad549ce384c883f0025922d3ee5c586370029be963f2','model_checkpoint_sha256':'9255f52b6677845ad238f20dfaafa94727053694127ab7f255c048f0f9365779','noise_file_sha256':'5439f8f84b471b7d53e431b886c730fc7e78492b159ce7658e08a2bad046b310','noise_tensor_sha256':'564dd8a5d999279ffed272b8df53211610648f4e985d53e29feab5f94118eda8','calibration_plan_sha256':'d0a3b95f861b0392b1dcef2cdb7122209758a5d80f3130ae3e50fc1841b90d78'}
    if any(s.get(k)!=v for k,v in expected_assets.items()):raise ValueError('frozen science asset identity differs')
    if s['trajectory_id']!='live_phase_short0358_'+s['method']+'_20261023' or s['output_dir']!='/data/research-user/h3_inference_20261023/live_phase_pair_20261023/audit/live_phase':raise ValueError('isolated trajectory destination differs')
    from struct import pack,unpack
    original='1,0.995633187773,0.990825688073,0.985507246377,0.979591836735,0.972972972973,0.965517241379,0.957055214724,0.947368421053,0.936170212766,0.923076923077,0.90756302521,0.888888888889,0.865979381443,0.837209302326,0.8,0.75,0.679245283019,0.571428571429,0.387096774194,0'
    if s['sigmas_video']!=[unpack('f',pack('f',float(x)))[0] for x in original.split(',')]:raise ValueError('frozen sigma schedule differs')

class H3LivePhaseObservation:
    @classmethod
    def INPUT_TYPES(cls):return {'required':{'model':('MODEL',),'observation_contract':('STRING',),'contract_sha256':('STRING',)}}
    RETURN_TYPES=('MODEL',);FUNCTION='apply';CATEGORY='research/H3PassiveObservation'
    def apply(self,model,observation_contract,contract_sha256):
        from comfy.patcher_extension import WrappersMP
        if file_sha(observation_contract)!=contract_sha256:raise ValueError('contract file changed')
        spec=json.loads(Path(observation_contract).read_text());validate_contract(spec)
        c=model.clone();c.add_wrapper_with_key(WrappersMP.SAMPLER_SAMPLE,'H3LivePhaseObservation',LiveObservation(spec,contract_sha256));return (c,)

NODE_CLASS_MAPPINGS={'H3LivePhaseObservation':H3LivePhaseObservation,'H3HistoricalNoise':H3HistoricalNoise}
