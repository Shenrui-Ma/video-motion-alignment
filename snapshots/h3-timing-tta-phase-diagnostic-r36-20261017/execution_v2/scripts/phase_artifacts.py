"""Durable attempts; a complete phase is validated before reuse, never recomputed."""
import json,os
from pathlib import Path
from contract import ROOT,read,sha,require,save


def identity(pid):
    p=Path('/proc')/str(pid)
    if not p.exists():return None
    text=(p/'stat').read_text();rest=text[text.rfind(')')+2:].split()
    return {'pid':pid,'uid':p.stat().st_uid,'start_ticks':int(rest[19]),'cmdline_sha256':sha(p/'cmdline')}


def owner_alive(record):
    return record is not None and identity(record['pid'])==record


def validate_record(dest,record,entry,view):
    require(record.get('status')=='complete' and record['phase']==f"pose:{entry['id']}:{view}",'Phase identity')
    require(record['freeze_sha256']==sha(ROOT/'FREEZE.json') and record['input_video_sha256']==entry['video_sha256'] and record['identity_pose_sha256']==entry['identity_pose_sha256'],'Completion input binding')
    relative=Path(record['attempt']);require(not relative.is_absolute() and relative.parts[:1]==('attempts',) and len(relative.parts)==2 and '..' not in relative.parts,'Attempt path')
    attempt=dest/relative;require(attempt.is_dir() and not attempt.is_symlink(),'Attempt directory')
    actual={str(p.relative_to(attempt)) for p in attempt.rglob('*') if p.is_file()}-{'VALIDATED.json'}
    require(actual==set(record['files']),'Exact attempt inventory')
    for name,digest in record['files'].items():
        p=attempt/name;require(not p.is_symlink() and p.resolve().is_relative_to(attempt.resolve()) and sha(p)==digest,'Attempt artifact changed')
    require(record['inverse_pose_sha256']==sha(attempt/'inverse.pose.json'),'Inverse pose binding')
    return attempt


def completed_or_recover(dest,entry,view):
    dest=Path(dest)
    if (dest/'COMPLETE.json').exists():
        c=read(dest/'COMPLETE.json');attempt=validate_record(dest,c,entry,view)
        require(sha(attempt/'VALIDATED.json')==c['attempt_manifest_sha256'],'Validated manifest SHA')
        require(read(attempt/'VALIDATED.json')=={k:v for k,v in c.items() if k!='attempt_manifest_sha256'},'Completion/validated equality')
        return c
    for attempt in sorted((dest/'attempts').glob('attempt*')):
        if (attempt/'VALIDATED.json').exists():
            c=read(attempt/'VALIDATED.json');validate_record(dest,c,entry,view)
            final=c|{'attempt_manifest_sha256':sha(attempt/'VALIDATED.json')};save(dest/'COMPLETE.json',final);return final
        for name in ('RUNNING.json','CHILD.json'):
            p=attempt/name
            if p.exists() and owner_alive(read(p).get('identity')):raise RuntimeError('Matching live phase process; refuse duplicate')
    return None


def create_attempt(dest):
    base=Path(dest)/'attempts';base.mkdir(parents=True,exist_ok=True)
    numbers=[]
    for p in base.iterdir():
        if not p.is_dir() or not p.name.startswith('attempt') or not p.name[7:].isdigit():raise ValueError('Unexpected attempt entry')
        numbers.append(int(p.name[7:]))
    attempt=base/f'attempt{max(numbers,default=0)+1:03d}';attempt.mkdir();return attempt
