"""Launch real isolated Python children with markers; CPU stdlib only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('candidate_transport',ROOT/'transport.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
rows=[]
with tempfile.TemporaryDirectory(prefix='real_launch_',dir=ROOT) as td:
 t.ROOT=Path(td);obs=t.ROOT/'audit/observations';obs.mkdir(parents=True)
 parent=t.identity(os.getpid())
 code='''import importlib.util,json,os,sys,time
from pathlib import Path
spec=importlib.util.spec_from_file_location('child_transport',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.install_lifetime_guard(json.loads(sys.argv[3]))
time.sleep(.1)
m.write_new(Path(sys.argv[2]),{'schema':'h3-child-execution-start-v1','identity':m.identity(os.getpid()),'started_monotonic':time.monotonic()})
time.sleep(.25)
'''
 for i in range(10):
  d=obs/('step%03d'%i);d.mkdir();marker=d/'started.json'
  command=[sys.executable,'-c',code,str(ROOT/'transport.py'),str(marker),json.dumps(parent)]
  result=t.run_child(command,dict(os.environ,CUDA_VISIBLE_DEVICES=''),d,'cpu_child',10,parent,execution_started_path=marker,execution_timeout=10)
  assert result['returncode']==0 and not t.alive(result['process'])
  assert result['execution_start']['identity']==result['process']
  rows.append({'iteration':i,'process':result['process'],'returncode':0,'wall_seconds':result['wall_seconds'],'exact_marker_identity':True})
record={'passed':True,'iterations':rows,'cuda_imported':False,'torch_imported':False,'scope':'Real Linux /proc identity, complete argv binding, isolated process group and child marker; CPU-only Python children.'}
(ROOT/'LINUX_SMOKE.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({'passed':True,'iterations':len(rows),'file':str(ROOT/'LINUX_SMOKE.json')}))
