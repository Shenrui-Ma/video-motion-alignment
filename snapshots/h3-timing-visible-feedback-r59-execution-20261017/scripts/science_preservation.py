"""Verify candidate mathematics/observer bytes and enumerate administrative edits."""
import copy
import re
from pathlib import Path
from execution_contract import ROOT, read, sha, require
from r59_contract import REMOTE, ORIGINAL_REMOTE


def check(root=ROOT):
    root = Path(root)
    candidate = root / 'candidate'
    excluded = {'scripts/preflight.py', 'scripts/prepare_candidate.py', 'scripts/seal_cpu.py'}
    checked = []
    for folder in ('scripts', 'extensions'):
        for path in sorted((candidate / folder).rglob('*.py')):
            relative = str(path.relative_to(candidate))
            if relative in excluded:
                continue
            expected = path.read_text().replace(ORIGINAL_REMOTE, str(REMOTE))
            if relative == 'extensions/H3AutomaticWindowRouter/transport.py':
                expected, count = re.subn(r"^PROTOCOL_SHA='[0-9a-f]+'$", 'PROTOCOL_SHA=' + repr(sha(root / 'configs/protocol.json')), expected, flags=re.MULTILINE)
                require(count == 1, 'candidate protocol constant missing')
                expected = expected.replace('import hashlib,json,os,signal,subprocess,threading,time', 'import hashlib,json,os,signal,subprocess,sys,threading,time')
                fix_path = root / 'operations_snapshot/r50_recovery/transport.py'
                require(sha(fix_path) == '0bdacdff50328e12057778e2deb14b0dbffe647f441e534c37ed3ca962cbf108', 'reviewed R50 process binding fix changed')
                own_fix_path = root / 'operations_snapshot/r59_recovery/process_transport_prefix.py'
                require(sha(own_fix_path) == 'b364456d87b4f35b7c46e7c01b36eb57510d4a4276ea890c4f725caa959bd837', 'R59 administrative transport fix changed')
                fix = own_fix_path.read_text()
                expected = (expected[:expected.index('def identity(pid):')] +
                            fix +
                            expected[expected.index('def require_parent_closure('):])
            elif relative == 'extensions/H3AutomaticWindowRouter/__init__.py':
                expected = expected.replace('r55_short_0210_seed2026101701_auto', 'r59_short_0210_seed2026101701_visible_only')
            elif relative == 'extensions/H3EventAudit/__init__.py':
                expected = expected.replace('from r55_contract', 'from r59_contract')
            elif relative == 'extensions/H3PairAudit/__init__.py':
                expected = expected.replace('from r55_contract', 'from r59_contract')
                expected = expected.replace("if source_run_id != 'r55_'+row['case']['source_id']+'_shared':", "if source_run_id != run_id+'_shared':")
                expected = expected.replace('R50 source-conditioning identity mismatch', 'R59 per-arm source-conditioning identity mismatch')
            require((root / relative).read_text() == expected, 'candidate production code changed beyond declared administrative edits: ' + relative)
            checked.append(relative)
    actual = copy.deepcopy(read(root / 'configs/protocol.json'))
    expected = copy.deepcopy(read(candidate / 'configs/protocol.json'))
    for value in (actual, expected):
        value.pop('cases')
        value.pop('preparation_status')
        value['prefix'].pop('availability')
    require(actual == expected, 'candidate observer/actuator/protocol parameters changed')
    actual = copy.deepcopy(read(root / 'configs/scientific_contract.json'))
    expected = copy.deepcopy(read(candidate / 'configs/scientific_contract.json'))
    for value in (actual, expected):
        for key in ('cases', 'case_order', 'continuous', 'status', 'paired_parent_status'):
            value.pop(key, None)
    require(actual == expected, 'four-arm scientific contract changed')
    return {'passed': True, 'checked_candidate_code_files': len(checked), 'checked_files': checked,
            'administrative_differences': ['task-owned absolute root', 'protocol SHA after actual-parent publication',
                'Comfy node default ID', 'contract module name', 'per-arm shared-conditioning identity binding',
                'reviewed R50 child argv binding and primary-error preservation']}
