"""Complete the archived chest case after its verified input inventory repair."""
import shutil
from pathlib import Path
import incremental_case as inc
from source_inputs import checked_inputs

consumer, ROOT, HERE = inc.consumer, inc.ROOT, inc.HERE
read, save, sha, require = inc.read, inc.save, inc.sha, inc.require
case = inc.case_for('r50_source_chest_seed2026101701_auto')
arc = HERE / 'completed_cases' / case['run_id']
audit = HERE / 'audit/input_archive_v3/chest_recovery'
with consumer.locked():
    owner = consumer.bound()
    inc.verify_producer_sources(ROOT, consumer.P['producer_manifest_sha256'], all_files=True)
    require(not (arc / 'CASE_READY.json').exists(), 'case already complete')
    inventory = read(arc / 'FILE_INVENTORY.json')
    inc.verify_phase_dependencies(ROOT, arc, inventory)
    inc.validate_partial_gate(read(arc / 'CASE_RUNTIME_GATE.json'), case['run_id'])
    dest = arc / 'final' / case['run_id']
    require(dest.is_dir() and not list(dest.iterdir()), 'unexpected partial result content')
    audit.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(arc / 'FILE_INVENTORY.json', audit / 'ORIGINAL_FILE_INVENTORY.json')
    added = {}
    for source in checked_inputs(ROOT, [case]):
        rel = str(source.relative_to(ROOT))
        require(rel not in inventory, 'input was already archived')
        target = arc / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        require(sha(target) == sha(source), 'input copy differs')
        added[rel] = {'sha256': sha(target), 'bytes': target.stat().st_size}
    inventory.update(added)
    save(arc / 'FILE_INVENTORY.json', inventory)
    save(audit / 'INPUT_ADDITION.json', {'run_id': case['run_id'],
         'original_inventory_sha256': sha(audit / 'ORIGINAL_FILE_INVENTORY.json'),
         'new_inventory_sha256': sha(arc / 'FILE_INVENTORY.json'), 'added': added,
         'source_parent_inventory_sha256': sha(ROOT / case['parent_file_inventory']),
         'scientific_contract_sha256': sha(ROOT / 'configs/scientific_contract.json'),
         'producer_changed': False})
    dest.rmdir()  # Only the verified empty directory from the failed consumer phase.
    summary = consumer.evaluate_case(case, arc=arc, runtime_gate_name='CASE_RUNTIME_GATE.json')
    save(dest / 'CASE_FILES.json', {str(p.relative_to(dest)): sha(p) for p in dest.rglob('*') if p.is_file() and p.name != 'CASE_FILES.json'})
    inc.verify_phase_dependencies(ROOT, arc, inventory)
    ready = {'status': 'case_ready', 'partial_batch': True, 'planned_denominator': 5,
             'run_id': case['run_id'], 'owner': owner,
             'file_inventory_sha256': sha(arc / 'FILE_INVENTORY.json'),
             'runtime_gate_sha256': sha(arc / 'CASE_RUNTIME_GATE.json'),
             'case_files_sha256': sha(dest / 'CASE_FILES.json'),
             'metric_inputs': str(dest / 'METRIC_INPUTS.json'),
             'metric_inputs_sha256': sha(dest / 'METRIC_INPUTS.json'),
             'root_release_allowed': False, 'batch_complete': False, 'summary': summary}
    save(arc / 'CASE_READY.json', ready)
    save(arc / 'DERIVED_FILES.json', {str(p.relative_to(arc)): sha(p) for p in arc.rglob('*') if p.is_file() and str(p.relative_to(arc)) not in inventory and p.name not in ('FILE_INVENTORY.json', 'DERIVED_FILES.json')})
    inc.completed(arc, case)
    save(audit / 'COMPLETE.json', {'passed': True, 'case_ready_sha256': sha(arc / 'CASE_READY.json')})
    print(inc.json.dumps({'status': 'case_ready', 'metric_inputs_sha256': ready['metric_inputs_sha256']}))
