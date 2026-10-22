"""Load the pinned existing consumer; variant facts come only from its manifest."""
from pathlib import Path
import hashlib
import json
import re


def load(module, scope):
    root = Path(scope['__file__']).resolve().parents[1]
    contract = json.loads((root / 'configs/contract.json').read_text())
    manifest = json.loads((root / 'configs/SHARED_CODE.json').read_text())
    namespace = contract['namespace']
    assert re.fullmatch(r'r[0-9]+', namespace)
    reference = manifest['modules'][module]
    path = Path(reference['file'])
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == reference['sha256']
    code = data.decode().replace('r120', namespace).replace('R120', namespace.upper())
    if module == 'preflight':
        assert code.count("len(science['cases'])==6") == 1
        code = code.replace("len(science['cases'])==6", "len(science['cases'])==2*len(SOURCES)")
    if module in ('render_native', 'render_pair'):
        old = namespace.upper() + '固定3个来源：红酱替换、添加手帕、上衣改黑；1条完整原片、2条六秒片段。全部只输入参考视频。'
        assert code.count(old) == 1
        code = code.replace(old, contract['display_description'])
        assert code.count("'fixed_source_denominator':3") == 1
        code = code.replace("'fixed_source_denominator':3", "'fixed_source_denominator':config()['fixed_source_denominator']")
    exec(compile(code, str(path), 'exec'), scope)
    if module == 'common':
        scope['SOURCES'] = tuple(contract['source_order'])

        def verify_prompt(row, graph=None):
            require = scope['require']
            require(row['prompt_version'] == 'IVEBench-edit-with-generic-retention-v1', 'prompt format label differs')
            require(hashlib.sha256(row['prompt'].encode()).hexdigest() == row['expected_prompt_sha256'], 'frozen task/reference/retention prompt changed')
            require(row['original_task']['edit_prompt'] in row['prompt'], 'official edit instruction missing')
            if graph is not None:
                require(graph['5']['inputs']['prompt'] == row['prompt'], 'actual graph prompt differs')

        scope['verify_official_prompt'] = verify_prompt
