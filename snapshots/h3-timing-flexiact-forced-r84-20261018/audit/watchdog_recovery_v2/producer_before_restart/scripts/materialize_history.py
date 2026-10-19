"""Copy the two original noise caches within .41 and verify exact original bytes."""
import argparse
import os
from pathlib import Path
import shutil
from r84_contract import ROOT, read, sha, require, registry
from execution_gate import atomic, historical_evidence


def prepare(root=ROOT):
    root = Path(root)
    require(root == Path(read(root / 'configs/runtime.json')['remote_root']), 'actual remote root required')
    jobs, order = registry(root); rows = []
    (root / 'audit').mkdir(exist_ok=True)
    for run in order:
        c = jobs[run]['case']; source = Path(c['baseline_root']) / 'audit' / (c['baseline_noise_pair_id'] + '_noise.pt')
        expected = read(root / 'configs/HISTORICAL_BINDINGS.json')[c['source_id']]['files']['audit/' + source.name]['sha256']
        require(sha(source) == expected, 'original noise changed')
        target = root / 'audit' / source.name
        if not target.exists():
            temporary = target.with_name(target.name + f'.{os.getpid()}.tmp')
            with source.open('rb') as before, temporary.open('xb') as after:
                shutil.copyfileobj(before, after)
            require(sha(temporary) == expected, 'copied noise differs')
            os.link(temporary, target); temporary.unlink()
        require(not target.is_symlink() and sha(target) == expected, 'existing copied noise differs')
        rows.append(historical_evidence(run, root))
    result = {'passed': True, 'new_GPU_processes': 0, 'historical_runs': rows}
    atomic(root / 'audit/HISTORICAL_MATERIALIZATION.json', result)
    return result


if __name__ == '__main__':
    import json
    print(json.dumps(prepare(), indent=2))
