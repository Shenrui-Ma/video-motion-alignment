"""Reuse exact numerical evidence while requiring new root resource admission."""
import json,subprocess,sys,hashlib
from pathlib import Path
from retry_inheritance import check as check_inheritance,specification,inherited_file
from recovery_contract import read,sha,require

def check_engineering_revision(root):
 root=Path(root);check_inheritance(root,inputs=False)
 spec=read(root/'configs/engineering_revision_v2.json')
 for rel,digest in spec['unchanged_scientific_files'].items():inherited_file(root,rel,digest)
 from observer_import import t
 profile=t.decoder_memory_profile();p=read(root/'configs/protocol.json')
 require(p['resources']['decoder_memory_profile_sha256']==profile['profile_sha256'],'decoder measured profile differs')
 return spec

def check(root):
 root=Path(root);check_engineering_revision(root);spec,base,_=specification(root)
 for name in ('known_endpoint_158_split_gate.json','resource_admission_v2.json'):
  require(sha(base/'audit'/name)==sha(root/'configs/recovery'/name),'inherited actual gate changed: '+name)
 # Run the previous gate in a separate interpreter with its original module paths.
 # The returned GPU evidence remains labelled as inherited, not as new GPU work.
 code='import json;from pathlib import Path;from prelaunch_gates import check;print(json.dumps(check(Path('+repr(str(base))+'))))'
 result=subprocess.run([sys.executable,'-c',code],cwd=base/'scripts',capture_output=True,text=True,timeout=180,check=True)
 inherited=json.loads(result.stdout)
 review=read(root/'audit/ROOT_RECOVERY_APPROVAL.json')
 require(review['root_approved'] is True and review['producer_manifest_sha256']==sha(root/'deploy_manifest.json'),'new root recovery approval missing/stale')
 require(review['protocol_sha256']==sha(root/'configs/protocol.json') and review['scope']=='four_new_cases_external_chest_fixed5','recovery resource approval scope differs')
 require(review['main_required_free_bytes']==read(root/'configs/main_memory_profile.json')['required_free_bytes'],'main memory bound changed')
 return {'inherited_numerical_GPU_gates':inherited,'previous_root':str(base),'new_GPU_numerical_gate_executed':False,'new_root_approval_sha256':sha(root/'audit/ROOT_RECOVERY_APPROVAL.json'),'actual_resource_checks_repeated_at_service_start':True}

def check_layout_cases(k, root):
    actual=[v for v in k['cases'] if v['actual_shape']]
    cases=read(root/'configs/protocol.json')['cases']
    require([v.get('case_run') for v in actual]==[c['run_id'] for c in cases],'all five actual layout gates required')
    for a,case in zip(actual,cases):
        condition=read(root/case['parent_conditioning'])
        segments=condition['packed_layout']['segments'];n=condition['packed_layout']['seq_len']
        target=[s for s in segments if s[2]=='video'];ref=[s for s in segments if s[2]=='ref_img' and s[1]-s[0]==47*864]
        require(len(target)==len(ref)==1,'ambiguous actual reference/target layout')
        expected={'seq_len':n,'frame_rows':864,'latent_interval_half_open':[0,47],'query_interval_half_open':target[0][:2],'reference_video_segment':ref[0][:2]}
        require(a['shape']==[1,56,n,128] and a['plan']==expected,'new actual kernel layout differs')
    require(all(v['passed'] and all(v['checks'].values()) for v in k['cases']),'partial kernel failure')
