"""Read-only isolation and pair-identity gate; does not import torch."""
from pathlib import Path
import hashlib,json
ROOT='/data/research-user/h3_inference_20261023/live_phase_pair_20261023'
EXPECTED={'UNETLoader','VAELoader','MiniMaxH3SigmaShift','KSamplerSelect','ManualSigmas','SamplerCustomAdvanced','VAEDecode','VAEDecodeAudio','CreateVideo','SaveVideo','H3TrustedConditionCache','H3HistoricalNoise','H3StudySchedule','H3LivePhaseObservation','BasicGuider'}
def verify(graph,contract,method,contract_bytes):
 assert contract['method']==method and contract['trajectory_id']=='live_phase_short0358_'+method+'_20261023'
 assert contract['output_dir']==ROOT+'/audit/live_phase'
 assert contract['steps']==[9,19] and contract['layer']==25
 assert contract['frames']==107 and contract['valid_frames']==105
 assert contract['actual_new_video_binding_required'] is True
 assert set(n['class_type'] for n in graph.values())==EXPECTED
 assert sum(n['class_type']=='SamplerCustomAdvanced' for n in graph.values())==1
 assert graph['52']['inputs']=={'model':['50',0],'observation_contract':ROOT+'/contracts/'+method+'_contract.json','contract_sha256':hashlib.sha256(contract_bytes).hexdigest()}
 assert graph['50']['inputs']['audit_dir']==ROOT+'/audit/router'
 assert graph['50']['inputs']['run_id']==contract['trajectory_id']
 assert graph['14']['inputs']['filename_prefix']==contract['trajectory_id']+'/'+contract['trajectory_id']
 assert graph['11']['inputs']['samples']==['10',0] and graph['12']['inputs']['samples']==['10',0]
 assert graph['7']['inputs']['model']==['52',0] and graph['10']['inputs']['guider']==['7',0]
 assert graph['5']['inputs']['manifest_sha256']==contract['cache_manifest_sha256']
 assert graph['6']['inputs']['noise_sha256']==contract['noise_file_sha256']
 assert graph['6']['inputs']['seed']==contract['seed']==2026101701
 r=graph['50']['inputs'];assert (r['mode'],r['alpha'],r['schedule'])==(('native',1.0,'fixed') if method=='native' else ('mass_preserve',.25,'global_weak'))
 assert len(graph['9']['inputs']['sigmas'].split(','))==21
 return True

def main():
 d=Path(__file__).parent;e=d.parents[1];p=e/'innovation/signed_phase_calibration_20261023/replay_live_pair/plans';rows={};graphs={}
 for method in ['native','global_weak']:
  cb=(p/(method+'_contract.json')).read_bytes();gb=(p/(method+'_graph.json')).read_bytes();g=json.loads(gb);c=json.loads(cb);verify(g,c,method,cb);graphs[method]=g
  rows[method]={'graph_sha256':hashlib.sha256(gb).hexdigest(),'contract_sha256':hashlib.sha256(cb).hexdigest(),'passed':True}
 for node in ['1','3','4','41','8','9','10','11','12','13','5','6','7']:
  assert graphs['native'][node]==graphs['global_weak'][node],node
 out={'schema':'h3-live-pair-runtime-path-check-v1','status':'prepared_not_submitted','cohort':'phase_calibration_pair','separate_from_main10_and_innovation':True,'rows':rows,'identical_science_nodes':['1','3','4','41','8','9','10','11','12','13','5','6','7'],'passed':True}
 (d/'PLANS_CHECK.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
if __name__=='__main__':main()
