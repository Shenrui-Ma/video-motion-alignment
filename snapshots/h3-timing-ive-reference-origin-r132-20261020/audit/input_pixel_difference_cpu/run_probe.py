from pathlib import Path
import subprocess,concurrent.futures,shlex,json
out=Path(__file__).resolve().parent
script=(out/'probe.py').read_text()
configs=[('host41','H3_SERVER_B','/data3/researcher/ComfyUI/.venv/bin/python','/data3/researcher/h3_runs/closure_tutorials_53592/01-anime/runtime_deps','/data4/researcher/h3_runs/timing_ive_reference_origin_r132_20261020','r132_long_0039_seed2026101701_reference_origin_conditioning.json'),('host9','H3_SERVER_A','/home/researcher/miniconda3/envs/comfyui/bin/python','/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps','/home/researcher/h3_runs/timing_ive_generic_retention_r122_20261020','r122_long_0039_shared_conditioning.json')]
def run(c):
 label,host,python,deps,root,name=c
 cmd='CUDA_VISIBLE_DEVICES= PYTHONPATH='+shlex.quote(deps)+' '+shlex.join([python,'-',root,name])
 r=subprocess.run(['ssh',host,cmd],input=script,text=True,capture_output=True,timeout=120)
 (out/(label+'.stderr.txt')).write_text(r.stderr)
 (out/(label+'.json' if r.returncode==0 else label+'.failed.txt')).write_text(r.stdout)
 return label,r.returncode,r.stderr[-1000:]
with concurrent.futures.ThreadPoolExecutor() as e:
 for v in e.map(run,configs):print(v)
