"""Copy only this isolated run's evidence to its local archive."""
import argparse
import json
import subprocess
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REMOTE='researcher@192.0.2.1:/data5/researcher/h3_runs/sam_real_dance_batch_20261015'


def collect(full=False):
    pairs=[('output','outputs'),('logs','logs'),('processes','processes/remote'),
           ('configs','remote_configs'),('analysis','analysis/remote'),('audit','audit')]
    if full:pairs += [('scripts','remote_scripts'),('extensions','remote_extensions')]
    rows=[]
    for source,dest in pairs:
        target=ROOT/dest;target.mkdir(parents=True,exist_ok=True)
        cmd=['rsync','-az','--partial','--exclude=*.tmp','--exclude=__pycache__',
             '-e','ssh -o BatchMode=yes -o ConnectTimeout=12']
        if source=='audit' and not full:cmd += ['--exclude=*.pt','--exclude=tensor_blobs']
        p=subprocess.run(cmd+[REMOTE+'/'+source+'/',str(target)+'/'],capture_output=True,text=True,timeout=600)
        rows.append({'source':source,'dest':dest,'rc':p.returncode,'stderr':p.stderr[-1200:]})
        if p.returncode:raise RuntimeError(rows)
    (ROOT/'logs/last_collection.json').write_text(json.dumps({'unix':time.time(),'full':full,'results':rows},indent=2))
    print(json.dumps({'collected':len(rows),'full':full}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--full',action='store_true');a=p.parse_args();collect(a.full)
