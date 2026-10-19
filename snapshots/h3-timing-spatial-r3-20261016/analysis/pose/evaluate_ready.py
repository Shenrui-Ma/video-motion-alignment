"""One-shot serial evaluation of explicitly admitted R3 runs; never waits for jobs."""
import argparse
import fcntl
from pathlib import Path
from types import SimpleNamespace
import consumer_r3 as consumer


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',action='append',required=True)
    args=parser.parse_args();local=Path(__file__).resolve().parent
    settings=SimpleNamespace(local_dir=str(local),producer_host='H3_SERVER_A',
        producer_root='/data5/researcher/h3_runs/timing_spatial_r3_20261016',
        cpu_host='H3_SERVER_A',cpu_dir='/data5/researcher/h3_runs/timing_spatial_r3_20261016/analysis/pose',
        cpu_python='/home/researcher/miniconda3/envs/comfyui/bin/python')
    for run in args.run_id:
        consumer.formal_run(run)
        if not (local/'pilot'/(run+'_provenance')/'intake_manifest.json').is_file():
            raise ValueError('Exact-history intake is not complete for '+run)
    with (local/'cpu_coordinator.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        completed=[]
        for run in args.run_id:
            if not consumer.cached_complete(local,run):consumer.evaluate(settings,run)
            completed.append(run)
            consumer.save(local/'cpu_evaluation_state.json',{'requested':args.run_id,
                'completed':completed,'status':'serial_cpu_evaluation','no_gpu':True})
        consumer.save(local/'cpu_evaluation_state.json',{'requested':args.run_id,
            'completed':completed,'status':'complete','no_gpu':True})


if __name__=='__main__':main()
