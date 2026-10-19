"""Read-only post-exit proof for both actual R116 trackers, with a live peer allowed."""
from pathlib import Path
import argparse, sys, subprocess, time, math

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from common import read, sha, save, bound, identity, verify_seal
import capacity, process_identity, peer_support


def main(attempt):
    verify_seal()
    folder = ROOT/'audit'/attempt
    done = read(folder/'COMPLETE.json')
    assert done['passed'] and done['remaining'] == [] and done['all_spawned_trackers_released']
    rt = read(ROOT/'configs/RUNTIME.json')
    wrapper = read(folder/'STARTED.json')['identity']
    assert identity(wrapper['pid']) != wrapper
    assert not Path('/proc', str(wrapper['pid'])).exists()
    states, results, released, identities = [], [], [], []
    for job in read(ROOT/'configs/PLAN.json')['jobs']:
        state_file = ROOT/'state'/job['case']/(job['role']+'.json')
        state = read(state_file)
        receipt = state['release']
        assert sha(receipt['file']) == receipt['sha256']
        release = read(receipt['file'])
        assert release['passed'] and release['returncode'] == 0
        assert release['process_absent'] and release['CUDA_absent'] and release['peer_registrations_removed']
        owner = release['identity']
        assert identity(owner['pid']) != owner and not Path('/proc', str(owner['pid'])).exists()
        report_file = ROOT/state['folder']/'REPORT.json'
        report = read(report_file)
        assert sha(report_file) == state['report_sha256'] and report['passed']
        assert sha(report_file.parent/'tracks.pt') == report['tracks_sha256']
        result_file = ROOT/'results'/job['case']/(job['role']+'.json')
        value = read(result_file)['score']
        assert isinstance(value, (int, float)) and math.isfinite(value)
        states.append(bound(state_file));results.append(bound(result_file));released.append(receipt);identities.append(owner)
    assert len(states) == len(results) == 2
    cuda = subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'], text=True)
    rows = []
    for line in cuda.splitlines():
        if not line.strip(): continue
        pid, gpu = map(str.strip, line.split(','));p = Path('/proc')/pid
        if not p.exists(): continue
        assert int(pid) not in [x['pid'] for x in identities]
        rows.append({'pid': int(pid), 'uid': p.stat().st_uid, 'gpu_uuid': gpu})
    peers = peer_support.peers(rt['peer_roots'], process_identity)
    own = peer_support.owned_check({'processes':rows}, peers, process_identity, rt['gpu_uuid'])
    for peer in peers:
        admission = read(Path(peer['root'])/'configs/admission.json')
        assert all(x['pid'] not in [v['pid'] for v in identities] for x in admission['permitted_compute_processes'])
    baseline = read(folder/'OOM_BASE.json');fresh = capacity.snapshot()
    delta = capacity.oom_delta(baseline, fresh);assert delta['passed']
    for obs in folder.glob('jobs/*/*/RESOURCE_OBSERVATIONS.json'):
        for sample in read(obs)['samples']:
            assert capacity.oom_delta(baseline, sample['capacity'])['passed']
    result = {'passed':True, 'wrapper_identities':[wrapper], 'tracker_identities':identities,
        'all_spawned_trackers_released':True, 'exact_processes_absent':True,
        'exact_CUDA_allocations_absent':True, 'peer_registrations_removed':True,
        'completed_generated_scores':2, 'state_receipts':states, 'result_receipts':results,
        'child_release_receipts':released, 'fresh_own_contexts':own, 'fresh_capacity':fresh,
        'OOM_delta':delta, 'final_complete':bound(folder/'COMPLETE.json'),
        'seal':bound(ROOT/'SEAL.json'), 'unix':time.time()}
    target = ROOT/'audit/FINAL_RELEASE_VERIFIED.json'
    assert not target.exists();save(target, result)
    print({'file':str(target),'sha256':sha(target),'all_released':True})


if __name__ == '__main__':
    p = argparse.ArgumentParser();p.add_argument('--attempt',required=True)
    main(p.parse_args().attempt)
