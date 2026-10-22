"""Host9 cgroup-v1 telemetry and host-RAM guard; no file-cache credit assumptions."""
import json, os, time
from pathlib import Path
GIB=2**30
UNLIMITED=2**60
ROOT=Path(__file__).resolve().parents[1]


def snapshot(proc=Path('/proc/self/cgroup'),mount=Path('/sys/fs/cgroup/memory'),meminfo=Path('/proc/meminfo')):
    entries=[x.split(':',2) for x in Path(proc).read_text().splitlines()]
    members=[x[2] for x in entries if 'memory' in x[1].split(',')]
    if len(members)!=1:raise ValueError('host9 cgroup-v1 memory membership required')
    member=Path(members[0])
    if not member.is_absolute() or '..' in member.parts:raise ValueError('invalid memory membership')
    rows=[]
    for rel in [member,*member.parents]:
        p=Path(mount)/str(rel).lstrip('/')
        limit=int((p/'memory.limit_in_bytes').read_text());current=int((p/'memory.usage_in_bytes').read_text())
        events={k:int(v) for k,v in (x.split() for x in (p/'memory.oom_control').read_text().splitlines())}
        events['failcnt']=int((p/'memory.failcnt').read_text())
        if min(limit,current,*events.values())<0:raise ValueError('invalid memory accounting')
        rows.append({'path':str(rel),'current_bytes':current,'max_bytes':None if limit>=UNLIMITED else limit,'events':events})
    fields=dict(x.split(':',1) for x in Path(meminfo).read_text().splitlines())
    units=fields['MemAvailable'].split()
    if len(units)!=2 or units[1]!='kB':raise ValueError('unexpected MemAvailable units')
    return {'schema':'r149-host9-cgroup-v1-v1','uid':os.getuid(),'membership':str(member),'ancestors':rows,
            'host_available_bytes':int(units[0])*1024,'observed_unix':time.time()}


def assess(value,*,stage,baseline=None,previous_pressure_streak=0):
    if stage not in ('entry','running') or value['uid']!=1016:raise ValueError('unexpected host9 trial UID/stage')
    host=value['host_available_bytes']
    if type(host) is not int or host<0:raise ValueError('invalid host available bytes')
    reasons=[]
    if (host<64*GIB if stage=='entry' else host<=40*GIB):reasons.append('host MemAvailable threshold')
    old={r['path']:r for r in baseline['ancestors']} if baseline else None
    rows=[]
    for r in value['ancestors']:
        free=None if r['max_bytes'] is None else r['max_bytes']-r['current_bytes']
        if free is not None and (free<46*GIB if stage=='entry' else free<=20*GIB):reasons.append(r['path']+' raw cgroup max headroom threshold')
        if r['events'].get('under_oom')!=0:reasons.append(r['path']+' under_oom')
        delta={}
        if old is not None:
            if r['path'] not in old or old[r['path']]['max_bytes']!=r['max_bytes']:raise ValueError('memory ancestry/limit changed')
            for key in ('failcnt','oom_kill'):
                if key in r['events']:
                    delta[key]=r['events'][key]-old[r['path']]['events'][key]
                    if delta[key]!=0:reasons.append(r['path']+' memory event delta/reset: '+key)
        rows.append(dict(r,raw_max_headroom_bytes=free,events_delta=delta))
    if not rows:raise ValueError('missing cgroup memory accounting')
    return {'passed':not reasons,'stage':stage,'reasons':reasons,'pressure_streak':0,'host_available_bytes':host,'ancestors':rows,'policy':'host9 v1; host entry64/running40GiB; finite ancestor raw entry46/running20GiB; event changes stop'}


def check(root=ROOT):
    value=snapshot();decision=assess(value,stage='entry')
    if not decision['passed']:raise RuntimeError('capacity admission: '+'; '.join(decision['reasons']))
    return dict(value,admitted=True,working_set_admission=decision)


def observe(root=ROOT):
    try:return {'sample_available':True,'snapshot':snapshot()}
    except Exception as error:return {'sample_available':False,'error':repr(error),'observed_unix':time.time()}
