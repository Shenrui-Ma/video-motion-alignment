from pathlib import Path
import ast,hashlib,json,shutil
R=Path(__file__).resolve().parents[1]
C=Path('/Users/researcher/DevProjects/h3-timing-ivebench-auto-r55-20261017/audit/controller_resilience_candidate/overlay/scripts')
def function(text,name):
 n=next(n for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
 return '\n'.join(text.splitlines()[n.lineno-1:n.end_lineno])
def replace(text,name,new):return text.replace(function(text,name),new.rstrip())
p=R/'scripts/service.py';s=p.read_text();s=s.replace("PORT = RUNTIME['port']", "PORT = RUNTIME['port']\n\n\nclass ResourceUnavailable(ValueError):\n    def __init__(self,reason,snapshot):\n        super().__init__(reason);self.snapshot=snapshot")
s=s.replace('capture_output=True, text=True, check=True).stdout','capture_output=True, text=True, check=True, timeout=20).stdout')
s=replace(s,'check_admission','''def check_admission(admission, processes, queue):
    allowed={int(row['pid']):row['identity'] for row in admission['permitted_compute_processes']}
    owned=[]
    for row in processes:
        uid=proc_uid(row['pid'])
        if uid is None:raise ResourceUnavailable('compute process ownership temporarily unavailable',{'processes':processes})
        if uid!=os.getuid():continue
        owned.append(row)
        actual=external_identity(row['pid'])
        if actual is None:raise ResourceUnavailable('own compute identity disappeared during query',{'pid':row['pid']})
        if row['pid'] not in allowed or actual!=allowed[row['pid']]:
            raise RuntimeError('Unexpected own compute identity '+str(row['pid']))
    if len({row['gpu_uuid'] for row in owned}|{GPU})>2:
        raise ResourceUnavailable('planned service exceeds two owned GPU cards',{'processes':processes})
    if queue['queue_running'] or queue['queue_pending']:
        raise RuntimeError('Existing Comfy service has queued/running work; refusing to start')
''')
new='''def native_memory_profile():
    path=RUN/'configs/native_memory_profile.json';profile=json.loads(path.read_text())
    if profile.get('schema')!='r57-native-memory-admission-v2' or profile.get('margin_mib')!=2048:
        raise ValueError('native memory profile changed')
    relative=Path(profile['evidence_file'])
    if relative.is_absolute() or '..' in relative.parts:raise ValueError('unsafe memory evidence path')
    evidence=RUN/relative
    if hashlib.sha256(evidence.read_bytes()).hexdigest()!=profile['evidence_sha256']:raise ValueError('native memory evidence changed')
    rows=[json.loads(line) for line in evidence.read_text().splitlines() if line.strip()]
    peak=max(float(row['sample'].split(',')[1]) for row in rows)
    if peak!=46353 or profile['sampled_peak_mib']!=peak or profile['required_free_mib']!=peak+2048:
        raise ValueError('native required free memory differs from measured maximum plus margin')
    return dict(profile,profile_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def gpu_readiness(admission,queue,*,clock=time.monotonic,sleep=time.sleep,timeout=600):
    if type(timeout) not in (int,float) or not 0<timeout<=600:raise ValueError('resource wait must be at most600seconds')
    profile=native_memory_profile();deadline=clock()+timeout
    while True:
        if clock()>=deadline:raise TimeoutError('native GPU resource admission deadline expired')
        state={'observed_unix':time.time(),'required_free_mib':profile['required_free_mib'],'memory_profile_sha256':profile['profile_sha256']}
        try:
            processes=compute_processes();state['processes']=processes;check_admission(admission,processes,queue)
            result=subprocess.run(['nvidia-smi','-i',GPU,'--query-gpu=uuid,memory.used,memory.free,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True,timeout=20)
            rows=[line.strip() for line in result.stdout.splitlines() if line.strip()]
            if len(rows)!=1 or result.stderr.strip():raise RuntimeError('GPU exact-UUID query returned ambiguity or driver error')
            values=[x.strip() for x in rows[0].split(',')]
            if len(values)!=5 or values[0]!=GPU:raise RuntimeError('GPU exact UUID differs from planned device')
            used,free,utilization,temperature=[float(x) for x in values[1:]]
            if not (used>=0 and free>=0 and 0<=utilization<=100 and 0<=temperature<85):raise RuntimeError('GPU health schema/range invalid')
            state.update(csv=rows[0],memory_free_mib=free,memory_used_mib=used,index_fallback=False)
            if free<profile['required_free_mib']:raise ResourceUnavailable('native GPU lacks required free memory',state)
            state['status']='admitted'
        except (ResourceUnavailable,subprocess.TimeoutExpired,subprocess.CalledProcessError) as error:
            state.update(status='waiting',error_type=type(error).__name__,error=str(error),snapshot=getattr(error,'snapshot',None))
        except BaseException as error:
            state.update(status='hard_failure',error_type=type(error).__name__,error=str(error))
            with (RUN/'logs/service_resource_admission.jsonl').open('a') as handle:handle.write(json.dumps(state)+'\\n')
            raise
        with (RUN/'logs/service_resource_admission.jsonl').open('a') as handle:handle.write(json.dumps(state)+'\\n')
        if clock()>=deadline:raise TimeoutError('native GPU resource query completed after deadline')
        if state['status']=='admitted':return state
        sleep(min(2,deadline-clock()))
'''
s=replace(s,'gpu_readiness',new)
s=s.replace("        hardware = gpu_readiness()\n        processes = compute_processes()\n        queue = queue_at(admission.get('existing_comfy_port', 8189))\n        check_admission(admission, processes, queue)","        queue = queue_at(admission.get('existing_comfy_port', 8189))\n        hardware = gpu_readiness(admission,queue)\n        processes = hardware['processes']")
s=replace(s,'residency_snapshot',function((C/'service.py').read_text(),'residency_snapshot'))
p.write_text(s)
p=R/'scripts/job.py';s=p.read_text().replace('import re\n','import re\nimport subprocess\n');c=(C/'job.py').read_text()
for name in ['check_host_admission','wait_host_admission']:
 replacement=function(c,name).replace('    from observer_import import t\n','').replace('t.ResourceUnavailable','service.ResourceUnavailable')
 s=replace(s,name,replacement)
p.write_text(s)
p=R/'scripts/run_queue.py';s=p.read_text();start=s.index("                stats=subprocess.run(");end=s.index('                state(status=status',start)
s=s[:start]+"                record_resources(current)\n"+s[end:]
helper='''
def record_resources(current):
    sample={'unix':time.time(),'job':current}
    try:
        stats=subprocess.run(['nvidia-smi','-i',service.GPU,'--query-gpu=uuid,memory.used,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=20,check=True)
    except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as error:
        sample.update(sample=None,sample_available=False,error_type=type(error).__name__,error=str(error))
    else:
        sample.update(sample=stats.stdout.strip() or None,sample_available=bool(stats.stdout.strip()))
    with (service.RUN/'logs/resources.jsonl').open('a') as handle:handle.write(json.dumps(sample)+'\\n')

'''
s=s.replace('\ndef run(expected_pid',helper+'\ndef run(expected_pid');p.write_text(s)
# Actual full-five periodic driver evidence, bound locally and copied in the small bundle.
source=Path('/Users/researcher/DevProjects/h3-timing-ivebench-auto-r55-20261017/audit/r54_native_resources.jsonl');dest=R/'configs/memory_evidence/r54_native_resources.jsonl';dest.parent.mkdir(exist_ok=True);shutil.copyfile(source,dest)
profile={'schema':'r57-native-memory-admission-v2','sampled_peak_mib':46353,'margin_mib':2048,'required_free_mib':48401,'evidence_file':'configs/memory_evidence/r54_native_resources.jsonl','evidence_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'scope':'R54 full-five periodic driver samples about20seconds. Sampled maximum is not a continuous peak upper bound; P1 still requires actual observation.','runtime_settings':'Same R54 Native; no reserve-vram change','root_authorization':'REDACTED_CREDENTIAL'}
(R/'configs/native_memory_profile.json').write_text(json.dumps(profile,indent=2)+'\n')
p=R/'tests/test_resource_resilience.py';s=p.read_text().replace("'cmdline':'owned'}}","'cmdline':'owned'},'cache_none':False}")
s=s.replace("self.q={'queue_running':[],'queue_pending':[]}","self.q={'queue_running':[],'queue_pending':[]}\n  import shutil\n  (self.root/'configs/memory_evidence').mkdir()\n  shutil.copyfile(ROOT/'configs/native_memory_profile.json',self.root/'configs/native_memory_profile.json')\n  shutil.copyfile(ROOT/'configs/memory_evidence/r54_native_resources.jsonl',self.root/'configs/memory_evidence/r54_native_resources.jsonl')")
p.write_text(s)
print('Native resource revision2 applied; startup args and numerical modules unchanged')
