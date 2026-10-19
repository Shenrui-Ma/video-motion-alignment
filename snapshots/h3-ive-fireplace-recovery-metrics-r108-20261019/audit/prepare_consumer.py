"""Reuse the verified consumer with a single, separately bound fireplace task."""
from pathlib import Path
import json,hashlib,shutil
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'h3-ive-task-repair-metrics-r100-20261019'
PRODUCER=ROOT.parent/'h3-timing-ive-fireplace-recovery-r108-20261019'
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
assert not (ROOT/'CONSUMER_FREEZE.json').exists()
for folder in ['scripts','tests','configs','inputs','audit','incoming','incoming_pairs','showcase','showcase_pairs','prepared']:
    (ROOT/folder).mkdir(exist_ok=True)
for folder in ['scripts','tests']:
    for p in (PARENT/folder).glob('*.py'):
        text=p.read_text().replace('r100','r108').replace('R100','R108').replace('timing_ive_task_repair_r108','timing_ive_fireplace_recovery_r108').replace('8564','8571')
        text=text.replace("SOURCES=('short_0114','short_0392')","SOURCES=('short_0392',)").replace("len(c.SOURCES),2","len(c.SOURCES),1").replace('fixed_two_denominator','fixed_one_denominator').replace("'fixed_source_denominator':2","'fixed_source_denominator':1").replace('固定2个来源','固定1个来源')
        if folder=='tests':
            text=text.replace("source_id='short_0392'","source_id='not_registered'").replace("'short_0114'","'short_0392'")
        (ROOT/folder/p.name).write_text(text)
c=read(PARENT/'configs/contract.json');s=read(PRODUCER/'configs/scientific_contract.json');runtime=read(PRODUCER/'configs/runtime.json')
c.update(schema='r108-native-and-paired-media-consumer-v1',producer_local=str(PRODUCER),producer_remote=runtime['remote_root'],producer_seal_sha256=sha(PRODUCER/'deploy_manifest.json'),producer_contract_sha256=sha(PRODUCER/'configs/scientific_contract.json'),producer_runtime_sha256=sha(PRODUCER/'configs/runtime.json'),source_order=['short_0392'])
c['sources']=[p for p in c['sources'] if p['source_id']=='short_0392']
for row in c['sources']:
    row['run_id']=row['run_id'].replace('r100','r108');row['forced_run_id']=row['forced_run_id'].replace('r100','r108')
    row['graph_sha256']=sha(PRODUCER/'configs/graphs'/f"{row['run_id']}.json")
    row['forced_graph_sha256']=sha(PRODUCER/'configs/graphs'/f"{row['forced_run_id']}.json")
    row['original_media']['file']=str(PRODUCER/'inputs/short_0392_original.mp4')
    for key in ['source','provenance']:shutil.copy2(PRODUCER/row[key]['file'],ROOT/row[key]['file'])
put(ROOT/'configs/contract.json',c)
for a,b in [('producer_runtime.json','configs/runtime.json'),('producer_scientific_contract.json','configs/scientific_contract.json'),('producer_seal.json','deploy_manifest.json')]:shutil.copy2(PRODUCER/b,ROOT/'configs'/a)
put(ROOT/'audit/PREPARATION_ORIGIN.json',{'parent':str(PARENT),'parent_freeze_sha256':sha(PARENT/'CONSUMER_FREEZE.json'),'producer':str(PRODUCER),'producer_seal':c['producer_seal_sha256'],'execution_started':False})
print(c['source_order'])
