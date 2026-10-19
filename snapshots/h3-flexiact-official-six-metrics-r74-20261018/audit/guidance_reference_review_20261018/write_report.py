from pathlib import Path
import json,hashlib,math
from PIL import Image
root=Path('/Users/researcher/DevProjects/h3-flexiact-official-six-metrics-r74-20261018/audit/guidance_reference_review_20261018')
base=Path('/Users/researcher/DevProjects')
prompt_audit=root.parent/'prompt_protocol_review'
refs={
 'minimax_readme': 'https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/README.md#local-deployment-of-h3-base',
 'prompt_guide': 'https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/references/ref-en.txt',
 'comfy_template': 'https://github.com/Comfy-Org/workflow_templates/blob/e7cd011d4ded3411c2f481200544f0be6fdc962e/templates/video_minimax_h3_r2v.json',
 'comfy_guide': 'https://docs.comfy.org/tutorials/video/minimax/minimax-h3',
 'comfy_weights': 'https://huggingface.co/Comfy-Org/MiniMax-H3/tree/e5eb578a89295337b8ff433a035929ce0279e0b6',
 'sglang_sampling': 'https://github.com/sgl-project/sglang/blob/main/python/sglang/multimodal_gen/configs/sample/minimax_h3.py',
}
rows=[]
for exp in ('h3-timing-flexiact-prompt-pair-r72-20261018','h3-timing-flexiact-official-six-r74-20261018'):
 for p in sorted((base/exp/'inputs').glob('target*')):
  if p.suffix.lower() not in ('.jpg','.jpeg','.webp','.png'):continue
  with Image.open(p) as im:w,h=im.size
  modes={}
  for mode in ('match','max'):
   scale=min(1.,math.sqrt(1152*768/(w*h))) if mode=='match' else min(1.,2048/min(w,h))
   modes[mode]=[max(32,round(w*scale/32)*32),max(32,round(h*scale/32)*32)]
  rows.append({'experiment':exp,'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'original_wh':[w,h],**modes,'kind':'CPU dimension calculation from frozen node; max not GPU-tested'})
api=json.loads((root/'official/comfy_model_api.json').read_text())
old=json.loads((base/'h3-timing-architecture-r2-20261016/configs/model_hashes_host41.json').read_text())
weights=[]
for s in api['siblings']:
 k=s['rfilename']
 if k in old:
  weights.append({'file':k,'release_sha256':s.get('lfs',{}).get('sha256'),'archived_actual_sha256':old[k]['sha256'],'equal':s.get('lfs',{}).get('sha256')==old[k]['sha256'],'scope':'existing inherited archival hash, no new remote model rehash'})
result={'scope':'CPU/read-only review; no scientific/configuration changes or new inference','sources':refs,'official_comfy_template_revision':'e7cd011d4ded3411c2f481200544f0be6fdc962e','template_commit_date':'2026-09-28T13:58:12Z','weight_release_revision':api['sha'],'weight_comparison':weights,'image_sizes':rows,'clear_cfg_or_shift_misuse_found':False,'documented_sampler_difference':{'ours':'Euler 20','recommended_comfy_template':'res_multistep / simple / 20'},'prompt_difference':'P1 binds identity to Subject1/Picture1 but assigns motion chiefly to Video1; guide permits Subject1 to combine Picture1 appearance with Video1 motion and keeps action as Subject content. Semantic precedence is already stated in summary/details; causal failure attribution untested.','suggested_minimal_diagnostic':'Fresh same-host Native Euler20 vs res_multistep20 on frozen chest__game_man_5 P1, same media/AVnoise/directconditions/sigma grid; identity across full147valid frames first. No temporal intervention and no simultaneous prompt/size/CFG changes.'}
(root/'FACTS.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
report='''H3 Ref2VA guidance、参考图与 P1 提示核对（只读，2026-10-18）

结论
公开资料与现有图支持 BasicGuider/CFG=1 和 video/audio shift=12/3。没有找到“必须把 CFG 调大才能替换人物”的官方依据。现在最清楚的采样差异是 Euler20 与推荐 Comfy 模板的 res_multistep/simple20。它说明我们尚未完整复现推荐采样器，尚不能归因为身份替换失败。当前运行与参数均未改动。

1. 模型与 CFG
MiniMax 固定官方 README 第191行明确说明公开 checkpoint 已做 CFG 蒸馏。它列出的 Comfy 官方 R2V 模板（2026-09-28提交 e7cd011d…）使用 BasicGuider，并加载与我们相同的 minimax_h3_ref2va_pruned_int8_convrot.safetensors / qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors。R72/R74 node1/2/7匹配这些类型和文件名。
额外核 HuggingFace 官方 Comfy 仓库发布元数据：上述权重 SHA 与我们继承档案的实际 SHA 完全相同（9255f52b…5779 / 35a88d51…f2c6；详见 FACTS.json）。这里只核既有实测归档，没有重新读取20GB权重。
Comfy BasicGuider只设置positive；CFGGuider默认self.cfg=1.0。我们采用公开的蒸馏推理形式。把它理解为“没有参考引导”会混淆外部双分支CFG与模型已有条件预测。SGLang当前采样配置也固定guidance_scale=1、negative_prompt=None；其默认50步属于另一后端配方，不能据此把Comfy20步判成错误。

2. 采样步与 shifts
官方推荐Comfy模板 node123=res_multistep、124=simple/20、126=BasicGuider。R72/R74 node8=Euler、9=手写21个sigma点，20次更新；没有Turbo LoRA。两者的solver确实不同。模型定义与已归档MiniMaxH3SigmaShift原节点的默认值均12/3，现有图41同值。历史配方已经核过手写表与同shift的Simple20仅浮点舍入差；无需重复解释为双重shift。
官方Comfy文档建议重参考任务用20步，仍漂移可试25；这只是待测选项。我们不能把“更多步必修复身份”写成结论。没有本轮新采样结果。

3. 参考强度与输入是否接错
当前MiniMaxH3ReferenceToVideo原生schema没有每张图/每段视频独立的strength或CFG旋钮。另一个Fun ControlNet节点的strength不属于这条图。我们的alpha1只用于单独时序路由；Native下没有路由写入，它也不是官方人物参考强度。
H3EventAuditReference第187–190行把真实ref_image_0和ref_video_0同时传给原生节点，并固定ref_image_size=match。它是官方模板默认值。match按生成像素面积缩小图像；max保留更高参考分辨率至2048短边上限，两个分支都不主动放大低分辨率原图。官方节点说明max面向更高身份保真，但我们未实测它解决这些失败。
实际R72 fitness P1 conditioning收据已保存目标图1248×704进入Qwen和VAE，以及完整158帧视频进入VAE；语义视频2fps是原生Qwen采样，不能当作VAE只见2fps。
尺寸诊断：game_man_5原1920×1080，match1248×704，max1920×1088；movie_man_9为1152×768对1248×832。R74 game_man_1/game_man_4/movie_man_5在两个选项下像素尺寸完全相同。因而max不是普适的“调高权重”，对小图甚至没有任何尺寸变化。所有目标尺寸见FACTS.json。

4. 提示角色
官方ref-en第55–58行示范同一Subject同时绑定Picture外观与Video动作；第76–88行区分Video整体结构与Subject可见内容，动作属于可复用Subject内容。R72/R74 P1已清楚规定Picture1提供目标身份/衣服/风格/场景，Video1提供完整动作/时刻；summary和详细描述明确由目标人执行源动作。输入标签与真实图/视频顺序匹配。
已知格式差别：subject_definitions只把外观写进Subject1，动作主要挂在Video1；更贴官方的写法可将Picture外观和Video动作同时写入Subject1。该差别有明确文本依据，是否造成源人物残留需要单因素实验。源caption仍含原人物性别/衣着，这是源描述，不能直接说它覆盖了明确的目标身份指令。
对允许目标图场景的FlexiAct动作迁移，[reference generation]符合官方任务定义。Picture场景不是错误。chest要求目标图场景内完成源健身器械交互，仍可能增加任务难度。我们的P1为自行构造的Context-IR样式文本；官方托管多阶段Context-IR未在本地运行，因此不能宣称复现其完整质量。

最小诊断建议（本轮未实施）
仅对已失败的chest__game_man_5做同机fresh Native二组：原Euler20 vs res_multistep20。固定现有P1全文、素材、初始AV噪声、条件和同一sigma网格；关闭时序干预。先核完整147有效帧的目标身份/原人物残留和动作内容，再看时序。此对照只问推荐solver是否影响该失败；不同时改CFG、提示词、参考分辨率或步数。单例若改善仍只够决定后续复核，不构成普遍修复。

证据位置
- 官方说明：official sources见FACTS.json；固定MiniMax README在 ../prompt_protocol_review/official/README.md:191,220–228。
- 官方prompt：../prompt_protocol_review/official/skills/h3-prompt-writing/references/ref-en.txt:39–88,129–143,155–207。
- 固定Comfy模板：official/video_minimax_h3_r2v.json，节点123/124/126/127/128/136。
- 原生Ref2V：../prompt_protocol_review/actual_code/host41/comfy_extras/nodes_minimax_h3.py:242–350,366–405（运行环境原档）。
- R74桥接：h3-timing-flexiact-official-six-r74-20261018/extensions/H3EventAudit/__init__.py:178–190。
- R72真实条件：h3-timing-flexiact-prompt-pair-r72-20261018/audit/consumer/incoming/fitness__game_man_5/p1_conditioning.json。
- R72/R74 configs/graphs与design/P1_TEMPLATE.txt、configs/scientific_contract.json。
- BasicGuider定义读本机ComfyUI-dev/comfy_extras/nodes_custom_sampler.py:797–820、comfy/samplers.py:1188–1201；此辅助解释不声称本机整个Core和41逐字相同。
'''
(root/'REPORT.txt').write_text(report)
paths=[root/'REPORT.txt',root/'FACTS.json',root/'write_report.py',*sorted((root/'official').glob('*'))]
manifest={'files':[{'path':str(p.relative_to(root)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in paths if p.is_file()]}
(root/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'report':str(root/'REPORT.txt'),'report_sha256':hashlib.sha256((root/'REPORT.txt').read_bytes()).hexdigest(),'facts_sha256':hashlib.sha256((root/'FACTS.json').read_bytes()).hexdigest(),'weights_all_equal':all(w['equal'] for w in weights),'weight_count':len(weights),'targets':len(rows)},indent=2))
