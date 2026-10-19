"""One serial fixed-mask CPU intake/evaluation chain. Never starts a GPU."""
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time
import consumer_r11 as consumer

HERE=Path(__file__).resolve().parent
RUNS=['r11_s05_continuous6to19','r11_s05_skip7_6to14']
SHARED=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')


def main():
    with (HERE/'serial_chain.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        completed=[]
        for run in RUNS:
            consumer.save(HERE/'serial_chain_state.json',{'status':'waiting_for_formal_history','current_run':run,'completed':completed,'started_unix':time.time()})
            subprocess.run([sys.executable,str(HERE/'consumer_r11.py'),'--run-id',run,'--wait'],check=True)
            manifest=HERE/'pilot'/(run+'_provenance')/'archive_manifest.json'
            if not manifest.is_file():raise ValueError('Formal output not admitted and measured; retained failure for '+run)
            with SHARED.open('a') as heavy:
                fcntl.flock(heavy,fcntl.LOCK_EX)
                for script in ['check_prefix.py','check_capture_inventory.py','check_feedback_audit.py']:
                    subprocess.run([sys.executable,str(HERE/script),'--run-id',run],check=True)
                subprocess.run([sys.executable,str(HERE/'complete_r11.py')],check=True)
            completed.append(run)
            consumer.save(HERE/'serial_chain_state.json',{'status':'run_measured','completed':completed,'fixed_frame_quality_pending':True,'gpu_started':False})
        consumer.save(HERE/'serial_chain_state.json',{'status':'all_metrics_and_controls_complete','completed':completed,'completed_unix':time.time(),'fixed_frame_quality_pending':True,'gpu_started':False})
        print(json.dumps({'status':'all_metrics_and_controls_complete','completed':completed}),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        consumer.save(HERE/'serial_chain_failure.json',{'error':repr(exc),'retained':True,'unix':time.time()})
        raise
