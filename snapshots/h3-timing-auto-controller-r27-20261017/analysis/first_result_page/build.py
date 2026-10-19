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

# Normal case: archive/runtime evidence only. Its postrun numerical replay may continue.
NORMAL=ROOT/'analysis/postrun/captured/r27_s05_normal1313_auto'
ng=json.loads((NORMAL/'RUN_GATE.json').read_text())
nl=json.loads((NORMAL/'DECISION_LEDGER.json').read_text())
ni=json.loads((NORMAL/'FILE_INVENTORY.json').read_text())
nd=json.loads((ROOT/'analysis/postrun/r27_s05_normal1313_auto_DOWNLOAD.json').read_text())
assert ng['passed'] is True and ng['run_id']=='r27_s05_normal1313_auto'
assert sha(NORMAL/'FILE_INVENTORY.json')==ng['file_inventory_sha256']==nd['original_inventory_sha256']
assert sha(NORMAL/'DECISION_LEDGER.json')==ng['ledger_sha256']
ncase=[c for c in ng['runtime']['cases'] if c['run']==ng['run_id']]
assert len(ncase)==1 and ncase[0]['mask']==[] and ncase[0]['all_OFF_final_exact'] is True
assert ncase[0]['NFE']==ncase[0]['updates']==ncase[0]['observations']==20
assert nl['active_indices']==[] and nl['NFE']==nl['Euler_updates']==20 and len(nl['rows'])==20
assert all(r['chosen']=='native' and not r['decision']['latent_bins'] for r in nl['rows'])
assert ng['additional_checks']['clean_condition_exact'] and ng['additional_checks']['two_stream_noise_actual_exact']
assert all(x['independent_tensor_equal'] for x in ng['additional_checks']['independent_prefix_replays'])
normal_native=Path('/Users/researcher/DevProjects/h3-timing-native-screen-r14-host9-20261016/analysis/pose/raw/r14_s05_seed1313_native_host9_00001_.mp4')
normal_auto=NORMAL/'output/r27_s05_normal1313_auto_00001_.mp4'
def add_asset(label,path,digest):
    assert sha(path)==digest
    assets.append({'label':label,'src':'data:video/mp4;base64,'+base64.b64encode(path.read_bytes()).decode(),'sha256':digest,'source':str(path)})
    return len(assets)-1
normal_ids=[0,add_asset('编辑后视频 · 正常种子',normal_native,protocol['parents']['normal_native']['video_sha256']),add_asset('自动监测 · 全程 OFF',normal_auto,ni[str(normal_auto.relative_to(NORMAL))]['sha256'])]
assert sha(NORMAL/'input/05_real_megumi_v.mp4')==assets[0]['sha256']
summary['normal']={'seed':2026101313,'asset_ids':normal_ids,'NFE':20,'updates':20,'observations':20,'active_indices':[],
    'all_OFF_final_exact':True,'clean_condition_exact':True,'noise_exact':True,
    'prefix_indices':[x['index'] for x in ng['additional_checks']['independent_prefix_replays']],
    'mp4_bytes_equal':sha(normal_native)==sha(normal_auto),
    'gate_sha256':sha(NORMAL/'RUN_GATE.json'),'ledger_sha256':sha(NORMAL/'DECISION_LEDGER.json'),
    'rows':[{'n':r['denoising_index'],'choice':r['chosen'],'known':r['summary']['known_denominator'],'reason':r['decision']['reason']} for r in nl['rows']],
    'scope':'同一源视频的一个已见正常种子；本页核运行/归档门，20点数值重放及最终pose由既有消费者继续。'}

JOINT=Path('/Users/researcher/DevProjects/h3-timing-forward-reverse-r30-20261017/analysis/postrun')
JA=JOINT/'captured/batch';JR=JA/'final/r30_s05_forward_full_reverse_block_6to14'
jdone=json.loads((JA/'CPU_COMPLETE.json').read_text());assert jdone['passed'] is True
jderived=json.loads((JA/'DERIVED_FILES.json').read_text())
assert all(sha(JA/rel)==digest for rel,digest in jderived.items())
jgate=json.loads((JA/'RUN_GATE.json').read_text());jinv=json.loads((JA/'FILE_INVENTORY.json').read_text())
assert jgate['passed'] is True and sha(JA/'FILE_INVENTORY.json')==jgate['file_inventory_sha256']
jdownload=json.loads((JOINT/'DOWNLOAD.json').read_text());assert jdownload['file_inventory_sha256']==jgate['file_inventory_sha256']
js=json.loads((JR/'SUMMARY.json').read_text());jf=json.loads((JR/'FIXED_WINDOWS.json').read_text())['results']
jvideo=JA/'output/r30_s05_forward_full_reverse_block_6to14_00001_.mp4'
jids=[0,2,add_asset('编辑＋正向 Full＋反向 BLOCK',jvideo,jinv[str(jvideo.relative_to(JA))]['sha256'])]
jrows=[]
for window in windows:
 for feature in features:
  rec={'window':window,'feature':feature,'methods':{}}
  for method in ('N','F','B','FB'):
   rec['methods'][method]={}
   for c in ('0.3','0.5'):
    found=[x for x in jf[method][c]['diagnostics'] if x['window']==window and x['feature']==feature]
    assert len(found)==1
    v=found[0];rec['methods'][method][c]={'lag':v['reliable_lag_frames'],'status':v['status'],'flags':v.get('flags',[])}
  jrows.append(rec)
jcommon=[]
for c in ('0.3','0.5'):
 for x in json.loads((JR/f'COMMON_F_FB_{c}.json').read_text())['rows']:
  if x['feature']=='arm_direction' and x['region'] in ('fixed_50_65','fixed_80_92','region_0_140'):
   jcommon.append({'confidence':c,'region':x['region'],'status':x['status'],'coverage':x['common_valid_fraction'],'F':x['runs']['F']['same_frame_error_on_common_support'],'FB':x['runs']['FB']['same_frame_error_on_common_support']})
summary['joint']={'asset_ids':jids,'metric_rows':jrows,'common_rows':jcommon,'gate_sha256':sha(JA/'RUN_GATE.json'),
    'CPU_complete_sha256':sha(JA/'CPU_COMPLETE.json'),'summary_sha256':sha(JR/'SUMMARY.json'),
    'NFE':js['NFE'],'updates':js['Euler_updates'],'F_calls':js['F_calls'],'B_calls':js['B_calls'],
    'quality':'固定55/86/105三帧匿名盲评没有可靠画质偏好；减轻重影为 UNKNOWN。该盲评未完成连续视频质量评价。',
    'whole_scan':{k:{'baseline_counts':v['baseline_counts'],'rows':v['rows']} for k,v in js['whole_scan'].items()}}
summary['status']='同一源视频：1 个困难种子＋1 个正常种子｜自动控制开发验证；另列固定联合干预诊断'
summary['limitations']=[
 '证据来自同一源视频的两个已见种子：困难 seed2026101311 与正常 seed2026101313。R30使用同一个困难种子，属于方法消融。跨源与泛化效果继续验证。',
 '困难样例主窗进入±2帧；69–81帧高置信度检测不足保留UNKNOWN，全片另有24–39帧左臂约3帧延后。固定Full主窗同帧姿态误差更低。',
 '正常样例20次原生观测均未触发Full，最终视频/音频latent与原Native逐位相同。历史逐点核对限于实际留存的8个端点；正式数值重放和最终pose仍由既有消费者完成。',
 '困难样例index5因严格置信度下可见性不足关闭；后续继续监测。UNKNOWN停用与确认已对齐分别记录。',
 '联合F+B主窗方向1/1、腕部2/2帧，但80–92辅助窗方向与腕部均退至4/4帧；它没有优于单独Full。固定三帧盲评对重影改善保留UNKNOWN。',
 '0.5增益门、两次相邻观察、16/32帧尺度是开发超参数；共有姿态模型的两个置信度门不是独立统计证据。',
 '局部反馈、动态停止和同帧参考注意力均有先例。当前结果用于验证自动执行和组件效用，独立方法贡献还需匹配支持/剂量消融与新素材证据。']

text=(HERE/'template.html').read_text().replace('__ASSETS__',json.dumps(assets,ensure_ascii=False)).replace('__DATA__',json.dumps(summary,ensure_ascii=False))
OUT.write_text(text)
(HERE/'manifest.json').write_text(json.dumps({'output':str(OUT),'sha256':sha(OUT),'assets':[{k:v for k,v in a.items()if k!='src'}for a in assets],'gate':summary['archive_gate_sha256'],'priority_summary_sha256':summary['priority_summary_sha256'],'pose_sha256':outcome['pose_sha256'],'source_pose_sha256':outcome['source_pose_sha256'],'metrics_complete_sha256':sha(priority/'METRICS_COMPLETE.json'),'source_files':{n:sha(HERE/n)for n in ['build.py','template.html','check_dom.cjs']},'normal_gate_sha256':summary['normal']['gate_sha256'],'normal_ledger_sha256':summary['normal']['ledger_sha256'],'joint_gate_sha256':summary['joint']['gate_sha256'],'joint_CPU_complete_sha256':summary['joint']['CPU_complete_sha256'],'joint_summary_sha256':summary['joint']['summary_sha256'],'layout_and_actual_playback':'unassessed; offline DOM and embedded bytes checked separately'},ensure_ascii=False,indent=2))
print(str(OUT))
