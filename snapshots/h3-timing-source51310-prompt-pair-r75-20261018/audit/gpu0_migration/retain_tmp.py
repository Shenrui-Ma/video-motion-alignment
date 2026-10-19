"""Retain exactly two authorized historical CPU test directories on data5."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import stat
import subprocess
import time

NAMES = ['h3-counterfactual-cpu-lrjm6f2i', 'h3-counterfactual-cpu-ha3f096u']
ARCHIVE = Path('/data5/researcher/h3_runs/admin_archive_20261018/tmp_retained')
UID = os.getuid()
SSH_DAEMON_VISIBILITY = {}

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def save(path, value):
    temp = path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(value,indent=2)+'\n')
    temp.replace(path)

def active(roots):
    refs=[]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:
            if proc.stat().st_uid!=UID:continue
            cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            targets=[('cmdline',cmd),('cwd',os.readlink(proc/'cwd'))]
            for fd in (proc/'fd').iterdir():
                try:targets.append(('fd',os.readlink(fd)))
                except FileNotFoundError:pass
            for kind,text in targets:
                if any(str(r) in text for r in roots):refs.append({'pid':int(proc.name),'kind':kind,'reference':text})
        except FileNotFoundError:continue
        except PermissionError as exc:
            status=(proc/'status').read_text()
            command=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace').strip()
            fields={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in status.splitlines() if ':' in line}
            if fields.get('Name')=='sshd' and command=='sshd: researcher@notty' and set(fields['Uid'].split())=={str(UID)}:
                SSH_DAEMON_VISIBILITY[proc.name]={'cmdline':command,'stat':(proc/'stat').read_text(),'exception':'non-dumpable SSH session daemon; application descendants inspected separately'}
                continue
            raise RuntimeError('Cannot inspect current-user application process '+proc.name) from exc
    return refs

def inventory(root):
    result={}
    for p in [root,*sorted(root.rglob('*'))]:
        s=p.lstat()
        assert s.st_uid==UID and not stat.S_ISLNK(s.st_mode),str(p)
        assert stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode),str(p)
        row={'uid':s.st_uid,'gid':s.st_gid,'mode':stat.S_IMODE(s.st_mode),'mtime_ns':s.st_mtime_ns,'type':'file' if p.is_file() else 'directory'}
        if p.is_file():row.update(bytes=s.st_size,sha256=sha(p))
        result[str(p.relative_to(root))]=row
    return result

def df():
    return subprocess.check_output(['df','-B1','/','/tmp','/data5'],text=True)

def main():
    assert UID==1016
    ARCHIVE.mkdir(parents=True,exist_ok=True)
    receipt={'schema':'authorized-task-temp-retention-v1','started_unix':time.time(),'uid':UID,'df_before':df(),'directories':[]}
    save(ARCHIVE/'MIGRATION_IN_PROGRESS.json',receipt)
    for name in NAMES:
        source=Path('/tmp')/name;dest=ARCHIVE/name
        assert source.is_dir() and not source.is_symlink()
        refs=active([source]);assert not refs,refs
        original=inventory(source)
        assert all((source/x).is_file() for x in ['reference_off.json','reference_restart.json','reference_always.json'])
        for x in ['reference_off.json','reference_restart.json','reference_always.json']:
            j=json.loads((source/x).read_text())
            assert j['metadata']=={'refs':[]} and j['run_id']==Path(x).stem
        save(ARCHIVE/(name+'.SOURCE_MANIFEST.json'),original)
        print(json.dumps({'phase':'copying','name':name,'files':sum(v['type']=='file' for v in original.values()),'bytes':sum(v.get('bytes',0) for v in original.values())}),flush=True)
        if not dest.exists():shutil.copytree(source,dest,copy_function=shutil.copy2)
        copied=inventory(dest)
        assert copied==original,'Copied content or metadata differs'
        assert inventory(source)==original,'Original changed during copy'
        refs=active([source]);assert not refs,refs
        backup=source.with_name(source.name+'.verified-retained-20261018')
        assert not backup.exists()
        anchor=Path('/data5/researcher')/('h3tmp_l' if name.endswith('lrjm6f2i') else 'h3tmp_h')
        if anchor.is_symlink():assert anchor.resolve()==dest
        else:
            assert not anchor.exists()
            anchor.symlink_to(dest,target_is_directory=True)
        assert len(str(anchor))<60
        source.rename(backup)
        released_file=None
        try:
            try:source.symlink_to(anchor,target_is_directory=True)
            except OSError as exc:
                if exc.errno!=28:raise
                relative,item=max(((k,v) for k,v in original.items() if v['type']=='file'),key=lambda kv:kv[1]['bytes'])
                old_file=backup/relative;new_file=dest/relative
                assert old_file.stat().st_uid==UID and sha(old_file)==sha(new_file)==item['sha256']
                old_file.unlink()
                old_file.symlink_to(new_file)
                assert old_file.resolve()==new_file and sha(old_file)==item['sha256']
                released_file={'relative':relative,'bytes':item['bytes'],'sha256':item['sha256'],'new_file':str(new_file)}
                save(ARCHIVE/(name+'.ROOT_SPACE_RECOVERY.json'),released_file)
                source.symlink_to(anchor,target_is_directory=True)
        except BaseException:
            backup.rename(source)
            raise
        assert source.resolve()==dest and inventory(source.resolve())==original
        if released_file is None:assert inventory(backup)==original
        else:
            assert {'.',*(str(p.relative_to(backup)) for p in backup.rglob('*'))}==set(original)
            for relative,item in original.items():
                p=backup/relative
                assert p.lstat().st_uid==UID
                if item['type']=='file':
                    assert p.is_symlink()==(relative==released_file['relative'])
                    assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256']
                else:assert p.is_dir() and not p.is_symlink()
        refs=active([backup]);assert not refs,refs
        # Parent authorized deletion only of the byte-verified redundant copy.
        shutil.rmtree(backup)
        assert source.is_symlink() and not backup.exists()
        row={'source':str(source),'retained':str(dest),'short_symlink_anchor':str(anchor),'source_manifest':str(ARCHIVE/(name+'.SOURCE_MANIFEST.json')),
             'files':sum(v['type']=='file' for v in original.values()),'bytes':sum(v.get('bytes',0) for v in original.values()),
             'all_sha256_and_metadata_equal':True,'root_space_recovery_file':released_file,'old_path_symlink_verified':True,'redundant_copy_removed':True,'finished_unix':time.time()}
        receipt['directories'].append(row)
        save(ARCHIVE/'MIGRATION_IN_PROGRESS.json',receipt)
        print(json.dumps({'phase':'retained','name':name,'bytes':row['bytes']}),flush=True)
    receipt.update(completed=True,df_after=df(),finished_unix=time.time(),ssh_session_daemon_visibility=SSH_DAEMON_VISIBILITY)
    save(ARCHIVE/'COMPLETE.json',receipt)
    print(json.dumps({'completed':True,'df_after':receipt['df_after']}),flush=True)

if __name__=='__main__':main()
