from pathlib import Path
import json,hashlib,shutil
P=Path(__file__).resolve().parents[1];R=P/'analysis/evaluation';O=Path('/Users/researcher/DevProjects/h3-ivebench-body-metrics-r76-20261018')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
for d in ['scripts','tests','runtime']:
 for src in (O/d).rglob('*'):
  if not src.is_file():continue
  rel=src.relative_to(O);dest=R/rel;dest.parent.mkdir(parents=True,exist_ok=True)
  if d=='runtime':shutil.copyfile(src,dest);continue
  if '__pycache__' in src.parts:continue
  text=src.read_text().replace('r76','r79').replace('R76','R79').replace("'P1'","'P1-local-v1'").replace('SELECTED_5_MANIFEST','SELECTED_2_MANIFEST')
  text=text.replace("('short_0131', 'short_0178', 'short_0090', 'short_0055', 'short_0321')","('short_0144', 'short_0166')").replace('[(56, 44), (124, 121), (107, 105), (90, 85), (56, 49)]','[(107, 104), (124, 123)]')
  text=text.replace("'fixed_denominator': 5","'fixed_denominator': 2").replace('fixed_denominator=5','fixed_denominator=2').replace("report['fixed_denominator'], 5","report['fixed_denominator'], 2").replace('sum(values) / 5 if len(values) == 5','sum(values) / 2 if len(values) == 2').replace('all_five','all_two').replace('fixed_five','fixed_two').replace('five_p1','two_p1').replace('fixed five','fixed two').replace('all five','all two').replace('five source-selected','two source-selected')
  dest.write_text(text)
for d in ['inputs','prepared','tracks','controls','incoming','results','media','audit','configs/prompts']:(R/d).mkdir(parents=True,exist_ok=True)
for src,dest in [('design/INPUT_PLAN.json','configs/INPUT_PLAN.json'),('configs/source_selection/SELECTED_2_MANIFEST.json','configs/SELECTED_2_MANIFEST.json'),('PREPARED_INPUTS_MANIFEST.json','configs/PREPARED_INPUTS_MANIFEST.json'),('design/P1_TEMPLATE.txt','configs/P1_TEMPLATE.txt'),('configs/scientific_contract.json','configs/producer_scientific_contract.json'),('configs/input_hashes.json','configs/producer_input_hashes.json'),('design/NEXT_EVALUATION_RULES.txt','configs/NEXT_EVALUATION_RULES.txt')]:shutil.copyfile(P/src,R/dest)
for src in (P/'configs/prompts').glob('*.txt'):shutil.copyfile(src,R/'configs/prompts'/src.name)
shutil.copyfile(O/'configs/R63_RUNTIME_INHERITANCE.json',R/'configs/R63_RUNTIME_INHERITANCE.json')
put(R/'configs/SELECTION_BINDING.json',{'source_selection_sha256':sha(R/'configs/SELECTED_2_MANIFEST.json'),'input_plan_sha256':sha(R/'configs/INPUT_PLAN.json'),'producer_plan_sha256':sha(P/'design/INPUT_PLAN.json')})
p=R/'scripts/common.py';s=p.read_text().replace("selection['source_selection_sha256'] == sha(ROOT / 'configs/SELECTED_2_MANIFEST.json')","read(ROOT / 'configs/SELECTION_BINDING.json')['source_selection_sha256'] == sha(ROOT / 'configs/SELECTED_2_MANIFEST.json')");p.write_text(s)
paths=read(O/'configs/paths.json');remote=read(P/'configs/runtime.json')['remote_root'];paths.update(schema='r79-consumer-host-paths-v1',local=str(R),remote41=remote+'/analysis/evaluation',remote9='/data5/researcher/h3_runs/timing_local_scene_r79_20261018/analysis/evaluation',producer_remote41=remote,producer_remote9='/data5/researcher/h3_runs/timing_local_scene_r79_20261018',tracker_capacity_status='UNPROFILED_123_VALID_FRAMES_CONSERVATIVE_BOOTSTRAP',tracker_capacity_note='24GiB conservative engineering threshold; actual123-frame source capacity must be recorded by root tracker. No prior measured123-frame claim.');put(R/'configs/paths.json',paths)
p=R/'scripts/make_showcase.py';s=p.read_text().replace('五条新素材','两条局部编辑').replace('五条源视频筛选出的官方编辑任务：两条衣服颜色编辑、两条风格编辑和一条添加花束。两人场景保留各自角色；花束造成的合法遮挡单独记录，两组均使用相同的 H3 格式提示词。','两条官方原场景局部编辑任务：背景屏幕换成数字广告牌、狗换成猫。先检查指定编辑是否完成、未编辑人物与场景是否保留、动作内容是否保留，再评价合格配对的时序。合法遮挡和不可观测事件单独记录。两组均使用相同的 P1-local-v1 提示词。').replace('固定分母为5','固定分母为2');p.write_text(s)
put(R/'audit/INHERITANCE.json',{'parent_consumer':str(O),'parent_freeze_sha256':sha(O/'CONSUMER_FREEZE.json'),'numerics':'all inherited runtime bytes unchanged','task_fidelity_rules_sha256':sha(R/'configs/NEXT_EVALUATION_RULES.txt'),'no_generated_outputs_yet':True})
print(str(R))
