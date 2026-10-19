from pathlib import Path
import json,hashlib,shutil,difflib
C=Path(__file__).resolve().parent
snap=json.loads((C/'SOURCE_SNAPSHOTS.json').read_text());src=Path(snap['r50']['source_root']);base=C/'r50/before';out=C/'r50/overlay'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for rel in ('scripts/service.py','scripts/prelaunch_gates.py','scripts/known_endpoint_158_gate.py'):
 if not(src/rel).exists():continue
 p=base/rel;p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():shutil.copyfile(src/rel,p)
 snap['r50']['files'][rel]={'before_sha256':sha(p)}
(C/'SOURCE_SNAPSHOTS.json').write_text(json.dumps(snap,indent=2)+'\n')
p=base/'extensions/H3AutomaticWindowRouter/transport.py';s=p.read_text()
a=s.index('def validate_separate_decoder(');b=s.index('def record_resource_event(',a)
s=s[:a]+(C/'fragments/memory_profile.py').read_text()+s[b:]
s=s.replace('0<execution_timeout<=180','0<execution_timeout<=780')
s=s.replace("if proc.returncode:raise RuntimeError(label+' exit '+str(proc.returncode)+'; see '+str(log))", "if proc.returncode:raise ChildExitError(label+' exit '+str(proc.returncode)+'; see '+str(log),{'process':entry,'wall_seconds':time.monotonic()-start,'returncode':proc.returncode,'execution_start':execution_start})")
s=s.replace("require(admission['memory_free_mib']>=45000 and admission['memory_used_mib']<=1024 and admission['utilization_percent']==0,'response decoder admission invalid')", "profile=decoder_memory_profile()\n require(admission['memory_profile_sha256']==profile['profile_sha256'] and admission['required_free_bytes']==profile['required_free_bytes'] and admission['memory_free_mib']*1024**2>=profile['required_free_bytes'],'response decoder memory admission invalid')")
(out/p.relative_to(base)).write_text(s)
(out/'scripts/run_observer.py').write_text((C/'fragments/run_observer.py').read_text())
p=base/'scripts/decode_live_child.py';s=p.read_text();a=s.index('def assert_idle_gpu(');b=s.index('\ndef load_snapshot(',a)
s=s[:a]+'''def assert_idle_gpu(uuid):
    # Retained interface for standalone bridge; admission now uses actual free
    # memory and the own-user card cap, while foreign users may coexist.
    return t.standalone_decoder_admission(uuid)

'''+s[b:]
s=s.replace("t.require(args.output.resolve()==args.request.parent.resolve()/'native.mp4','Unexpected output path')", """global ATTEMPT_DIRECTORY
    ATTEMPT_DIRECTORY=args.request.parent.resolve()
    attempt=os.environ.get('H3_DECODER_ATTEMPT_DIRECTORY')
    if attempt is not None:
        import re
        ATTEMPT_DIRECTORY=t.inside(attempt,t.ROOT/'audit/observations')
        t.require(ATTEMPT_DIRECTORY.parent==args.request.parent.resolve() and re.fullmatch(r'decoder_attempt00[1-3]',ATTEMPT_DIRECTORY.name),'Unexpected decoder attempt directory')
    t.require(args.output.resolve()==ATTEMPT_DIRECTORY/'native.mp4','Unexpected output path')""")
s=s.replace("t.require(args.gpu_uuid==t.DECODER_UUID and args.expected_vae_sha256==frozen['vae_sha256'],'Decoder GPU/model differs')", """t.require(args.gpu_uuid==t.DECODER_UUID and args.expected_vae_sha256==frozen['vae_sha256'],'Decoder GPU/model differs')
    profile=t.decoder_memory_profile(bootstrap=ATTEMPT_DIRECTORY.name.startswith('known_endpoint_'))
    t.require(profile['geometry']==REQUEST['geometry'] and profile['vae_sha256']==frozen['vae_sha256'],'Decoder profile geometry/model differs')""")
s=s.replace("args.request.parent/'decoder_admission.jsonl'", "ATTEMPT_DIRECTORY/'decoder_admission.jsonl'")
s=s.replace("marker==args.request.parent.resolve()/'decoder_cuda_started.json'", "marker==ATTEMPT_DIRECTORY/'decoder_cuda_started.json'")
s=s.replace('REQUEST_SHA = None','REQUEST_SHA = None\nATTEMPT_DIRECTORY = None')
s=s.replace('    raise SystemExit(main())', '''    try:
        raise SystemExit(main())
    except BaseException as error:
        torch_module=sys.modules.get('torch')
        oom_type=getattr(getattr(torch_module,'cuda',None),'OutOfMemoryError',None)
        chain=t.typed_cuda_oom(error,oom_type)
        if chain is not None and REQUEST is not None and ATTEMPT_DIRECTORY is not None:
            t.write_new(ATTEMPT_DIRECTORY/'decoder_oom.json',{'schema':'h3-typed-cuda-oom-v4','typed_cuda_oom':True,'exception_chain':chain,'identity':t.identity(os.getpid()),'request_sha256':REQUEST_SHA,**{key:REQUEST[key] for key in ('endpoint_file_sha256','seed','geometry')}})
            raise SystemExit(t.CUDA_OOM_EXIT) from error
        raise''')
(out/p.relative_to(base)).write_text(s)
p=base/'scripts/gpu_release_gate.py';s=p.read_text().replace("compute_pids=None,audit_path=None):", "compute_pids=None,audit_path=None,allow_cuda_oom=False):")
pos=s.index('def wait_own_child_released(')
s=s[:pos]+s[pos:].replace("if child['returncode']!=0:raise RuntimeError('decoder did not exit successfully')", "if child['returncode']!=0 and not (allow_cuda_oom and child['returncode']==86):raise RuntimeError('decoder exit is neither success nor verified CUDA OOM')",1)
(out/p.relative_to(base)).write_text(s)
p=base/'scripts/service.py';s=p.read_text();a=s.index('def check_admission(');b=s.index('def command(',a)
s=s[:a]+(C/'fragments/service_admission.py').read_text()+s[b:]
s=s.replace('        check_admission(admission, processes, queue)\n        memory =', '        check_admission(admission, processes, queue)\n        hardware = gpu_readiness(admission,queue)\n        memory =')
s=s.replace('capture_output=True, text=True, check=True).stdout','capture_output=True, text=True, check=True, timeout=10).stdout')
s=s.replace("'host_available_kib': available_kib, 'admission': admission,", "'host_available_kib': available_kib, 'admission': admission, 'gpu_readiness':hardware,")
(out/p.relative_to(base)).write_text(s)
p=base/'scripts/prelaunch_gates.py';s=p.read_text()
s=s.replace("    require(current['resources']['decoder_idle_min_free_MiB']>=45000 and current['resources']['decoder_idle_max_used_MiB']<=1024,'decoder admission weakened')", "    from observer_import import t\n    profile=t.decoder_memory_profile()\n    require(current['resources']['decoder_memory_profile_sha256']==profile['profile_sha256'] and current['resources']['decoder_required_free_MiB']*1024**2>=profile['required_free_bytes'],'decoder measured memory admission differs')")
s=s.replace("    require(r['required_free_before_decoder_mib']>=45000,'dedicated decoder headroom weakened')", "    from observer_import import t\n    profile=t.decoder_memory_profile()\n    require(r['decoder_memory_profile_sha256']==profile['profile_sha256'] and r['required_free_before_decoder_mib']*1024**2>=profile['required_free_bytes'],'dedicated decoder measured headroom differs')")
(out/p.relative_to(base)).write_text(s)
p=base/'scripts/known_endpoint_158_gate.py';s=p.read_text().replace('from gpu_release_gate import wait_after_child','from gpu_release_gate import wait_own_child_released').replace("wait_after_child(t.DECODER_UUID,record['decoder'],live.assert_idle_gpu,t.identity)","wait_own_child_released(t.DECODER_UUID,record['decoder'],t.identity)")
(out/p.relative_to(base)).write_text(s)
evidence=Path('/Users/researcher/DevProjects/h3-timing-flexiact-auto-r50-20261017/analysis/postrun/captured_failure/step006_release/audit/resource_admission_v2.json')
dest=out/'configs/main_memory_evidence/resource_admission_v2.json';dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(evidence,dest)
profile={'schema':'h3-main-memory-profile-v4','status':'MEASURED_BOUND','required_free_bytes':77968965632,'evidence_file':str(dest.relative_to(out)),'evidence_sha256':sha(dest),'scope':'Actual Native sampled peak plus measured routing upper bound plus1GiB; main service startup only'}
(out/'configs/main_memory_profile.json').write_text(json.dumps(profile,indent=2)+'\n')
patch=[]
for rel in snap['r50']['files']:
 patch.extend(difflib.unified_diff((base/rel).read_text().splitlines(True),(out/rel).read_text().splitlines(True),fromfile='a/'+rel,tofile='b/'+rel))
(C/'r50/candidate.patch').write_text(''.join(patch))
