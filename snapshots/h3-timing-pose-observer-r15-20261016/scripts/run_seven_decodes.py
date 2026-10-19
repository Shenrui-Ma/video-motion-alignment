"""Root-scheduled sequential seven-VAE batch. Requires --execute; no DiT."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import decode_endpoint as adapter

ROOT = Path(__file__).resolve().parents[1]
UUID = 'GPU-REDACTED'
VAE_SHA = '7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522'
def save(path, obj):
    path.write_text(json.dumps(obj, indent=2)+'\n')
def gpu_state():
    return {'gpu': subprocess.check_output(['nvidia-smi', '--id='+UUID, '--query-gpu=uuid,memory.used,utilization.gpu', '--format=csv,noheader,nounits'], text=True).strip(),
            'compute': subprocess.check_output(['nvidia-smi', '--id='+UUID, '--query-compute-apps=pid', '--format=csv,noheader,nounits'], text=True).strip()}
def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--execute', action='store_true'); a = p.parse_args()
    rows = json.loads((ROOT/'analysis/input_inventory.json').read_text())['inputs']
    output = ROOT/'analysis/x0_decoded'; output.mkdir(parents=True, exist_ok=True)
    commands = []
    for row in rows:
        stem = row['case']+f"_step{row['index']:03d}"
        command = [sys.executable, '-u', str(ROOT/'scripts/decode_endpoint.py'), '--case', row['case'], '--index', str(row['index']),
                   '--core', '/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI',
                   '--runtime-deps', '/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps',
                   '--vae', '/data5/researcher/ComfyUI/models/vae/minimax_h3_video_vae_fp16.safetensors',
                   '--expected-vae-sha256', VAE_SHA, '--gpu-uuid', UUID, '--output', str(output/(stem+'.mp4'))]
        commands.append({'stem': stem, 'source': row, 'command': command})
    if not a.execute:
        print(json.dumps({'execute': False, 'commands': commands}, indent=2)); return
    with (output/'coordinator.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        record_path = output/'execution.json'
        if record_path.exists(): raise FileExistsError('Inspect existing batch; no automatic retry/overwrite')
        gate=json.loads((ROOT/'analysis/input_cpu_validation.json').read_text())
        if gate['status'] != 'pass' or gate['adapter_sha256'] != adapter.sha(ROOT/'scripts/decode_endpoint.py') or gate['inventory_sha256'] != adapter.sha(ROOT/'analysis/input_inventory.json'):
            raise ValueError('Validated adapter/input binding differs')
        record = {'status':'running','pid':os.getpid(),'started_unix':time.time(),'nfe':0,'dit_started':False,
                  'source_run_ids':['r10_s05_fixed_full_probe','r14_s05_seed1313_native_host9'],
                  'before':gpu_state(),'rows':[], 'adapter_sha256':gate['adapter_sha256'], 'decoder_sha256':adapter.DECODER_SHA}
        save(record_path,record)
        try:
            env=os.environ.copy()
            for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):env[k]='4'
            for item in commands:
                t=time.time(); stem=item['stem']; source=item['source']
                with (output/(stem+'.log')).open('x') as log:
                    proc=subprocess.Popen(item['command'],env=env,stdout=log,stderr=subprocess.STDOUT)
                    row={'stem':stem,'pid':proc.pid,'command':item['command'],'started_unix':t};record['rows'].append(row);save(record_path,record)
                    rc=proc.wait()
                row.update(exit_code=rc,finished_unix=time.time(),wall_seconds=time.time()-t,pid_absent=not Path('/proc/'+str(proc.pid)).exists(),gpu_after=gpu_state())
                save(record_path,record)
                if rc:raise RuntimeError('VAE decode failed; stop, preserve evidence')
                d=json.loads((output/(stem+'.json')).read_text())
                if d['status']!='complete' or d['snapshot_sha256']!=source['sha256'] or d['vae_sha256']!=VAE_SHA or d['decoded_shape']!=[141,736,1312,3] or d['output_sha256']!=adapter.sha(output/(stem+'.mp4')):
                    raise ValueError('Decode record/output mismatch')
                if row['gpu_after']['compute']:raise RuntimeError('Compute remains after decoder exit')
                print(json.dumps({'completed':stem,'wall_seconds':row['wall_seconds'],'gpu_after':row['gpu_after']}),flush=True)
            record['status']='complete'
        except BaseException as error:
            record.update(status='failed',error=repr(error));raise
        finally:
            record.update(finished_unix=time.time(),after=gpu_state());save(record_path,record)
if __name__=='__main__':main()
