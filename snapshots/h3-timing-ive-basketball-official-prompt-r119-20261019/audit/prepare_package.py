"""Clone the reviewed R117 lifecycle; scientific change is exact official prompt."""
from pathlib import Path
import copy, hashlib, json, sys, time

R = Path(__file__).resolve().parents[1]
P = R.parent / 'h3-timing-ive-basketball-framing-repair-r117-20261019'
REMOTE = '/home/researcher/h3_runs/timing_ive_basketball_official_prompt_r119_20261019'

def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')

manifest = read(P / 'deploy_manifest.json')
origins = {}
for rel, row in manifest['files'].items():
    p = P / rel
    assert sha(p) == row['sha256'], rel
    target = rel.replace('r117_contract.py', 'r119_contract.py')
    target = target.replace('graphs/r117_', 'graphs/r119_')
    q = R / target
    q.parent.mkdir(parents=True, exist_ok=True)
    data = p.read_bytes()
    if not rel.startswith(('source_snapshot/', 'design/R110_EVIDENCE/')):
        data = data.decode().replace('r117', 'r119').replace('R117', 'R119').encode()
    q.write_bytes(data)
    origins[target] = {'source': str(p), 'source_sha256': sha(p)}

for p in (P / 'inputs').iterdir():
    if p.is_file():
        q = R / 'inputs' / p.name
        q.parent.mkdir(exist_ok=True)
        q.write_bytes(p.read_bytes())

for rel in ['deploy_manifest.json', 'configs/runtime.json', 'configs/scientific_contract.json',
            'configs/graphs/r117_short_0114_seed2026101701_native.json',
            'configs/graphs/r117_short_0114_seed2026101701_forced.json']:
    q = R / 'source_snapshot/r117' / rel
    q.parent.mkdir(parents=True, exist_ok=True)
    q.write_bytes((P / rel).read_bytes())

science = read(R / 'configs/scientific_contract.json')
prompt = science['cases'][0]['original_task']['edit_prompt']
assert prompt == 'Replace the basketball with a neon-lit ball'
pf = R / 'configs/prompts/short_0114.txt'
pf.write_text(prompt)
old_prompt = read(P / 'configs/scientific_contract.json')['cases'][0]['prompt']
contract = R / 'scripts/r119_contract.py'
t = contract.read_text().replace(old_prompt, prompt).replace('frame-preservation-short-v1', 'official-edit-prompt-verbatim-v1')
t = t.replace('R110 numerical inputs with one approved framing prompt', 'R110 numerical inputs with the exact official edit_prompt')
t = t.replace("require(case['original_task'] == original['original_task'] and case['clip'] == original['clip'], 'official task or source clip changed')", "require(case['original_task'] == original['original_task'] and case['clip'] == original['clip'], 'official task or source clip changed')\n        require(case['prompt'] == case['original_task']['edit_prompt'], 'official edit_prompt must be verbatim')")
contract.write_text(t)

runtime = read(R / 'configs/runtime.json')
runtime.update(remote_root=REMOTE, port=8583, profile='host9_gpu0_r119_normal_reserve8',
               profile_scope='R117 original inputs and numerical settings; exact official edit_prompt. Native task review then same-prompt fixed6..14.')
put(R / 'configs/runtime.json', runtime)
put(R / 'configs/admission.json', {'ready_for_launch': False, 'scope': 'own_user_video_jobs', 'existing_comfy_port': None, 'permitted_compute_processes': []})
science['schema'] = 'r119-basketball-official-prompt-v1'
science['prompt_version'] = 'official-edit-prompt-verbatim-v1'
science['evaluation']['adaptation'] = 'Official short_0114 video and verbatim edit_prompt; Native task acceptance then same-prompt fixed6..14. All105valid frames.'
science['evaluation']['rules_sha256'] = sha(R / 'design/SOURCE_ACCEPTANCE.json')
science['scope_note'] = 'Compared with R117 only the text prompt changes. No extra action, timing, camera or reference-label clauses. Native task review precedes guidance.'
for c in science['cases']:
    c.update(prompt=prompt, prompt_sha256=sha(pf), prompt_version=science['prompt_version'])
put(R / 'configs/scientific_contract.json', science)
binding = read(R / 'configs/parent_bindings.json')
binding['prompt_sha256'] = sha(pf)
binding['r117_seal_sha256'] = sha(P / 'deploy_manifest.json')
binding['r117_science_sha256'] = sha(P / 'configs/scientific_contract.json')
put(R / 'configs/parent_bindings.json', binding)
put(R / 'configs/predecessor.json', {'schema':'r119-actual-predecessor-v1', 'required': [{
    'key':'R117', 'remote_root': read(P / 'configs/runtime.json')['remote_root'],
    'producer_seal_sha256':sha(P / 'deploy_manifest.json'),
    'runtime_sha256':sha(P / 'configs/runtime.json'),
    'kind':'screen', 'required_sources':['short_0114']}],
    'scheduling':'R117 Native task review and exact release precede R119 on GPU0. Root registers any other owned active GPU as a peer; total own .9 GPUs at most two.'})

sys.path.insert(0, str(R / 'scripts'))
import r119_contract as c
for case in science['cases']:
    put(R / 'configs/graphs' / (case['run_id'] + '.json'), c.expected_graph(R, case))

test = R / 'tests/test_basketball_contract.py'
t = test.read_text()
start = t.index('    def test_prompt_preserves_original_head_visibility(self):')
end = t.index('    def test_expected_visual_inputs_and_noise(self):', start)
t = t[:start] + '''    def test_prompt_is_verbatim_official_edit_instruction(self):
        science=c.read(ROOT/'configs/scientific_contract.json')
        for case in science['cases']:
            self.assertEqual(c.PROMPT,case['original_task']['edit_prompt'])
            graph=c.read(ROOT/'configs/graphs'/(case['run_id']+'.json'))
            self.assertEqual(graph['5']['inputs']['prompt'],case['original_task']['edit_prompt'])
        self.assertEqual(c.PROMPT,'Replace the basketball with a neon-lit ball')
        self.assertIn('Source opening already crops the head',c.read(ROOT/'design/SOURCE_ACCEPTANCE.json')['source_observation'])

''' + t[end:]
test.write_text(t)

plan = '''R119：IVEBench 篮球外观编辑，官方提示词复核

唯一文本输入逐字使用 benchmark 的 edit_prompt：
Replace the basketball with a neon-lit ball

参考视频、预处理、seed2026101701、Euler20/CFG1/原sigma、H3权重、加速kernel、1312×736画布、105有效/107生成帧均沿用R117。Native完成后审核原人物/场景、球外观、相机朝向和构图、运球动作；任务成立后同prompt生成固定6..14引导版。两版使用相同初始AV噪声，前6步预测必须逐值一致。所有实际输出保留。

源片开头本来裁切头部；按原视频逐帧可见内容验收。比较输出统一去除模型补边(x16,y8,w1280,h720)，全部105有效帧参与审阅和评分。遮挡/画外动作单独记录。Native失败时root可决定跳过guided。

当前数学实现逐字复用R117：alpha1、50层、去噪zero-based6..14、保留reference总注意力质量并改为同时间reference读出。本轮检验官方原文下基本编辑任务与配对效果。

执行于.9 GPU0/port8583，继承已验证的R117生命周期和精确PID释放。R117实际complete+release是前置；root批准本包和当前peer登记后启动。至多两张自有GPU。原始x0张量保留远端，小JSON/MP4由独立consumer收取。
'''
(R / 'design/EXECUTION_PLAN.txt').write_text(plan)
put(R / 'design/OFFICIAL_PROMPT_BINDING.json', {'schema':'r119-official-prompt-binding-v1',
    'task_id':114, 'source_id':'short_0114', 'field':'original_task.edit_prompt',
    'prompt':prompt, 'prompt_utf8_sha256':sha(pf), 'source_definition_file':'design/CASE_DEFINITION.json',
    'source_definition_sha256':sha(R/'design/CASE_DEFINITION.json'),
    'r117_parent_seal_sha256':sha(P/'deploy_manifest.json'),
    'scientific_change':'Only prompt text; numerical method/input/seed/geometry unchanged.'})

for d in ['logs','processes','output','input','analysis/postrun/short_0114']:
    (R / d).mkdir(parents=True, exist_ok=True)

put(R / 'audit/INHERITED_BYTE_BINDINGS.json', {'schema':'r119-source-file-origins-v1', 'files':origins,
    'note':'Cloned reviewed R117; runtime/module identifiers and official prompt bindings only. Numerical kernels byte equal.'})
c.registry()
print(json.dumps({'root':str(R),'prompt':prompt,'inherited_files':len(origins),'gpu_started':False},indent=2))
