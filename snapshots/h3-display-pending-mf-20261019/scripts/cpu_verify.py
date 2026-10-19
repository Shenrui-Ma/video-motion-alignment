"""Validate sealed bytes, exact input domains and frozen caches without model allocation."""
from common import *
import importlib.util,time

def main():
 verify_seal();plan=read(ROOT/'configs/PLAN.json');seen=set();n=0;caches=[]
 for key in plan['groups']:
  c=case(key);m=validate_case(c,'source',False);assert 1<=m['valid_frames']<=147
  if m['benchmark']=='IVEBench':assert m['valid_frames']<=145 and m['evaluation_fps']==24
  else:assert m['valid_frames']==147 and m['evaluation_frames']==49 and m['evaluation_fps']==8
  for t in m['targets']:
   validate_case(c,t['role'],False);unique=(m['benchmark'],m['source_score_sha256'],t['full_sha256'],tuple(t['evaluation_indices']));assert unique not in seen;seen.add(unique);n+=1
   assert t['evaluation_indices']==(list(range(0,147,3))if m['benchmark']=='FlexiAct'else list(range(m['valid_frames'])))
  if m['source_cache']:
   rp=c/'tracks/source/REPORT.json';r=read(rp);ext='tracks.pt'if m['benchmark']=='FlexiAct'else'tracks.npz';assert sha(rp)==m['source_cache']['report_sha256'];assert sha(c/'tracks/source'/ext)==m['source_cache']['tracks_sha256']==r['tracks_sha256']
   if m['benchmark']=='FlexiAct':validate_flex_report(r,m,'source')
   else:
    assert r['official_commit']=='2dcf8900ee65197f43854c76f61c66a32bb8dbfc'and r['checkpoint_sha256']=='da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df'
    assert r['effective_frame_count']==m['valid_frames']and r['decoded_frame_md5']==m['source_frame_md5']and r['source_score_sha256']==m['source_score_sha256']and r['source_prepared_sha256']==m['source_full_sha256']and r['selection_sha256']==m['selection_sha256']
   caches.append(key)
 for family in ('ive','flex'):
  for rel,h in read(ROOT/'configs'/f'{family}_NUMERIC.json')['files'].items():assert sha(ROOT/'runtime'/family/rel)==h
 assert n==plan['unique_targets']==34;assert len(caches)==plan['source_cache_count']==6
 import track,run_batch,score
 assert 'torch'not in sys.modules,'CPU validation unexpectedly imported model runtime'
 result=dict(passed=True,seal_sha256=sha(ROOT/'SEAL.json'),source_domains=len(plan['groups']),unique_targets=n,cached_sources=caches,new_trackers=len(plan['jobs']),scientific_numerics_unchanged=True,CUDA_started=False,unix=time.time());save(ROOT/'audit/CPU_VERIFIED.json',result);print(json.dumps(result))
if __name__=='__main__':main()
