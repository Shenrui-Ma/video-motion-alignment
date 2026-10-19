from pathlib import Path
import copy,json,hashlib,time
R=Path(__file__).resolve().parents[1]
Q=R.parent/'h3-ive-followup-quantitative-r97-r99-r100-20261019/audit/recovery_20261019'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=R/'inventory/ivebench.json';before=sha(p);d=read(p);old=copy.deepcopy(d['items'])
row=next(x for x in d['items'] if x['id']=='r111_long_0174_spatial')
files={'native':Q/'r107_long_0174/actual_host41/cases/r107_long_0174/results/native.json',
    'fixed':Q/'r107_long_0174/actual_host41/cases/r107_long_0174/results/forced.json',
    'spatial':Q/'r111_long_0174_spatial_capacity4/actual_host41/cases/r111_long_0174_spatial/results/spatial.json'}
scores={k:read(v) for k,v in files.items()}
media={'native':'ordinary_video_path','fixed':'fixed_control_video_path','spatial':'guided_video_path'}
for role,result in scores.items():
    assert result['actual_generated_video_sha256']==sha(row[media[role]])
    assert result['valid_frames']==145 and result['fps']==24
    for key in ('official_vendor','checkpoint_sha256','source_tracks_sha256'):
        assert result[key]==scores['native'][key]
receipt=Q/'r111_long_0174_spatial_capacity4/RESULT_VERIFIED.json'
actual=read(receipt);release=Path(actual['release_receipt']['file'])
assert sha(release)==actual['release_receipt']['sha256']
assert actual['scores']['spatial']==scores['spatial']['motion_fidelity']
evidence=list(files.values())+[receipt,release]
mf=row['quantitative_metrics']['motion_fidelity']
mf.update(native=scores['native']['motion_fidelity'],guided=scores['spatial']['motion_fidelity'],
    fixed_control=scores['fixed']['motion_fidelity'],delta=scores['spatial']['motion_fidelity']-scores['native']['motion_fidelity'],
    delta_vs_fixed=scores['spatial']['motion_fidelity']-scores['fixed']['motion_fidelity'],status='complete',
    source_files=[str(x) for x in evidence],source_sha256={str(x):sha(x) for x in evidence},
    scope='145有效帧，三版使用相同官方MF源码、checkpoint和同一原参考轨迹。新方案0.90764，普通编辑0.94243、固定引导0.92995。基础任务与三个不可比动作事件的负结论保留。')
row['quantitative_metrics']['method_variants']={'native':scores['native']['motion_fidelity'],'fixed':scores['fixed']['motion_fidelity'],'spatial':scores['spatial']['motion_fidelity'],'measure':'IVEBench official MF'}
for path in evidence:
    if str(path) not in row['evidence_paths']:row['evidence_paths'].append(str(path))
    row['evidence_sha256'][str(path)]=sha(path)
for oldrow,newrow in zip(old,d['items']):
    if oldrow['id']!=row['id']:assert oldrow==newrow
d['previous_inventory_sha256']=before;d['updated_unix']=time.time();assert sha(p)==before
a=R/'audit/r111_mf_20261019';a.mkdir(exist_ok=False);(a/'PREVIOUS_INVENTORY.json').write_bytes(p.read_bytes())
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
receipt={'before_sha256':before,'after_sha256':sha(p),'row':row['id'],'scores':{k:s['motion_fidelity'] for k,s in scores.items()},'review_unchanged':True}
(a/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
