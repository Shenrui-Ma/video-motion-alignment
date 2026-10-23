"""48-hour CPU supervisor; only actual pending metric jobs allocate CUDA."""
import argparse,fcntl,json,subprocess,sys,time
from pathlib import Path
from metric_worker import atomic
p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--hours',type=float,default=48);a=p.parse_args();root=Path(a.root);code=root/'code';lock=open(root/'metric_service.lock','a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:sys.exit(0)
deadline=time.time()+3600*a.hours
while time.time()<deadline:
 enabled=json.loads((code/'enabled_metrics.json').read_text())
 cmd=[sys.executable,str(code/'durable_metrics.py'),'--root',str(root/'evaluation'),'--manifest',str(code/'manifest.json'),'--official',str(code/'official_source'),'--model-paths',str(code/'model_paths.yml'),'--metrics',*enabled,'--gpu','GPU-REPLACE-WITH-DEVICE-UUID','--min-free-mib','18000','--timeout','2400','--once']
 subprocess.run(cmd,check=False)
 subprocess.run([sys.executable,str(code/'aggregate.py'),'--results',str(root/'evaluation/results'),'--output',str(root/'evaluation/summary.json'),'--manifest',str(code/'manifest.json')],check=False)
 atomic(root/'service_status.json',{'time':time.time(),'enabled_metrics':enabled,'deadline':deadline})
 time.sleep(60)
