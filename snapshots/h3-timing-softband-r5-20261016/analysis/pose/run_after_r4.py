"""One serial R5 CPU chain; waits for the active R4 replay finalizer."""
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time
import consumer_r5 as consumer

HERE=Path(__file__).resolve().parent
R4=Path('/Users/researcher/DevProjects/h3-timing-target-path-r4-20261016/analysis/pose')


def main():
    with (HERE/'serial_chain.lock').open('a') as own:
        fcntl.flock(own,fcntl.LOCK_EX|fcntl.LOCK_NB)
        consumer.save(HERE/'serial_chain_state.json',{'status':'waiting_for_existing_r4_finalizer','no_gpu':True})
        with (R4/'replay_finalizer.lock').open('a') as previous:
            fcntl.flock(previous,fcntl.LOCK_EX)
            state=json.loads((R4/'replay_state.json').read_text())
            if state['status']!='complete':raise RuntimeError('R4 replay chain not complete')
        consumer.save(HERE/'serial_chain_state.json',{'status':'r5_single_consumer_running','r4_replay_passed':state['passed'],'no_gpu':True})
        subprocess.run([sys.executable,'-u',str(HERE/'consumer_r5.py'),'--run-id','r5_s05_softband_6to14','--wait','--timeout-minutes','120'],check=True)
        subprocess.run([sys.executable,'-u',str(HERE/'complete_r5.py')],check=True)
        consumer.save(HERE/'serial_chain_state.json',{'status':'cpu_and_pairing_complete','r4_replay_passed':state['passed'],'quality_review':'pending','no_gpu':True})


if __name__=='__main__':
    try:main()
    except Exception as exc:
        consumer.save(HERE/'serial_chain_failure.json',{'error':repr(exc),'retained':True,'unix':time.time()})
        raise
