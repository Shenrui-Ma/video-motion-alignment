"""Explicitly launched single R9 intake/CPU evaluation and read-only controls."""
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time
import consumer_r9 as consumer

HERE=Path(__file__).resolve().parent
RUN='r9_s05_hold2'
SHARED=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')


def main():
    with (HERE/'serial_chain.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        consumer.save(HERE/'serial_chain_state.json',{'status':'waiting_for_formal_history','run_id':RUN,'started_unix':time.time()})
        subprocess.run([sys.executable,str(HERE/'consumer_r9.py'),'--run-id',RUN,'--wait'],check=True)
        manifest=HERE/'pilot'/(RUN+'_provenance')/'archive_manifest.json'
        if not manifest.is_file():raise ValueError('Formal output not successfully admitted and measured; failure retained')
        with SHARED.open('a') as heavy_lock:
            fcntl.flock(heavy_lock,fcntl.LOCK_EX)
            subprocess.run([sys.executable,str(HERE/'check_prefix.py')],check=True)
            subprocess.run([sys.executable,str(HERE/'check_capture_inventory.py')],check=True)
            subprocess.run([sys.executable,str(HERE/'complete_r9.py')],check=True)
        consumer.save(HERE/'serial_chain_state.json',{'status':'metrics_and_controls_complete','run_id':RUN,
            'completed_unix':time.time(),'fixed_frame_quality_review_pending':True,'gpu_started':False})
        print(json.dumps({'status':'metrics_and_controls_complete','run_id':RUN}),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        consumer.save(HERE/'serial_chain_failure.json',{'error':repr(exc),'retained':True,'unix':time.time()})
        raise
