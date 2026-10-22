"""Read-only CUDA admission for one tracker alongside existing user services."""
IDENTITY_KEYS = ('pid', 'uid', 'start_ticks', 'cmdline_sha256')


def same_identity(left, right):
    return all(str(left.get(key)) == str(right.get(key)) for key in IDENTITY_KEYS)


def assess(rows, selected_gpu, known_services, task_pid=None, uid=1004, limit=2):
    owned = []
    for source in rows:
        row = dict(source)
        if row['uid'] != uid:
            continue
        known = next((item for item in known_services
                      if same_identity(row, item)
                      and row['gpu_uuid'] == item['gpu_uuid']), None)
        row['classification'] = ('current tracker' if row['pid'] == task_pid else
                                 'verified pre-existing service' if known else
                                 'other observed process; capacity assessed')
        owned.append(row)
    devices = sorted({selected_gpu, *(row['gpu_uuid'] for row in owned)})
    return dict(passed=len(devices) <= limit, observed_owned_cuda=owned,
                owned_gpu_uuids_including_selected=devices, maximum_gpus=limit,
                failures=[] if len(devices) <= limit else ['owned GPU limit exceeded'])


def task_cuda_absent(rows, task_identities):
    return not any(same_identity(row, task)
                   for row in rows for task in task_identities)
