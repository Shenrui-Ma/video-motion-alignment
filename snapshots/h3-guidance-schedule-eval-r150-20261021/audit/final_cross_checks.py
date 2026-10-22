"""Final read-only cross-links requested by the independent root review."""
import sys
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, read, write, bound, require, verify_record


def main():
    controls, cleanup_checks, releases = [], [], []
    for path in sorted((ROOT / 'actual').glob('*/BATCH_RELEASE.json')):
        batch = read(path)
        sid = path.parent.name
        require(batch.get('passed') is True, 'Unfinished batch ' + sid)
        owners = [read(p)['service_owner'] for p in sorted((ROOT / 'actual' / sid).glob('*/GATE.json'))]
        refs = [batch[k] for k in ('release', 'segment_release') if k in batch]
        refs += [v['release'] for v in batch.get('segments', {}).values()]
        for ref in refs:
            verify_record(ref)
            receipt = read(ref['file'])
            owner = receipt['owner']
            require(owner in owners, 'Release owner not in actual jobs')
            cleanup = receipt.get('cleanup', {})
            if 'service_record' in cleanup:
                require(cleanup['service_record'] == owner, 'Nested cleanup owner differs')
                cleanup_checks.append({'source_id': sid, 'release': ref,
                    'service_record_equals_owner': True, 'pid': owner['pid']})
            releases.append({'source_id': sid, 'receipt': ref,
                'process_absent': receipt.get('process_absent'),
                'CUDA_allocation_absent': receipt.get('CUDA_allocation_absent')})
        # Native-only Firefly prefix has its real standalone cleanup instead of a full COMPLETE.
        artifacts = batch.get('prefix_artifacts', {})
        if 'processes/cleanup.json' in artifacts:
            ref = artifacts['processes/cleanup.json']; verify_record(ref)
            cleanup = read(ref['file']); owner = read(ROOT/'actual'/sid/'native/GATE.json')['service_owner']
            if 'service_record' in cleanup:
                require(cleanup['service_record'] == owner, 'Native-prefix cleanup differs')
                cleanup_checks.append({'source_id': sid, 'cleanup': ref,
                    'service_record_equals_owner': True, 'pid': owner['pid']})
        for control_path in sorted((ROOT/'actual'/sid).glob('*/CONTROL.json')):
            control = read(control_path); role = control['role']
            for key in ('gate', 'binding', 'video'): verify_record(control[key])
            gate = read(control['gate']['file'])
            require(control['video']['sha256'] == gate['video']['sha256'], 'Control media differs')
            if 'job_gates' in batch:
                require(control['gate'] == batch['job_gates'][role]
                        and control['binding'] == batch['bindings'][role], 'CONTROL differs from BATCH_RELEASE')
                connection = 'exact BATCH_RELEASE job_gates and bindings'
            else:
                verify_record(batch['gate'])
                aggregate = read(batch['gate']['file'])
                require(gate == aggregate['runs'][role], 'CONTROL gate differs from aggregate')
                require(control['binding'] == bound(ROOT/'runtime'/sid/(role+'.json')), 'CONTROL runtime differs')
                connection = 'exact aggregate run and current runtime binding'
            controls.append({'source_id': sid, 'role': role, 'control': bound(control_path),
                'batch_release': bound(path), 'gate_binding_video_match': True, 'connection': connection})
    require(len(controls) == 5, 'Missing new Native/fixed control')
    require(len(list((ROOT/'actual').glob('*/BATCH_RELEASE.json'))) == 7, 'Missing R150 case release')
    out = ROOT/'audit/FINAL_CONTROL_CLEANUP_CROSS_CHECKS.json'
    write(out, {'schema': 'r150-final-control-cleanup-cross-checks-v1', 'passed': True,
        'created_utc': datetime.now(timezone.utc).isoformat(), 'controls': controls,
        'cleanup_owner_checks': cleanup_checks, 'normal_releases': releases,
        'hardware_failure_note': 'Book original GPU6/GPU7 CUDA state remains unknown in its validated three-segment record; no healthy release substitutes for those historical failures.',
        'scope': 'Existing small JSON and bound-file hashes only; no new inference, scores or browser.'})
    print({'passed': True, 'controls':len(controls), 'cleanup_checks':len(cleanup_checks), 'file':str(out)})

if __name__ == '__main__': main()
