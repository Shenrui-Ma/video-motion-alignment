"""Read-only CPU verification of the frozen consumer and its producer origin."""
import ast, json, sys
from pathlib import Path
from common import ROOT, read, sha, require, verify_static

def main():
    cfg = verify_static()
    producer = Path(cfg['producer_local'])
    manifest = read(ROOT/'configs/producer_deploy_manifest.json')
    require(sha(producer/'deploy_manifest.json') == cfg['producer_seal_sha256'], 'local producer seal differs')
    for name, row in manifest['files'].items():
        require(sha(producer/name) == row['sha256'], 'producer file differs: '+name)
    mappings = {'producer_runtime.json':'configs/runtime.json', 'scientific_contract.json':'configs/scientific_contract.json',
                'PREREGISTERED_EVENTS.json':'design/PREREGISTERED_EVENTS.json'}
    for local, parent in mappings.items():
        require(sha(ROOT/'configs'/local) == sha(producer/parent), 'copied producer config differs')
    for graph in (ROOT/'configs/graphs').glob('*.json'):
        require(sha(graph) == sha(producer/'configs/graphs'/graph.name), 'copied graph differs')
    for folder in ('scripts', 'tests'):
        for file in (ROOT/folder).glob('*.py'):
            ast.parse(file.read_text())
    require('torch' not in sys.modules, 'CPU preparation imported torch')
    require(not (ROOT/'incoming/actual').exists(), 'preparation preflight expected no actual result yet')
    print(json.dumps({'passed':True, 'producer_files_verified':len(manifest['files']),
          'consumer_files_verified':len(read(ROOT/'CONSUMER_FREEZE.json')['files']),
          'producer_seal_sha256':cfg['producer_seal_sha256'], 'consumer_seal_sha256':sha(ROOT/'CONSUMER_FREEZE.json'),
          'GPU_started':False,'actual_results_present':False}))

if __name__ == '__main__':
    main()
