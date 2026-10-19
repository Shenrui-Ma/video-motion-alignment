"""Administrative capacity accounting; no CUDA, memory reclamation or limit changes."""
import copy
import json
import sys
import time
from pathlib import Path

GIB = 2**30
POLICY = {
    'expected_uid': 1004,
    'required_parent': '/user.slice',
    'expected_high_bytes': 100 * GIB,
    'expected_max_bytes': 112 * GIB,
    'retained_file_cache_bytes': 8 * GIB,
    'minimum_high_headroom_bytes': 64 * GIB,
    'minimum_max_headroom_bytes': 76 * GIB,
    'minimum_host_available_bytes': 64 * GIB,
    'maximum_startup_psi_avg10': 1.0,
}
STAT_KEYS = ('file', 'shmem', 'active_file', 'inactive_file', 'file_mapped',
             'file_dirty', 'file_writeback', 'anon')


def file_credit(stat, retained):
    for key in STAT_KEYS:
        if type(stat.get(key)) is not int or stat[key] < 0:
            raise ValueError('missing or invalid memory.stat: ' + key)
    # active/inactive file excludes shmem. min() also protects divergent counters.
    disk_cache = min(max(0, stat['file'] - stat['shmem']),
                     stat['active_file'] + stat['inactive_file'])
    clean_unmapped = max(0, disk_cache - stat['file_mapped'] -
                         stat['file_dirty'] - stat['file_writeback'])
    return clean_unmapped, max(0, clean_unmapped - retained)


def assess(snapshot, host_available_bytes, policy=POLICY):
    value = copy.deepcopy(snapshot)
    if value['uid'] != policy['expected_uid']:
        raise ValueError('UID changed')
    parent = next((r for r in value['ancestors']
                   if r['path'] == policy['required_parent']), None)
    if parent is None:
        raise ValueError('required parent missing')
    if (parent['high_bytes'], parent['max_bytes']) != (
            policy['expected_high_bytes'], policy['expected_max_bytes']):
        raise ValueError('parent high/max changed')
    if type(host_available_bytes) is not int or host_available_bytes < 0:
        raise ValueError('host MemAvailable unavailable')
    failures = []
    if host_available_bytes < policy['minimum_host_available_bytes']:
        failures.append('host MemAvailable below 64 GiB')
    bounded = []
    for row in value['ancestors']:
        limits = {k: row[k + '_bytes'] for k in ('high', 'max')
                  if row.get(k + '_bytes') is not None}
        if not limits:
            continue
        current = row['current_bytes']
        if type(current) is not int or current < 0:
            raise ValueError('bounded ancestor current unavailable')
        clean, credit = file_credit(row.get('stat', {}), policy['retained_file_cache_bytes'])
        credit = min(current, credit)
        adjusted = current - credit
        entry = {'path': row['path'], 'current_bytes': current,
                 'clean_unmapped_file_bytes': clean, 'credited_file_bytes': credit,
                 'retained_file_cache_bytes': policy['retained_file_cache_bytes'],
                 'adjusted_current_bytes': adjusted, 'headroom_bytes': {}}
        for kind, limit in limits.items():
            if type(limit) is not int or limit < 0:
                raise ValueError('invalid finite limit')
            headroom = limit - adjusted
            entry['headroom_bytes'][kind] = headroom
            if headroom < policy['minimum_' + kind + '_headroom_bytes']:
                failures.append(row['path'] + ' adjusted ' + kind + ' headroom too low')
        for kind in ('some', 'full'):
            psi = row.get('pressure', {}).get(kind, {}).get('avg10')
            if not isinstance(psi, (int, float)) or not 0 <= psi <= 100:
                raise ValueError('startup PSI unavailable')
            if psi > policy['maximum_startup_psi_avg10']:
                failures.append(row['path'] + ' startup memory pressure')
        bounded.append(entry)
    if not bounded:
        raise ValueError('no finite ancestor')
    return {'admitted': not failures, 'failures': failures,
            'host_available_bytes': host_available_bytes, 'policy': policy,
            'bounded_ancestors': bounded, 'snapshot': value,
            'historical_basis': {'R96_first_job_total_peak_bytes': 67952947200,
                                 'R96_entire_session_total_peak_bytes': 77757599744,
                                 'historical_anon_peak': None},
            'scope': 'One H3 service, no concurrent own H3 or MF; fresh startup and pre-GO checks. No explicit reclamation or limit changes.'}

