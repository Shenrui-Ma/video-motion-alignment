"""CPU-only official MF with frozen input domains and explicit historical cache provenance."""
import argparse,sys,os,time
from common import *
os.environ['CUDA_VISIBLE_DEVICES']=''
def checked(c,role):
 m=read(c/'INPUTS.json');folder=folder_for(c,role);r=read(folder/'REPORT.json');assert r['passed']
 ext='tracks.pt'if m['benchmark']=='FlexiAct'else'tracks.npz';assert sha(folder/ext)==r['tracks_sha256']
 if role=='source'and m['source_cache']:assert sha(folder/'REPORT.json')==m['source_cache']['report_sha256']and r['tracks_sha256']==m['source_cache']['tracks_sha256']
 else:
  b=read(folder/'INPUT_BINDING.json');assert b['case_input']['sha256']==sha(c/'INPUTS.json')and b['seal']['sha256']==sha(ROOT/'SEAL.json')and b['report']['sha256']==sha(folder/'REPORT.json')
 return folder,r

def run(name,role):
 verify_seal();c=case(name);m=validate_case(c,role);t=next(x for x in m['targets']if x['role']==role);sf,s=checked(c,'source');tf,z=checked(c,role)
 if m['benchmark']=='IVEBench':
  sys.path.insert(0,str(ROOT/'runtime/ive/metric_runtime'));import score_cached_tracks as score
  score.SELECTION_SHA=m['selection_sha256'];record=score.score(sf,tf)
  assert s['source_prepared_sha256']==m['source_full_sha256']and s['source_score_sha256']==m['source_score_sha256'];assert z['score_video']['sha256']==t['score_sha256']
 else:
  sys.path.insert(0,str(ROOT/'runtime/flex'));import torch
  torch.set_num_threads(2);from metric_adapter import score_tracks
  validate_flex_report(s,m,'source');validate_flex_report(z,m,role,t)
  a=torch.load(sf/'tracks.pt',map_location='cpu',weights_only=True)['tracks'];b=torch.load(tf/'tracks.pt',map_location='cpu',weights_only=True)['tracks'];assert a.shape==b.shape==(3025,49,2)and torch.isfinite(a).all()and torch.isfinite(b).all()
  tick=time.monotonic();record,matrix=score_tracks(b,a);record.update(score_seconds=time.monotonic()-tick,cuda_initialized=torch.cuda.is_initialized());del matrix
 record.update(benchmark=m['benchmark'],case=name,role=role,inventory_bindings=t['inventory_bindings'],actual_generated_video_sha256=t['full_sha256'],source_full_sha256=m['source_full_sha256'],source_score_sha256=m['source_score_sha256'],valid_frames=m['valid_frames'],evaluation_frames=m['evaluation_frames'],evaluation_fps=m['evaluation_fps'],case_input=bound(c/'INPUTS.json'),source_report=bound(sf/'REPORT.json'),target_report=bound(tf/'REPORT.json'),source_cache_reused=bool(m['source_cache']),runtime_provenance={'source':{k:s.get(k)for k in ['torch_version','cuda_version','admission_before_cuda']},'target':{k:z.get(k)for k in ['torch_version','cuda_version','admission_before_cuda']}},official_numerics_unchanged=True)
 assert record['cuda_initialized']is False
 out=ROOT/'results'/name/(role+'.json');assert not out.exists();save(out,record);print(json.dumps({'case':name,'role':role,'score':record.get('score',record.get('motion_fidelity'))}));return record
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--role',required=True);a=p.parse_args();run(a.case,a.role)
