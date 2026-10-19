from pathlib import Path
import hashlib,json,os,subprocess,time
r=Path('/data5/researcher/h3_runs/timing_signed_source6980766_r53_20261017')
peer=Path('/data5/researcher/h3_runs/timing_flexiact_native_r49_20261017')
def ident(pid):
 p=Path('/proc')/str(pid)
 return {'uid':p.stat().st_uid,'start_ticks':(p/'stat').read_text().rsplit(')',1)[1].split()[19],
         'cmdline_sha256':hashlib.sha256((p/'cmdline').read_bytes()).hexdigest()}
owner=json.loads((r/'processes/service.json').read_text())
assert owner['pid']==63582 and owner['identity']['start_ticks']=='2625625538'
actual=ident(63582);assert actual['uid']==1016 and actual['start_ticks']=='2625625538'
old=ident(45686);assert old=={'uid':1016,'start_ticks':'2625167040','cmdline_sha256':'95d6e7b29d8a8342315535cdb4cc44d2dccfed46fcdc228fb9802418843ed60b'}
p=peer/'configs/admission.json';a=json.loads(p.read_text())
backup=peer/f'audit/admission_before_r53_{time.time_ns()}.json';backup.write_bytes(p.read_bytes())
a['permitted_compute_processes']=[{'pid':63582,'identity':actual}]
temp=p.with_name('admission.root.tmp');temp.write_text(json.dumps(a,indent=2)+'\n');os.replace(temp,p)
(r/'audit/root_launch_owner.json').write_text(json.dumps({'pid':63582,**actual,'peer_pid':45686,'peer_identity':old,'peer_admission_backup':str(backup)},indent=2)+'\n')
env=dict(os.environ,TMPDIR=str(r/'temp'),TMP=str(r/'temp'),TEMP=str(r/'temp'))
done=subprocess.run(['python3',str(r/'scripts/start_controller.py'),'--pid','63582','--start-ticks','2625625538'],env=env,capture_output=True,text=True)
(r/'audit/root_controller_start.log').write_text(done.stdout+done.stderr)
print(json.dumps({'service':actual,'controller_start_exit':done.returncode}));print(done.stdout+done.stderr)
raise SystemExit(done.returncode)
