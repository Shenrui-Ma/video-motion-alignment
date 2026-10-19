"""Construct a root-reviewed certificate only from new successful R59 GPU evidence."""
import argparse
import importlib.util
import json
import subprocess
import time
from pathlib import Path
from execution_contract import ROOT, CANDIDATE_SHA, require, read, sha, write_new
from r59_contract import REMOTE


def build(probe_root, root=ROOT, root_reviewed=False):
    root, probe_root = Path(root), Path(probe_root)
    require(root_reviewed and root.resolve() == REMOTE, 'root-reviewed exact remote evidence required')
    require(probe_root.resolve().is_relative_to(root / 'audit/main_capacity_probe'), 'probe outside task root')
    report_path = probe_root / 'audit/capacity_complete.json'
    result_path = probe_root / 'audit/run_result.json'
    report, result = read(report_path), read(result_path)
    package = read(probe_root / 'configs/package.json')
    require(package['probe_sha256'] == sha(probe_root / 'configs/probe.json'), 'probe configuration changed')
    config = read(probe_root / 'configs/probe.json')
    require(report['configuration'] == config and config['producer_root'] == str(root), 'capacity producer differs')
    for path, digest in config['bound_files'].items():
        require(sha(path) == digest, 'probe input/code evidence changed: ' + path)
    spec = importlib.util.spec_from_file_location('r59_capacity_contract', root / 'audit/main_capacity_probe/H3MainCapacityProbe/contract.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.successful_capacity(report)
    require(result['capacity_passed'] is True and result['inference_complete'] is False and result['report_sha256'] == sha(report_path), 'capacity controlled-stop record failed')
    require(all(result['cleanup'][key] is True for key in ('original_generation_absent', 'own_compute_absent')), 'capacity process cleanup incomplete')
    require(len(config['all_case_seq_len']) == 5 and config['seq_len'] == max(row['seq_len'] for row in config['all_case_seq_len']), 'maximum P1 sequence was not measured')
    runtime = read(root / 'configs/runtime.json')
    require(config['runtime'] == runtime, 'production startup/runtime differs from capacity probe')
    require(report['reserve_vram_GiB'] == 8 and report['native_exact'] is True, 'reserve8 numerical pairing absent')
    pid = report['pid']
    identity = read(probe_root / 'audit/service_identity.json')['identity']
    require(identity['pid'] == pid, 'sampled GPU memory owner differs')
    nvml = []
    resources = probe_root / 'audit/resources.jsonl'
    for line in resources.read_text().splitlines():
        for row in json.loads(line)['compute']:
            if row['pid'] == pid:
                require(row['gpu_uuid'] == runtime['gpu_uuid'], 'capacity process used unexpected device')
                nvml.append(int(row['used_memory_MiB']) * 1024**2)
    require(bool(nvml), 'own-PID GPU memory samples missing')
    native, full = report['forwards']
    base_peak = max(report['before_first_forward']['lifetime_max_reserved_bytes'], native['peak_reserved_bytes'])
    measured_peak = max(base_peak, full['peak_reserved_bytes'], max(nvml))
    increment = max(1024**2, measured_peak - base_peak)
    margin = 2 * 1024**3
    estimated_peak = base_peak + increment + margin
    total = full['after']['driver_total_bytes']
    require(estimated_peak <= total, 'measured P1 capacity plus2GiB margin exceeds GPU memory')
    decoder_path = root / 'audit/known_endpoint_90_gate.json'
    kernel_path = root / 'audit/gpu_dynamic_union_gate.json'
    decoder, kernel = read(decoder_path), read(kernel_path)
    protocol_sha = sha(root / 'configs/protocol.json')
    require(decoder['passed'] is True and kernel['passed'] is True and decoder['protocol_sha256'] == kernel['protocol_sha256'] == protocol_sha, 'current kernel/decoder evidence missing')
    parent = read(root / 'prepared_parent/PARENT_BINDING.json')
    decoder_gpu_csv = subprocess.check_output(['nvidia-smi', '--id=' + runtime['decoder_uuid'], '--query-gpu=uuid,memory.total', '--format=csv,noheader,nounits'], text=True, timeout=10)
    fields = [value.strip() for value in decoder_gpu_csv.strip().split(',')]
    require(len(fields) == 2 and fields[0] == runtime['decoder_uuid'] and int(fields[1]) > 0, 'decoder total memory query differs')
    total_file = root / 'audit/decoder_total_memory.json'
    write_new(total_file, {'observed_unix': time.time(), 'gpu_uuid': runtime['decoder_uuid'], 'memory_total_mib': int(fields[1]), 'raw': decoder_gpu_csv})
    files = (report_path, result_path, resources, probe_root / 'audit/service_identity.json', decoder_path, kernel_path, total_file)
    record = {'schema': 'r55-root-two-GPU-resource-admission-v1', 'root_approved': True,
        'candidate_manifest_sha256': CANDIDATE_SHA, 'protocol_sha256': protocol_sha,
        'parent_manifest_sha256': parent['parent_manifest_sha256'],
        'kernel_gate_sha256': sha(kernel_path), 'decoder_gate_sha256': sha(decoder_path),
        'main_gpu_uuid': runtime['gpu_uuid'], 'decoder_gpu_uuid': runtime['decoder_uuid'],
        'main_native_peak_reserved_bytes': base_peak, 'routing_increment_bound_bytes': increment,
        'main_margin_bytes': margin, 'main_estimated_peak_bytes': estimated_peak, 'main_total_memory_bytes': total,
        'decoder_peak_reserved_bytes': decoder['decode']['max_memory_reserved_bytes'],
        'decoder_total_memory_bytes': int(fields[1]) * 1024**2,
        'scope': 'GPU1 main model; GPU2 isolated decoder; maximum2 owned GPUs',
        'capacity_scope': 'R59 P1 Native plus same-state Full global27 all50blocks alpha1',
        'actual_native_prefix_equal_R57': True, 'full_forward_completed_50_blocks': True,
        'input_sigma_condition_rng_equal': True, 'maximum_P1_sequence_case_measured': True,
        'evidence': [{'file': str(path), 'sha256': sha(path)} for path in files],
        'measured_own_PID_NVML_peak_bytes': max(nvml),
        'capacity_limits': 'Two first-state predictions with largest P1 sequence; later full-trajectory peaks remain monitored.2GiB margin is explicit root policy.'}
    write_new(root / 'audit/resource_admission.json', record)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe-root', type=Path, required=True)
    parser.add_argument('--root-reviewed', action='store_true')
    args = parser.parse_args()
    result = build(args.probe_root, root_reviewed=args.root_reviewed)
    print(json.dumps({'main_required_free_bytes': result['main_estimated_peak_bytes'], 'main_margin_bytes': result['main_margin_bytes']}))
