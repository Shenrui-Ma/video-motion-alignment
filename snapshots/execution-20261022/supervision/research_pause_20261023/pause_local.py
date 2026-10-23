from pathlib import Path
import subprocess,os,signal,time,json,re
D=Path(__file__).resolve().parent;E=D.parents[1];M=E/'metrics'
def ps(pid):
 s=subprocess.run(['ps','-p',str(pid),'-o','pid=,ppid=,uid=,lstart=,state=,command='],capture_output=True,text=True).stdout.strip()
 if not s:return None
 p=s.split(None,9);return {'pid':int(p[0]),'ppid':int(p[1]),'uid':int(p[2]),'start': ' '.join(p[3:8]),'state':p[8],'command':p[9]}
def matches(a,b):return a and b and all(a[k]==b[k] for k in ['pid','uid','start','command'])
def children(pid):
 s=subprocess.check_output(['ps','-axo','pid=,ppid='],text=True)
 return [ps(int(p[0])) for l in s.splitlines() if len(p:=l.split())==2 and int(p[1])==pid]
def write(x):(D/'LOCAL_PAUSE.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
out={'time':time.time(),'reason':'user_requested_pause_all_H3_research_pending_further_command','actions':[],'scope':'local original H3 relay, completed original AWQ downloader and return watcher only; no remote process operations'}
write(out)
targets=[('cn.h3.metrics.relay.20261022',M/'watch_outputs.py',None),('cn.h3.qwen.download.20261022',M/'download_qwen.py',None),(None,M/'qwen_runtime/host41_extension_live_incremental_20261023/return_watch.py',67193)]
for label,source,pid in targets:
 a={'label':label,'source':str(source)};out['actions'].append(a);write(out)
 if label:
  l=subprocess.run(['launchctl','list',label],capture_output=True,text=True)
  a['launchctl_before']=l.stdout
  if l.returncode:a['status']='already_unloaded';write(out);continue
  assert str(source) in l.stdout
  m=re.search(r'"PID"\s*=\s*(\d+)',l.stdout);pid=int(m.group(1)) if m else None
 expected=ps(pid) if pid else None;a['identity_before']=expected
 if expected:
  assert expected['uid']==os.getuid() and str(source) in expected['command'],expected
  assert matches(expected,ps(pid))
  os.kill(pid,signal.SIGSTOP);a['suspended_before_child_drain']=time.time();write(out)
  deadline=time.time()+60
  while children(pid) and time.time()<deadline:time.sleep(1)
  c=children(pid);a['children_after_drain']=c
  if c:a['status']='paused_waiting_existing_children';write(out);continue
 if label:
  # Paused parent cannot spawn anything; remove only its original launchd label.
  l=subprocess.run(['launchctl','remove',label],capture_output=True,text=True);a['launchctl_remove_code']=l.returncode;a['launchctl_remove_stderr']=l.stderr
  assert l.returncode==0,(label,l.stderr)
 if expected and matches(expected,ps(pid)):
  os.kill(pid,signal.SIGTERM)
  if matches(expected,ps(pid)):os.kill(pid,signal.SIGCONT)
  deadline=time.time()+5
  while matches(expected,ps(pid)) and time.time()<deadline:time.sleep(.2)
 a['identity_after']=ps(pid) if pid else None
 a['label_present_after']=subprocess.run(['launchctl','list',label],capture_output=True,text=True).returncode==0 if label else False
 a['status']='stopped_and_autostart_removed' if not a['label_present_after'] and not matches(expected,a['identity_after']) else 'requires_followup'
 write(out)
out['finished']=time.time();write(out);print(json.dumps(out,ensure_ascii=False,indent=2))
