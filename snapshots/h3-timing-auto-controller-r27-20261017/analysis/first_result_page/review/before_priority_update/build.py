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
files=[('参考视频',ARC/'input/05_real_megumi_v.mp4'),('编辑后视频',OLD/'analysis/pose/raw/r3_s05_native_00001_.mp4'),('编辑＋固定时序引导',OLD/'analysis/pose/raw/r3_s05_full_6to14_00001_.mp4'),('编辑＋自动窗口与启停',ARC/'output/r27_s05_bad1311_auto_00001_.mp4')]
assets=[]
for label,p in files:assets.append({'label':label,'src':'data:video/mp4;base64,'+base64.b64encode(p.read_bytes()).decode(),'sha256':sha(p),'source':str(p)})
rows=[]
for r in ledger['rows']:
 d=r['decision'];rows.append({'n':r['denoising_index'],'sigma':r['sigma'],'choice':r['chosen'],'physical':d['physical_intervals'],'bins':d['latent_bins'],'groups':len(d['groups']),'reason':d['reason'],'known':r['summary']['known_denominator']})
summary={'snapshot':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'首条开发样例，最终独立姿态评估进行中','nfe':ledger['NFE'],'updates':ledger['Euler_updates'],'rows':rows,'archive_gate_sha256':sha(ARC/'RUN_GATE.json'),'limitations':['这是同源开发样例；新素材和正常种子的结果仍在处理中。','第5个去噪步触发，第6个去噪步因严格置信度下可见性不足而关闭。','中间端点动作时差约2帧；最终同帧表现、形状和重影需结合后验评价。','当前.5增益门、2次连续观察以及16/32帧扫描尺度是预设规则。','每步都有端点解码和姿态读取，本轮总耗时约90分钟，含审计开销。']}
text=(HERE/'template.html').read_text().replace('__ASSETS__',json.dumps(assets,ensure_ascii=False)).replace('__DATA__',json.dumps(summary,ensure_ascii=False))
OUT.write_text(text)
(HERE/'manifest.json').write_text(json.dumps({'output':str(OUT),'sha256':sha(OUT),'assets':[{k:v for k,v in a.items()if k!='src'}for a in assets],'gate':summary['archive_gate_sha256']},ensure_ascii=False,indent=2))
print(str(OUT))
