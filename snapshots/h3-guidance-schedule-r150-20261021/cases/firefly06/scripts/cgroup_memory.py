"""Administrative first-load headroom and optional cgroup-v2 telemetry; no torch import."""
import json, math, os, time
from pathlib import Path

GIB=1024**3
ROOT=Path(__file__).resolve().parents[1]


def limit(text):
    value=text.strip()
    if value=='max':return None
    number=int(value)
    if number<0:raise ValueError('negative cgroup memory limit')
    return number


def counters(text):
    result={}
    for line in text.splitlines():
        key,value=line.split();number=int(value)
        if number<0:raise ValueError('negative cgroup event counter')
        result[key]=number
    return result


def pressure(text):
    result={}
    for line in text.splitlines():
        fields=line.split();row={}
        for field in fields[1:]:
            key,value=field.split('=');number=int(value) if key=='total' else float(value)
            if not math.isfinite(number) or number<0:raise ValueError('invalid memory pressure')
            row[key]=number
        result[fields[0]]=row
    return result


def snapshot(proc=Path('/proc/self/cgroup'),mount=Path('/sys/fs/cgroup'),meminfo=Path('/proc/meminfo')):
    start=time.monotonic();entries=[x.split(':',2) for x in Path(proc).read_text().splitlines()]
    entry=[x for x in entries if x[:2]==['0','']]
    if len(entry)!=1:raise RuntimeError('one unified cgroup-v2 membership required')
    membership=Path(entry[0][2]);mount=Path(mount)
    if not membership.is_absolute() or '..' in membership.parts:raise ValueError('invalid cgroup membership')
    rows=[]
    for rel in [membership,*membership.parents]:
        folder=mount/str(rel).lstrip('/')
        if rel==Path('/') and not (folder/'memory.current').exists():
            rows.append({'path':'/','current_bytes':None,'high_bytes':None,'max_bytes':None,'events':{},'pressure':pressure((folder/'memory.pressure').read_text()),'peak_bytes':None,'headroom_bytes':{},'root_controller_limits_exposed':False})
            continue
        current=int((folder/'memory.current').read_text())
        if current<0:raise ValueError('negative memory.current')
        row={'path':str(rel),'current_bytes':current,'high_bytes':limit((folder/'memory.high').read_text()),'max_bytes':limit((folder/'memory.max').read_text()),'events':counters((folder/'memory.events').read_text()),'pressure':pressure((folder/'memory.pressure').read_text())}
        row['stat']=counters((folder/'memory.stat').read_text())
        row['current_bytes']=max(current,int((folder/'memory.current').read_text()))
        current=row['current_bytes']
        peak=folder/'memory.peak'
        row['peak_bytes']=int(peak.read_text()) if peak.exists() else None
        row['headroom_bytes']={key:max(0,row[key+'_bytes']-current) for key in ('high','max') if row[key+'_bytes'] is not None}
        rows.append(row)
    finite=[(v,row['path'],key) for row in rows for key,v in row['headroom_bytes'].items()]
    if not finite:raise RuntimeError('no finite ancestor memory bound observed')
    smallest=min(finite)
    mem={k:v.strip() for k,v in (line.split(':',1) for line in Path(meminfo).read_text().splitlines())}
    available=mem['MemAvailable'].split()
    if len(available)!=2 or available[1]!='kB':raise ValueError('unexpected host memory units')
    return {'schema':'r123-cgroup-snapshot-v2','uid':os.getuid(),'membership':str(membership),'ancestors':rows,'effective_headroom_bytes':smallest[0],'limiting_path':smallest[1],'limiting_kind':smallest[2],'host_available_bytes':int(available[0])*1024,'observed_unix':time.time(),'read_seconds':time.monotonic()-start}


def admit(value,policy):
    from working_set_capacity import assess
    try:review=assess(value,value['host_available_bytes'],policy['working_set'])
    except (ValueError,KeyError) as error:raise RuntimeError('invalid capacity evidence: '+str(error)) from error
    if not review['admitted']:raise RuntimeError('capacity admission: '+'; '.join(review['failures']))
    return dict(value,admitted=True,working_set_admission=review,margin_basis=policy['margin_basis'])


def check(root=ROOT):
    policy=json.loads((Path(root)/'configs/cgroup_policy.json').read_text())
    return admit(snapshot(),policy)


def delta(current,baseline):
    before={row['path']:row for row in baseline['ancestors']};changes={}
    for row in current['ancestors']:
        old=before.get(row['path'])
        if old is None:continue
        difference={key:row['events'][key]-value for key,value in old['events'].items() if key in row['events']}
        # A reset is diagnostic, never treated as negative new events.
        changes[row['path']]={'events_delta':difference,'counter_reset_detected':any(v<0 for v in difference.values()),'current_bytes_change':row['current_bytes']-old['current_bytes'] if row['current_bytes'] is not None and old['current_bytes'] is not None else None}
    return {'paths':changes,'baseline_unix':baseline['observed_unix'],'historical_events_are_not_new_failures':True}


def observe(root=ROOT):
    """Telemetry failure is UNKNOWN; it never cancels an otherwise healthy inference."""
    try:
        root=Path(root);value=snapshot();baseline=json.loads((root/'audit/CGROUP_STARTUP.json').read_text())
        return {'sample_available':True,'snapshot':value,'since_startup':delta(value,baseline)}
    except (OSError,ValueError,KeyError,RuntimeError) as error:
        return {'sample_available':False,'observed_unix':time.time(),'error':repr(error)}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    print(json.dumps(check() if args.check else snapshot(),indent=2))
