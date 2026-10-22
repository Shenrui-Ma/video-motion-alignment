"""One bounded read-only snapshot of the current isolated remote run."""
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REMOTE_CODE='''import json,time,subprocess
from pathlib import Path
r=Path('/data3/researcher/h3_runs/silverwolf_baseline_20261014')
d={'unix':time.time(),'controller':json.loads((r/'logs/controller_state.json').read_text()),'hooks':{}}
for name in ['06_silverwolf_seed2_baseline']:
 p=r/'audit/emphasis'/f'{name}.json'
 if p.exists():
  h=json.loads(p.read_text());d['hooks'][name]={k:h.get(k) for k in ['factor','status','completed_calls','completed_forward_calls','expected_sampling_steps','native_override_calls','error']}
d['gpu_csv']=subprocess.check_output(['nvidia-smi','-i','GPU-REDACTED','--query-gpu=memory.used,memory.free,utilization.gpu,temperature.gpu','--format=csv,noheader'],text=True).strip()
log=r/'logs/comfyui.log'
with log.open('rb') as f:f.seek(max(0,log.stat().st_size-2200));d['log_tail']=f.read().decode(errors='replace')
print(json.dumps(d))
'''
p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','researcher@192.0.2.1','python3 -'],
    input=REMOTE_CODE,capture_output=True,text=True,timeout=40)
if p.returncode:raise RuntimeError(p.stderr[-1800:])
d=json.loads(p.stdout);out=ROOT/'analysis/resource_snapshots';out.mkdir(exist_ok=True)
(out/f'{int(d["unix"])}.json').write_text(json.dumps(d,indent=2))
print(json.dumps(d,ensure_ascii=False,indent=2))
