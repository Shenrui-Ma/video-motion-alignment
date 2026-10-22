from pathlib import Path
import time,importlib.util,tempfile,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from common import read,write,bound,ROOT
now=time.time();record=read(ROOT/'audit/MIXED_HOST_BINDING_CURRENT.json')
record['bindings']={sid:[bound(p) for p in sorted((ROOT/'runtime'/sid).glob('*.json'))] for sid in ['short_0252','05_real_megumi_v','short_0358']}
record['updated_unix']=now;write(ROOT/'audit/MIXED_HOST_BINDING_CURRENT.json',record)
previous=read(ROOT/'audit/hardware_recovery_before/audit/MIXED_HOST_BINDING_CURRENT.json')
old={Path(x['file']).relative_to(ROOT).as_posix():x['sha256'] for rows in previous['bindings'].values() for x in rows}
preserved=['runtime/05_real_megumi_v/'+a+'.json' for a in ['early','late','split']]+['runtime/short_0358/'+a+'.json' for a in ['early','late']]
assert all(bound(ROOT/x)['sha256']==old[x] for x in preserved)
write(ROOT/'audit/hardware_recovery/BINDING_UPDATE.json',{'passed':True,'unchanged_roles':[bound(ROOT/x) for x in preserved],'sam_global':bound(ROOT/'runtime/05_real_megumi_v/global_weak.json'),'drink_recovery':[bound(ROOT/'runtime/short_0358'/f'{a}.json') for a in ['split','global_weak']],'current':bound(ROOT/'audit/MIXED_HOST_BINDING_CURRENT.json'),'old_versions_archived':True,'completed_new_outputs':0,'GPU_launched':False,'created_unix':now})
gpu='GPU-REDACTED'
raw='GPU-REDACTED, [N/A], [N/A]\nGPU-REDACTED, [N/A], [N/A]\n'+gpu+', 12345, 7000\n'
checks=[]
for sid in ['short_0252','05_real_megumi_v','short_0358']:
 p=ROOT/'mf_preparation/batches'/sid/'scripts/gpu_query.py'
 spec=importlib.util.spec_from_file_location('query',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 with tempfile.TemporaryDirectory(dir=ROOT/'audit') as t:
  rows=m.parse_and_record(t,gpu,raw);audit=read(Path(t)/'audit/GPU_QUARANTINE_LATEST.json')
  assert rows==[{'gpu_uuid':gpu,'pid':12345,'used_memory_mib':7000}]
  assert len(audit['excluded'])==2 and all(x['release_confirmed'] is False for x in audit['excluded'])
 for invalid in [gpu+', [N/A], [N/A]',gpu+', 123, [N/A]',gpu+', [N/A], 23','broken row']:
  try:m.parse_compute(invalid,gpu)
  except ValueError:pass
  else:raise AssertionError('accepted invalid selected GPU telemetry')
 checks.append({'case':sid,'parser':bound(p),'passed':True,'known_non_target_double_NA_rows':2,'selected_GPU_unknown_or_partial_NA_rejected':True,'excluded_release_confirmed':False})
write(ROOT/'audit/hardware_recovery/MF_GPU_PARSER_CPU_CHECK.json',{'passed':True,'selected_gpu_fixture':gpu,'checks':checks,'common_path':'scripts/common.py:cuda_process_rows -> gpu_query.parse_and_record','entry_and_release_use_same_parser':True,'actual_GPU_query_performed':False,'new_GPU_execution':False,'numeric_or_execution_files_changed':False,'notes':'Inherited R148 parser records non-target exact UUID double-N/A as release_confirmed=false; selected GPU remains strict. Final runtime GPU is root-selected at finalize; current draft gpu=null.','created_unix':now})
mf=read(ROOT/'mf_preparation/HANDOFF.json');mf['producer_bindings']=bound(ROOT/'audit/MIXED_HOST_BINDING_CURRENT.json');mf['updated_unix']=now
mf['composite_release_support']={'verifier':bound(ROOT/'finalize_composite.py'),'hardware_prefix':bound(ROOT/'hardware_prefix.py'),'partitions':{'05_real_megumi_v':'3+1 normal planned-stop CUDA released','short_0358':'2+2 hardware prefix CUDA unknown; target normal CUDA released'},'actual_composite_finalized':False}
mf['gpu_parser_CPU_check']=bound(ROOT/'audit/hardware_recovery/MF_GPU_PARSER_CPU_CHECK.json');write(ROOT/'mf_preparation/HANDOFF.json',mf)
print('Bindings, preservation proof and inherited GPU parser CPU checks saved. No GPU or network.')
