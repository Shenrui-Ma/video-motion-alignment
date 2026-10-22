"""Reuse existing MF entry; add the already-approved exact peer accounting."""
from pathlib import Path
import os,json,hashlib,difflib
B=Path('/Users/researcher/DevProjects');R=Path(__file__).resolve().parents[1];OLD=B/'h3-ive-r121-mf-host41-20261020';PEER=B/'h3-ive-prompt-checks-mf-host9-20261020'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
assert not(R/'scripts').exists();(R/'scripts').mkdir();(R/'configs').mkdir()
changed={'common.py','run_batch.py','gpu_coexistence.py'}
for p in (OLD/'scripts').glob('*.py'):
 if p.name not in changed:os.link(p,R/'scripts'/p.name)
(R/'runtime').symlink_to(OLD/'runtime',target_is_directory=True)
s=(PEER/'scripts/peer_support.py').read_text();s=s.replace("{Path('/home/researcher/h3_runs'), Path('/data5/researcher/h3_runs')}","{Path('/data4/researcher/h3_runs')}").replace('1016','1004');(R/'scripts/peer_support.py').write_text(s)
s=(OLD/'scripts/gpu_coexistence.py').read_text();s=s.replace("devices = sorted({selected_gpu, *(row['gpu_uuid'] for row in owned)})","devices = sorted({selected_gpu, *(row['gpu_uuid'] for row in owned if row['classification'] != 'verified pre-existing service')})")
s=s.replace('maximum_gpus=limit,','maximum_gpus=limit, verified_preexisting_services_excluded_from_experiment_count=True,');(R/'scripts/gpu_coexistence.py').write_text(s)
s=(OLD/'scripts/common.py').read_text();s=s.replace('import capacity,gpu_coexistence\n','import capacity,gpu_coexistence,peer_support,process_identity\n',1)
needle="rows=cuda_process_rows();policy=read(ROOT/'configs/EXISTING_SERVICES.json')"
repl=needle+"\n peers=peer_support.peers(read(ROOT/'configs/RUNTIME.json')['peer_roots'],process_identity)\n assert len(peers)<=1, 'only one simultaneous H3 peer permitted'\n assert all(peer['owner']['gpu_uuid']!=gpu for peer in peers), 'selected GPU reserved by H3 peer'"
assert s.count(needle)==1;s=s.replace(needle,repl);s=s.replace('coexistence=coexistence)','coexistence=coexistence,peers=peers)')
peer_source=(PEER/'scripts/common.py').read_text();chunk=peer_source[peer_source.index('def register_peer(ident):'):peer_source.index('def validate_flex_report')];chunk=chunk.replace(" peers=peer_support.peers(read(ROOT/'configs/RUNTIME.json')['peer_roots'],process_identity)"," peers=peer_support.peers(read(ROOT/'configs/RUNTIME.json')['peer_roots'],process_identity)\n assert len(peers)<=1, 'only one simultaneous H3 peer permitted'")
s+='\n\n'+chunk;(R/'scripts/common.py').write_text(s)
s=(OLD/'scripts/run_batch.py').read_text();s=s.replace('samples=[];error=None','samples=[];error=None;registered_peers=[]').replace("   fresh=capacity.snapshot();oom_delta(baseline,fresh);save(logdir/'AT_GO.json'","   registered_peers=register_peer(ident);fresh=capacity.snapshot();oom_delta(baseline,fresh);save(logdir/'AT_GO.json'")
s=s.replace("   if ident is not None:save(logdir/'RELEASED.json',cleanup(child,ident))","   if ident is not None:\n    released=cleanup(child,ident);unregister_peer(ident,registered_peers);released['peer_registrations_removed']=True;save(logdir/'RELEASED.json',released)")
(R/'scripts/run_batch.py').write_text(s)
rt=json.loads((OLD/'configs/RUNTIME.json').read_text());rt.update(remote_root='/data4/researcher/h3_runs/ive_context_mf_20261020',peer_roots=['/data4/researcher/h3_runs/timing_ive_prompt_envelope_full_format_r123_20261020','/data4/researcher/h3_runs/timing_ive_full_context_long0161_r123_20261020'],status='CPU_ADMIN_PREPARATION_ONLY');rt['capacity_policy']=rt['capacity_policy'].replace('occupied UID1004 GPUs plus selected GPU <=2','experiment GPUs plus selected GPU <=2; exact pre-existing8189 excluded from task count, resource use retained');save(R/'configs/RUNTIME.json',rt)
os.link(OLD/'configs/EXISTING_SERVICES.json',R/'configs/EXISTING_SERVICES.json');os.link(OLD/'configs/ive_NUMERIC.json',R/'configs/ive_NUMERIC.json')
diffs=[]
for name in sorted(changed):diffs.extend(difflib.unified_diff((OLD/'scripts'/name).read_text().splitlines(True),(R/'scripts'/name).read_text().splitlines(True),fromfile='R121/'+name,tofile='context/'+name))
(R/'audit/ADMIN_DIFF.txt').write_text(''.join(diffs))
save(R/'audit/ADMIN_PREPARATION.json',{'passed':True,'status':'UNSEALED_WAITING_ACTUAL_GUIDED_INPUTS','numerical_track_score_reused':{name:sha(R/'scripts'/name) for name in ['track.py','score.py']},'unchanged_capacity_sha256':sha(R/'scripts/capacity.py'),'peer_support_reused_from':str(PEER/'scripts/peer_support.py'),'only_peer_host_uid_allowlist_changed':True,'GPU_started':False})
print(R)
