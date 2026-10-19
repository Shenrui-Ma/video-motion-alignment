"""Prepare task-isolated runtime/configs from a verified prior experiment."""
from pathlib import Path
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
OLD = Path('/Users/researcher/DevProjects/h3-sam-real-dance-batch-20261015')
REMOTE = '/data5/researcher/h3_runs/timing_autoresearch_20261016'
OLD_REMOTE = '/data5/researcher/h3_runs/sam_real_dance_batch_20261015'

for name in ('service.py', 'job.py', 'supervise_service.py', 'lease_watchdog.py',
             'compatibility_bootstrap.py', 'int8_row_chunking.py', 'backend_dispatch_audit.py'):
    text = (OLD / 'scripts' / name).read_text().replace(OLD_REMOTE, REMOTE)
    text = text.replace('h3-sam-real-dance-batch-20261015', 'h3-timing-autoresearch-20261016')
    text = text.replace('PORT = 8452', 'PORT = 8460')
    if name == 'service.py':
        text = text.replace("'H3EventEmphasis', 'H3PairAudit',", "'H3EventEmphasis', 'H3PairAudit', 'H3TemporalRouter',")
    (ROOT / 'scripts' / name).write_text(text)

for name in ('H3EventAudit', 'H3PairAudit', 'H3EventEmphasis'):
    dst = ROOT / 'extensions' / name
    if not dst.exists():
        shutil.copytree(OLD / 'extensions' / name, dst)
    for p in dst.rglob('*.py'):
        p.write_text(p.read_text().replace('sam_real_dance_batch_20261015', 'timing_autoresearch_20261016'))

for name in ('parent_runtime_provenance.json', 'parent_core_hashes.json', 'model_hashes_host9.json', 'admission.json'):
    shutil.copy2(OLD / 'configs' / name, ROOT / 'configs' / name)
for name in ('05_real_megumi_v.mp4', '07_real_ary_v.mp4', 'sam_altman_village_global_20221117_original.jpg'):
    shutil.copy2(OLD / 'inputs' / name, ROOT / 'inputs' / name)

def graph(name, mode='native', alpha=1.0, time_offset=0, case='05', seed=2026101311,
          width=1024, height=576, steps=20, radius=0, window=(50,65), block_start=0, block_end=50,
          step_start=0, step_end=20):
    g=json.loads((OLD/'configs'/f'{case}_sam_s1_baseline.json').read_text())
    g=json.loads(json.dumps(g).replace(OLD_REMOTE,REMOTE))
    shared=f'{case}_sam_{width}x{height}_shared'
    g['5']['inputs'].update(width=width,height=height,run_id=shared)
    g['6']['inputs'].update(noise_seed=seed,run_id=name,pair_id=f'{case}_sam_{width}x{height}_{seed}')
    g['51']['inputs'].update(source_run_id=shared,run_id=name)
    g['14']['inputs']['filename_prefix']=name
    if mode=='weight3':
        g['50']['inputs'].update(factor=3,start_frame=window[0],end_frame=window[1],run_id=name)
    else:
        g['50']={'class_type':'H3TemporalRouter','inputs':{
            'model':['41',0], 'positive':['51',0], 'mode':mode, 'alpha':alpha,
            'radius':radius, 'time_offset':time_offset,
            'start_frame':window[0], 'end_frame':window[1],
            'block_start':block_start, 'block_end':block_end,
            'step_start':step_start, 'step_end':step_end,
            'run_id':name, 'audit_dir':REMOTE+'/audit/router'}}
    if steps!=20:
        # Timing-only warmup: preserve early entries of the formal trajectory.
        g['9']['inputs']['sigmas']=','.join(g['9']['inputs']['sigmas'].split(',')[:steps+1])
    return g

if __name__=='__main__':
    jobs={
        's05_seed1_native_bench2':dict(mode='native',steps=2),
        's05_seed1_native':dict(mode='native'),
        's05_seed1_weight3':dict(mode='weight3'),
        's05_seed1_mass':dict(mode='mass_preserve'),
        's05_seed1_hard':dict(mode='hard_route'),
        's05_seed1_offset4':dict(mode='mass_preserve',time_offset=4),
    }
    for name,kwargs in jobs.items():
        p=ROOT/'configs'/f'{name}.json'
        if not p.exists():p.write_text(json.dumps(graph(name,**kwargs),indent=2)+'\n')
    print(json.dumps({'root':str(ROOT),'remote':REMOTE,'prepared':list(jobs)}))
