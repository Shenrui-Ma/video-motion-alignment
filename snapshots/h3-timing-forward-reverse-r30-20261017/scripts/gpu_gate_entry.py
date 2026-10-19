"""Pause before importing torch, let root register exact PID, then same-PID runpy."""
import argparse,runpy,sys
from pathlib import Path
from service_entry import wait_gate
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--gate-dir',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--comfy-root',default='/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI');a=p.parse_args()
 target=Path(__file__).resolve().with_name('gpu_joint_smoke.py');wait_gate(a.gate_dir,target)
 sys.argv=[str(target),'--output',str(a.output),'--comfy-root',a.comfy_root];runpy.run_path(str(target),run_name='__main__')
