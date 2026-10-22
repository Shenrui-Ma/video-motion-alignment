from pathlib import Path
import errno,hashlib,json,os,shutil,subprocess,sys,tarfile
HERE=Path(__file__).resolve().parent;PARENT=HERE.parent
read=lambda p:json.loads(Path(p).read_text())
def write(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
rows=read(Path('/Users/researcher/DevProjects/h3-reference-origin-positive-retest-r146-20261020/TRANSFER_RECEIPT.json'))['files']+read(Path('/Users/researcher/DevProjects/h3-timing-phase-combined-r148-20261020/SAM_TRANSFER_RECEIPT.json'))
map_paths={x['target']:x['source'] for x in rows}
legacy=read(Path('/Users/researcher/DevProjects/h3-timing-oxygen-generic-retention-r141b-host9-20261020/configs/runtime.json'))
for sid,index,uuid in [('short_0252',0,'GPU-REDACTED'),('05_real_megumi_v',1,'GPU-REDACTED')]:
 src=PARENT/'cases'/sid;dst=HERE/'cases'/sid
 if dst.exists():raise FileExistsError(dst)
 dst.mkdir(parents=True)
 for name in ['scripts','extensions','configs','design','analysis','tests','inputs']:
  shutil.copytree(src/name,dst/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'),copy_function=os.link if name=='inputs' else shutil.copy2)
 (dst/'audit').mkdir();
 for name in ['root_run_batch.py','INHERITANCE.json']:shutil.copy2(src/'audit'/name,dst/'audit'/name)
 for name in ['processes','logs','input','output','temp','user']: (dst/name).mkdir()
 runtime=read(src/'configs/runtime.json');oldremote=runtime['remote_root']
 runtime.update({k:legacy[k] for k in ['host','core','python','dependencies','models','kj_nodes','uid']})
 runtime.update(remote_root='/home/researcher/h3_runs/guidance_schedule_r149_host9_20261020/cases/'+sid,
  gpu_index=index,expected_gpu_index=index,gpu_uuid=uuid,minimum_free_mib=20480,
  profile='r149_host9_shared_gpu_partial_offload_'+sid,shared_gpu=True,
  profile_scope='Four original fixed same-bin arms; same cached tensors/noise; reserve8; existing normal model manager partial CPU offload based on actual free memory')
 write(dst/'configs/runtime.json',runtime)
 cache=read(dst/'configs/CONDITION_CACHE.json')
 cache['conditioning']['file']=map_paths[cache['conditioning']['file']]
 for t in cache['tensors']:t['file']=map_paths[t['file']]
 cache['parent_root']=str(Path(cache['conditioning']['file']).parent.parent)
 write(dst/'configs/CONDITION_CACHE.json',cache)
 science=read(dst/'configs/scientific_contract.json');science['parent_noise_file']=map_paths[science['parent_noise_file']]
 write(dst/'configs/scientific_contract.json',science)
 for p in (dst/'configs/graphs').glob('*.json'):p.write_text(p.read_text().replace(oldremote,runtime['remote_root']))
 write(dst/'configs/readonly_peer.json',{'boot_id':'no-bound-host9-peer','note':'Root supplies actual exact live peers via --peer-root; other UIDs are preserved.'})
 write(dst/'configs/cgroup_policy.json',{'schema':'r149-host9-cgroup-v1-policy-v1','expected_uid':1016,'host_entry_gib':64,'host_stop_gib':40,'finite_cgroup_raw_entry_gib':46,'finite_cgroup_raw_stop_gib':20,'file_cache_credit':False,'memory_events_stop':True})
 shutil.copy2(HERE/'cgroup_memory_host9.py',dst/'scripts/cgroup_memory.py')
 p=dst/'scripts/capacity_trial.py';t=p.read_text();a=t.index('def assess(');b=t.index('\ndef signal_exact(',a);p.write_text(t[:a]+'from cgroup_memory import assess\n\n'+t[b:])
 p=dst/'scripts/execution_gate.py';t=p.read_text().replace('a["required_free_bytes"] >= 40 * 1024**3','a["required_free_bytes"] >= runtime["minimum_free_mib"] * 1024**2').replace('default=40960','default=20480').replace('args.free_mib >= 40960','args.free_mib >= read(ROOT / "configs/runtime.json")["minimum_free_mib"]').replace('40GiB resource admission required','registered host9 partial-offload headroom required');p.write_text(t)
 p=dst/'audit/root_run_batch.py';t=p.read_text().replace("'--free-mib','40960'","'--free-mib',str(read(ROOT/'configs/runtime.json')['minimum_free_mib'])");p.write_text(t)
 p=dst/'scripts/r132_contract.py';t=p.read_text().replace('        os.link(source, target)','        try: os.link(source, target)\n        except OSError as error:\n            import errno, shutil\n            if error.errno != errno.EXDEV: raise\n            shutil.copy2(source, target)');p.write_text(t)
 inherited=read(dst/'audit/INHERITANCE.json');inherited['host9_fallback']={'parent_seal_sha256':hashlib.sha256((src/'deploy_manifest.json').read_bytes()).hexdigest(),'changes':'host/runtime, cgroup-v1 host-RAM monitor, GPU20GiB partial-offload admission, cache path mapping; science tensors and kernels unchanged'};write(dst/'audit/INHERITANCE.json',inherited)
 # Verify the exact scientific changes consist only of storage paths.
 orig=read(src/'configs/scientific_contract.json');assert {k for k in orig if orig[k]!=science[k]}=={'parent_noise_file'}
 for p in (src/'configs/graphs').glob('*.json'):assert p.read_text().replace(oldremote,runtime['remote_root'])==(dst/'configs/graphs'/p.name).read_text()
 for p in (src/'extensions').rglob('*.py'):assert p.read_bytes()==(dst/p.relative_to(src)).read_bytes()
 env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
 subprocess.run([sys.executable,str(dst/'scripts/preflight.py')],check=True,env=env,stdout=subprocess.DEVNULL)
 subprocess.run([sys.executable,str(dst/'scripts/execution_gate.py'),'seal'],check=True,env=env)
 print(sid, 'prepared',runtime['remote_root'])
