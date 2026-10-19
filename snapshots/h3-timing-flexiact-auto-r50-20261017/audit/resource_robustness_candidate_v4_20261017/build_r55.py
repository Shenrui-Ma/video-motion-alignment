from pathlib import Path
import json,hashlib,shutil,difflib
C=Path(__file__).resolve().parent;snap=json.loads((C/'SOURCE_SNAPSHOTS.json').read_text());src=Path(snap['r55']['source_root']);base=C/'r55/before';out=C/'r55/overlay'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for rel in ('scripts/service.py','scripts/known_endpoint_90_gate.py','scripts/prelaunch_gates.py'):
 p=base/rel;p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():shutil.copyfile(src/rel,p)
 snap['r55']['files'][rel]={'before_sha256':sha(p)}
(C/'SOURCE_SNAPSHOTS.json').write_text(json.dumps(snap,indent=2)+'\n')
p=base/'extensions/H3AutomaticWindowRouter/transport.py';s=p.read_text();a=s.index('def validate_separate_decoder(');b=s.index('def record_resource_event(',a)
s=s[:a]+(C/'fragments/memory_profile.py').read_text()+s[b:]
s=s.replace('0<execution_timeout<=180','0<execution_timeout<=780')
s=s.replace("if proc.returncode:raise RuntimeError(label+' exit '+str(proc.returncode)+'; see '+str(log))", "if proc.returncode:raise ChildExitError(label+' exit '+str(proc.returncode)+'; see '+str(log),{'process':entry,'wall_seconds':time.monotonic()-start,'returncode':proc.returncode,'execution_start':execution_start})")
s=s.replace("require(admission['memory_free_mib']>=45000 and admission['memory_used_mib']<=1024 and admission['utilization_percent']==0,'response decoder admission invalid')", "profile=decoder_memory_profile()\n require(admission['memory_profile_sha256']==profile['profile_sha256'] and admission['required_free_bytes']==profile['required_free_bytes'] and admission['memory_free_mib']*1024**2>=profile['required_free_bytes'],'response decoder memory admission invalid')")
(out/p.relative_to(base)).write_text(s)
for rel in ('scripts/run_observer.py','scripts/decode_live_child.py','scripts/gpu_release_gate.py'):shutil.copyfile(C/'r50/overlay'/rel,out/rel)
p=base/'scripts/service.py';s=p.read_text();a=s.index('def check_admission(');b=s.index('def command(',a)
fragment=(C/'fragments/service_admission.py').read_text().replace("r['main_native_peak_sampled_bytes']", "r['main_native_peak_reserved_bytes']")
s=s[:a]+fragment+s[b:]
s=s.replace('hardware = gpu_readiness()',"hardware = gpu_readiness(admission,queue_at(admission.get('existing_comfy_port',8189)))")
s=s.replace('capture_output=True, text=True, check=True).stdout','capture_output=True, text=True, check=True, timeout=10).stdout')
(out/p.relative_to(base)).write_text(s)
p=base/'scripts/known_endpoint_90_gate.py';s=p.read_text().replace('from gpu_release_gate import wait_after_child','from gpu_release_gate import wait_own_child_released').replace("wait_after_child(t.DECODER_UUID,record['decoder'],live.assert_idle_gpu,t.identity)","wait_own_child_released(t.DECODER_UUID,record['decoder'],t.identity)")
s=s.replace("    path=directory/'request.json';request_sha=t.write_new(path,request)", """    path=directory/'request.json';request_sha=t.write_new(path,request)
    # Preserve the exact bootstrap bindings before measured profile publication.
    # Source/protocol remain fixed; formal bindings subsequently incorporate the
    # measured gate/profile without rewriting this archived request.
    bootstrap_bindings=directory/'bootstrap_observer_bindings.json'
    bootstrap_profile=directory/'bootstrap_decoder_memory_profile.json'
    for source,destination in ((ROOT/'configs/observer_bindings.json',bootstrap_bindings),(ROOT/'configs/decoder_memory_profile.json',bootstrap_profile)):
        with destination.open('xb') as handle:handle.write(source.read_bytes());handle.flush();os.fsync(handle.fileno())
    t.require(t.sha(bootstrap_bindings)==request['bindings_sha256'],'bootstrap binding snapshot differs')""")
s=s.replace("'request_sha256':request_sha,'GPU_admission':admission,", "'request_sha256':request_sha,'GPU_admission':admission,\n            'bootstrap_bindings':{'file':str(bootstrap_bindings),'sha256':t.sha(bootstrap_bindings),'original_sha256':request['bindings_sha256']},\n            'bootstrap_memory_profile':{'file':str(bootstrap_profile),'sha256':t.sha(bootstrap_profile)},")
(out/p.relative_to(base)).write_text(s)
(out/'configs/main_memory_profile.json').write_text(json.dumps({'schema':'h3-main-memory-profile-v4','status':'PENDING','required_free_bytes':None,'evidence_file':None,'evidence_sha256':None,'scope':'Root must bind actual27-bin routing/residency capacity and reserve-vram choice before formal service startup'},indent=2)+'\n')
p=base/'scripts/prelaunch_gates.py';s=p.read_text()
s=s.replace(" k,d,r=read(kp),read(dp),read(rp)", " k,d,r=read(kp),read(dp),read(rp)\n from observer_import import t\n profile=t.decoder_memory_profile()\n require(profile['evidence_sha256']==sha(dp) and profile['peak_reserved_bytes']==d['decode']['max_memory_reserved_bytes'],'formal decoder profile differs from actual full90 gate')")
(out/p.relative_to(base)).write_text(s)
patch=[]
for rel in snap['r55']['files']:
 patch.extend(difflib.unified_diff((base/rel).read_text().splitlines(True),(out/rel).read_text().splitlines(True),fromfile='a/'+rel,tofile='b/'+rel))
(C/'r55/candidate.patch').write_text(''.join(patch))
