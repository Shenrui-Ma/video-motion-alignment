"""Separate administrative seal; the previously sealed MF packages remain intact."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + str(os.getpid()) + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def verify(package):
    seal = read(ROOT / 'ADMIN_FREEZE.json')
    assert all(sha(ROOT / name) == value for name, value in seal['files'].items()), 'administrative seal changed'
    package = Path(package).resolve()
    assert str(package) in seal['packages'], 'unregistered package'
    assert sha(package / 'CONSUMER_FREEZE.json') == seal['packages'][str(package)], 'consumer seal changed'
    frozen = read(package / 'CONSUMER_FREEZE.json')
    assert all(sha(package / name) == digest for name, digest in frozen['files'].items())
    return package
