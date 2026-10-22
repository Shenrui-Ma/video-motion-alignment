"""Inject only the host-specific capacity reader into the frozen tracker wrapper."""
import sys
from pathlib import Path
import capacity_v1
from admin_common import ROOT, load, save, sha, verify


def main():
    assert sys.argv[1] == '--package'
    package = verify(sys.argv[2]); del sys.argv[1:3]
    sys.path.insert(0, str(package / 'scripts'))
    sys.modules['mf_capacity'] = capacity_v1
    wrapper = load('host9_frozen_tracker_wrapper', package / 'scripts/track_shared.py')
    control = Path(sys.argv[sys.argv.index('--control') + 1])
    # The original ready/go handshake is retained; this extra binding identifies this entry.
    original = wrapper.register
    def register(path, arguments):
        record = original(path, arguments)
        save(control / 'HOST9_ADMIN_BINDING.json', {'entry_sha256': sha(__file__),
             'administrative_seal_sha256': sha(ROOT / 'ADMIN_FREEZE.json'),
             'consumer_freeze_sha256': sha(package / 'CONSUMER_FREEZE.json'),
             'capacity_reader_sha256': sha(capacity_v1.__file__)})
        return record
    wrapper.register = register
    wrapper.main()


if __name__ == '__main__':
    main()
