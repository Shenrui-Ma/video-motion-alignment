from pathlib import Path
import copy,json,hashlib,time
R=Path(__file__).resolve().parents[1]
Q=R.parent/'h3-ive-followup-quantitative-r97-r99-r100-20261019/audit/recovery_20261019'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=R/'inventory/ivebench.json';before=sha(p);d=read(p);old=copy.deepcopy(d['items'])
row=next(x for x in d['items'] if x['id']=='r106_short_0252_sampler_control')
base=Q/'r106_short_0252_solvers_capacity4'
files={k:base/f'actual_host41/cases/r106_short_0252_solvers/results/{k}.json' for k in ('euler','res_multistep')}
scores={k:read(v) for k,v in files.items()}
for role,key in [('euler','ordinary_video_path'),('res_multistep','alternative_video_path')]:
    result=scores[role]
    assert result['actual_generated_video_sha256']==sha(row[key])
    assert result['valid_frames']==98 and result['fps']==24
    for k in ('official_vendor','checkpoint_sha256','source_tracks_sha256'):assert result[k]==scores['euler'][k]
receipt=base/'RESULT_VERIFIED.json';verified=read(receipt)
release=Path(verified['release_receipt']['file']);assert sha(release)==verified['release_receipt']['sha256']
for role in scores:assert verified['scores'][role]==scores[role]['motion_fidelity']
evidence=list(files.values())+[receipt,release]
row['quantitative_metrics']['motion_fidelity'].update(euler=scores['euler']['motion_fidelity'],res_multistep=scores['res_multistep']['motion_fidelity'],
    delta=scores['res_multistep']['motion_fidelity']-scores['euler']['motion_fidelity'],status='complete',
    source_files=[str(x) for x in evidence],source_sha256={str(x):sha(x) for x in evidence},
    scope='98有效帧，同环境新计算原参考及两版输出的官方轨迹。res_multistep比Euler的MF高0.00818；两者可见事件区间近似一致且初段约晚15帧。两版均为普通编辑。')
for path in evidence:
    if str(path) not in row['evidence_paths']:row['evidence_paths'].append(str(path))
    row['evidence_sha256'][str(path)]=sha(path)
spatial=next(x for x in d['items'] if x['id']=='r111_long_0174_spatial')
comparison=Q/'r111_long_0174_spatial_capacity4/COMPARISON_VERIFIED.json'
assert sha(comparison)=='f9ec3cfd0849c14b159d8e2a739600a0fe5f4af71df2157be1625ece1f592313'
spatial['evidence_paths'].append(str(comparison));spatial['evidence_sha256'][str(comparison)]=sha(comparison)
for oldrow,newrow in zip(old,d['items']):
    if oldrow['id'] not in [row['id'],spatial['id']]:assert oldrow==newrow
d['previous_inventory_sha256']=before;d['updated_unix']=time.time();assert sha(p)==before
a=R/'audit/r106_mf_20261019';a.mkdir(exist_ok=False);(a/'PREVIOUS_INVENTORY.json').write_bytes(p.read_bytes())
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
receipt={'before_sha256':before,'after_sha256':sha(p),'row':row['id'],'scores':{k:s['motion_fidelity'] for k,s in scores.items()},'review_unchanged':True,'also_bound_r111_comparison':str(comparison)}
(a/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
