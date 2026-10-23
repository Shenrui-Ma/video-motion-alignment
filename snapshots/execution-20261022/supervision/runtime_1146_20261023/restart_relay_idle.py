import subprocess,os,signal,time,json,pathlib
D=pathlib.Path(__file__).parent;pid=16330;path='/workspace/research-user/DevProjects/video-motion-alignment/execution-20261022/metrics/watch_outputs.py';initial=subprocess.check_output(['ps','-p',str(pid),'-o','uid=,lstart=,command='],text=True)
assert path in initial and initial.strip().startswith('501 ')
for attempt in range(180):
 current=subprocess.run(['ps','-p',str(pid),'-o','uid=,lstart=,command='],text=True,capture_output=True).stdout
 if current!=initial:raise RuntimeError('relay identity changed')
 os.kill(pid,signal.SIGSTOP)
 try:
  children=subprocess.run(['pgrep','-P',str(pid)],capture_output=True,text=True).stdout.strip()
  if children:os.kill(pid,signal.SIGCONT);time.sleep(10);continue
  os.kill(pid,signal.SIGTERM);os.kill(pid,signal.SIGCONT);time.sleep(.3)
  subprocess.run(['launchctl','kickstart','gui/501/cn.h3.metrics.relay.20261022'],check=True)
  rec={'old_pid':pid,'old_ps':initial,'time':time.time(),'tests_passed':10,'reason':'add released field reproduction as ninth producer with separate cohort','active_children_before_stop':[]}
  (D/'RELAY_RESTART.json').write_text(json.dumps(rec,indent=2));print('restarted',flush=True);break
 except BaseException:
  try:os.kill(pid,signal.SIGCONT)
  except ProcessLookupError:pass
  raise
else:raise RuntimeError('no idle boundary in ten minutes')
