from pathlib import Path
import json,hashlib,copy,time
R=Path(__file__).resolve().parents[1]
E=R.parent/'h3-ive-followup-quantitative-r97-r99-r100-20261019/audit/recovery_20261019'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
path=R/'inventory/ivebench.json';old=read(path);new=copy.deepcopy(old)
cases=['r100_short_0114','r96_long_0173','r99_short_0230','r99_short_0352']
audit=R/'audit/four_verified_mf_20261019';audit.mkdir(exist_ok=True)
backup=audit/'PREVIOUS_INVENTORY.json'
assert not backup.exists(),'already applied'
backup.write_bytes(path.read_bytes())
rows=[]
for name in cases:
    evidence=E/name/'RESULT_VERIFIED.json';v=read(evidence)
    item=next(x for x in new['items'] if x['id']==name)
    assert item['valid_frames']==v['valid_frames']
    assert all(t['released']['process_absent'] and t['released']['own_cuda_absent'] for t in v['tracks'].values())
    sources=[evidence]
    for label in ['native','forced']:
        score=Path(v['scores'][label]['file']);assert sha(score)==v['scores'][label]['sha256'];sources.append(score)
    metric={'native':v['native'],'guided':v['forced'],'delta':v['delta'],'higher_is_better':True,'status':'complete','source_files':[str(p) for p in sources],'source_sha256':{str(p):sha(p) for p in sources},'valid_frames':v['valid_frames'],'scope':'同一片段有效帧上的官方MF；基础任务完成与具体动作时差另由逐帧审阅判断。','protocol':'IVEBench official MF; commit 2dcf8900ee65197f43854c76f61c66a32bb8dbfc; CoTracker3 offline, grid10, window60'}
    item.setdefault('quantitative_metrics',{})['motion_fidelity']=metric
    item['review_summary']+=f" 官方MF：{v['native']:.6f} → {v['forced']:.6f}（{v['delta']:+.6f}）。"
    rows.append({'id':name,'evidence_sha256':sha(evidence),'native':v['native'],'guided':v['forced'],'delta':v['delta']})
for olditem,newitem in zip(old['items'],new['items']):
    if olditem['id'] not in cases:assert olditem==newitem
new['updated_unix']=time.time();new['previous_inventory_sha256']=sha(path)
path.write_text(json.dumps(new,indent=2,ensure_ascii=False)+'\n')
(audit/'RECEIPT.json').write_text(json.dumps({'previous_sha256':sha(backup),'inventory_sha256':sha(path),'updated':rows,'other_rows_identical':True},indent=2)+'\n')
print(sha(path))
