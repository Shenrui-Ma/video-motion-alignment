"""Copy exact existing R83 source inputs on the destination host; no downloads."""
import argparse
import shutil
from common import *

def materialize(producer):
    producer = Path(producer).resolve()
    results = []
    for name, digest in read(ROOT / 'configs/producer_input_hashes.json').items():
        require(Path(name).name == name, 'unsafe input basename')
        source = producer / 'inputs' / name
        require(source.is_file() and sha(source) == digest, 'producer input differs: ' + name)
        destination = ROOT / 'inputs' / name
        if destination.exists():
            require(sha(destination) == digest, 'existing consumer input differs: ' + name)
        else:
            with source.open('rb') as incoming, destination.open('xb') as outgoing:
                shutil.copyfileobj(incoming, outgoing)
            require(sha(destination) == digest, 'input copy verification failed: ' + name)
        results.append({'file': name, 'sha256': digest})
    return {'passed': True, 'files': results, 'gpu_calls': 0}

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--producer-root', type=Path, required=True); a = p.parse_args()
    print(json.dumps(materialize(a.producer_root), indent=2))
