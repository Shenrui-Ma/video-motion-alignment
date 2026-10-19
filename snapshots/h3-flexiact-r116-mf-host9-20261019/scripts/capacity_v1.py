"""Read .9 cgroup-v1 capacity without changing limits or scientific parameters."""
import os
import time
from pathlib import Path

GIB = 2**30


def integers(path):
    return {parts[0]: int(parts[1]) for line in Path(path).read_text().splitlines()
            if len(parts := line.split()) == 2}


def limit(value):
    value = int(value)
    if value < 0:
        raise ValueError('negative memory limit')
    return None if value >= 2**60 else value


def snapshot(proc=Path('/proc'), mount=Path('/sys/fs/cgroup/memory'), uid=None):
    proc, mount = Path(proc), Path(mount)
    groups = [line.split(':', 2) for line in (proc / 'self/cgroup').read_text().splitlines()]
    paths = [path for _, controllers, path in groups if 'memory' in controllers.split(',')]
    assert len(paths) == 1 and paths[0].startswith('/') and '..' not in Path(paths[0]).parts
    current = Path(paths[0]); rows = []
    while True:
        folder = mount / str(current).lstrip('/')
        maximum = limit((folder / 'memory.limit_in_bytes').read_text())
        stats = integers(folder / 'memory.stat')
        inherited = limit(stats.get('hierarchical_memory_limit', 2**63))
        effective = min(x for x in (maximum, inherited) if x is not None) if any(
            x is not None for x in (maximum, inherited)) else None
        oom = integers(folder / 'memory.oom_control')
        rows.append({'path': str(current), 'current_bytes': int((folder / 'memory.usage_in_bytes').read_text()),
                     'max_bytes': effective, 'limit_bytes': maximum, 'hierarchical_limit_bytes': inherited,
                     'failcnt': int((folder / 'memory.failcnt').read_text()), 'oom_control': oom})
        if current == Path('/'):
            break
        current = current.parent
    mem = {}
    for line in (proc / 'meminfo').read_text().splitlines():
        key, text = line.split(':', 1); fields = text.split()
        if len(fields) == 2 and fields[1] == 'kB':
            mem[key] = int(fields[0]) * 1024
    vm = integers(proc / 'vmstat')
    pressure_path = proc / 'pressure/memory'
    return {'schema': 'host9-memory-v1', 'uid': os.getuid() if uid is None else uid,
            'unix': time.time(), 'cgroup_version': 1, 'ancestors': rows,
            'host_available_bytes': mem['MemAvailable'], 'host_oom_kill': vm.get('oom_kill'),
            'cumulative_host_oom_counter_available': 'oom_kill' in vm,
            'PSI_observation': pressure_path.read_text() if pressure_path.exists() else None}


def assess(value, required):
    assert required in (8, 12)
    assert value['uid'] == 1016 and value['cgroup_version'] == 1, 'host9 UID/cgroup mismatch'
    assert value['host_available_bytes'] >= 32 * GIB, 'host available below 32 GiB'
    assert value['ancestors'], 'missing memory hierarchy'
    rows = []
    for row in value['ancestors']:
        assert type(row['current_bytes']) is int and row['current_bytes'] >= 0
        assert row['failcnt'] >= 0 and row['oom_control'].get('under_oom') == 0, 'active cgroup OOM'
        remaining = None if row['max_bytes'] is None else row['max_bytes'] - row['current_bytes']
        assert remaining is None or remaining >= required * GIB, 'finite cgroup headroom too small'
        rows.append({'path': row['path'], 'raw_max_headroom_bytes': remaining})
    return {'passed': True, 'raw_required_gib': required, 'host_required_gib': 32,
            'cgroup_high': 'unavailable in cgroup v1', 'unlimited_ancestors_use_host_capacity': True,
            'cache_credit_bytes': 0, 'PSI_observation_only': True, 'rows': rows, 'snapshot': value}


def check(required):
    return assess(snapshot(), required)


def oom_delta(before, after):
    old = {row['path']: row for row in before['ancestors']}
    new = {row['path']: row for row in after['ancestors']}
    assert old.keys() == new.keys(), 'memory hierarchy changed'
    first, last = before['host_oom_kill'], after['host_oom_kill']
    assert (first is None) == (last is None), 'OOM counter availability changed'
    if first is not None:
        assert last >= first, 'OOM counter reset'
    host_delta = None if first is None else last - first
    changed = bool(host_delta)
    rows = {}
    for path, row in new.items():
        assert row['max_bytes'] == old[path]['max_bytes'], 'memory limit changed'
        assert row['failcnt'] >= old[path]['failcnt'], 'memory failure counter reset'
        delta = row['failcnt'] - old[path]['failcnt']
        # A new allocation-limit failure also stops this short batch conservatively.
        changed |= bool(delta) or bool(row['oom_control'].get('under_oom'))
        rows[path] = {'failcnt_delta': delta, 'under_oom': row['oom_control'].get('under_oom')}
    return {'passed': not changed, 'host_oom_kill_delta': host_delta,
            'cumulative_host_oom_counter_available': first is not None,
            'monitoring': 'v1 allocation failures, under_oom snapshots, host capacity, child exit; cumulative host kills when available',
            'rows': rows}
