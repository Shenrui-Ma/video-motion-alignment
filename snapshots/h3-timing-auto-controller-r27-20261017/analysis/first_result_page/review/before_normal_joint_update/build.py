from pathlib import Path
import base64,hashlib,json,datetime
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ARC=ROOT/'analysis/postrun/captured/r27_s05_bad1311_auto'
OLD=Path('/Users/researcher/DevProjects/h3-timing-spatial-r3-20261016')
OUT=Path('/Users/researcher/Downloads/H3_自动动作窗口_初步结果_20261017.html')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
gate=json.loads((ARC/'RUN_GATE.json').read_text());assert gate['passed']
assert (ROOT/'analysis/postrun/r27_s05_bad1311_auto_DOWNLOAD.json').exists()
ledger=json.loads((ARC/'DECISION_LEDGER.json').read_text())
priority=ROOT/'analysis/priority_final_outcome'
outcome=json.loads((priority/'SUMMARY.json').read_text())
complete=json.loads((priority/'METRICS_COMPLETE.json').read_text())
assert sha(priority/'SUMMARY.json')==complete['summary_sha256']
assert all(sha(priority/rel)==digest for rel,digest in complete['files'].items())
pose_complete=json.loads((priority/'POSE_COMPLETE.json').read_text())
assert all(sha(priority/rel)==digest for rel,digest in pose_complete['files'].items())
assert outcome['pose_sha256']==pose_complete['pose_sha256']
assert outcome['active_indices']==ledger['active_indices'] and outcome['NFE']==ledger['NFE']
protocol=json.loads((ROOT/'analysis/postrun/PROTOCOL.json').read_text())
assert sha(ROOT/'analysis/postrun/PROTOCOL.json')==outcome['frozen_protocol_sha256']
inventory=json.loads((ARC/'FILE_INVENTORY.json').read_text())
assert sha(ARC/'FILE_INVENTORY.json')==gate['file_inventory_sha256']
files=[('参考视频',ARC/'input/05_real_megumi_v.mp4'),('编辑后视频',OLD/'analysis/pose/raw/r3_s05_native_00001_.mp4'),('编辑＋固定时序引导',OLD/'analysis/pose/raw/r3_s05_full_6to14_00001_.mp4'),('编辑＋自动窗口与启停',ARC/'output/r27_s05_bad1311_auto_00001_.mp4')]
expected=[inventory['input/05_real_megumi_v.mp4']['sha256'],protocol['parents']['bad_native']['video_sha256'],protocol['parents']['bad_fixed_full']['video_sha256'],inventory['output/r27_s05_bad1311_auto_00001_.mp4']['sha256']]
assets=[]
for (label,p),digest in zip(files,expected):
 assert sha(p)==digest
 assets.append({'label':label,'src':'data:video/mp4;base64,'+base64.b64encode(p.read_bytes()).decode(),'sha256':digest,'source':str(p)})
assert assets[-1]['sha256']==outcome['input_sha256']
rows=[]
for r in ledger['rows']:
 d=r['decision'];rows.append({'n':r['denoising_index'],'sigma':r['sigma'],'choice':r['chosen'],'physical':d['physical_intervals'],'bins':d['latent_bins'],'groups':len(d['groups']),'reason':d['reason'],'known':r['summary']['known_denominator']})
methods=['bad_native','bad_fixed_full','auto'];features=['arm_direction','wrist_relative'];windows=protocol['cases'][0]['windows']
metric_rows=[]
for window in windows:
 for feature in features:
  record={'window':window,'feature':feature,'methods':{}}
  for method in methods:
   record['methods'][method]={}
   for conf in ['0.3','0.5']:
    selected=[r for r in outcome['fixed'][method][conf] if r['window']==window and r['feature']==feature]
    assert len(selected)==1
    r=selected[0];record['methods'][method][conf]={k:r[k] for k in ['lag','status','flags']}
  metric_rows.append(record)
common_rows=[]
for conf,rs in outcome['common_support']['bad_native__bad_fixed_full__auto'].items():
 for r in rs:
  if r['region']=='fixed_50_65' and r['feature'] in features:
   common_rows.append({'confidence':conf,'feature':r['feature'],'status':r['status'],'coverage':r['common_valid_fraction'],'errors':{n:v['same_frame_error_on_common_support'] for n,v in r['runs'].items()}})
summary={'snapshot':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'开发样例 1 条｜最终成片独立先行评价已完成；正式完整审计继续核验','nfe':ledger['NFE'],'updates':ledger['Euler_updates'],'rows':rows,'archive_gate_sha256':sha(ARC/'RUN_GATE.json'),'metric_rows':metric_rows,'whole_scan':outcome['whole_scan'],'common_rows':common_rows,'priority_summary_sha256':sha(priority/'SUMMARY.json'),'limitations':['本页是一条已知故障的开发样例。正常种子与全新素材的自动控制结果待完成。','主窗50–65帧、两项姿态特征和两个置信度门均进入±2帧范围。固定Full在主窗仍有更低的同帧姿态误差。','69–81帧在置信度0.5下检测覆盖不足，保留UNKNOWN；全片Auto另有24–39帧左臂约3帧延后。','第5个去噪步触发，第6个去噪步因严格置信度下可见性不足而关闭；后续保持监测。停用本身并不表示当时已完全修复。','固定55/86/105帧可见背景布局和男性编辑；手部细节模糊，精确身份、全片闪烁和重影仍待配对动态评价。姿态误差衡量动作几何与相位。','当前0.5增益门、两次连续观察以及16/32帧扫描尺度是固定的开发超参数。该结果支持这一病例的自动控制可行性；独立算法贡献需要消融与新素材验证。','独立先行评价复用冻结脚本及相同源姿态；正式20个在线观察重放与完整后验另行完成，再核对最终数字一致。']}
text=(HERE/'template.html').read_text().replace('__ASSETS__',json.dumps(assets,ensure_ascii=False)).replace('__DATA__',json.dumps(summary,ensure_ascii=False))
OUT.write_text(text)
(HERE/'manifest.json').write_text(json.dumps({'output':str(OUT),'sha256':sha(OUT),'assets':[{k:v for k,v in a.items()if k!='src'}for a in assets],'gate':summary['archive_gate_sha256'],'priority_summary_sha256':summary['priority_summary_sha256'],'pose_sha256':outcome['pose_sha256'],'source_pose_sha256':outcome['source_pose_sha256'],'metrics_complete_sha256':sha(priority/'METRICS_COMPLETE.json'),'source_files':{n:sha(HERE/n)for n in ['build.py','template.html','check_dom.cjs']},'layout_and_actual_playback':'unassessed; offline DOM and embedded bytes checked separately'},ensure_ascii=False,indent=2))
print(str(OUT))
