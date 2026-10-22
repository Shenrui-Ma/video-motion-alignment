"""CPU-only, lossless RGB8 comparisons after the root's exact exit receipt."""
import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CODEC = HERE.parent
PARENT = CODEC.parents[1]
EXPECTED_FREEZE = '75aaae0a2236f220148ba1e171ee4f73a4bea1a8d30cb9f344defe3297eb2285'
NAMES = ['shift3_anchor', 'shift3_transport', 'offline_mapping_anchor', 'offline_mapping_transport']
PIXELS = 1152 * 768 * 3


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def release_gate(result, receipt):
    require(result['status'] == 'complete' and not result.get('cleanup_error'), 'completed clean decode run')
    require(receipt['passed'] is True and receipt['process_absent'] is True
            and receipt['CUDA_allocation_absent'] is True, 'root exact exit and CUDA release')
    require(receipt['pid'] == result['pid'], 'receipt belongs to this run')
    identity = result['root_gate']['identity']
    require(identity == receipt['identity'] and identity['pid'] == result['pid']
            and identity['uid'] == result['uid'], 'exact PID/UID/start/cmd identity')
    require(result['model_forward_calls'] == 0 and result['vae_encode_calls'] == 0
            and result['vae_decode_calls'] == 4 and result['fallback_guard']['calls'] == 0,
            'four native VAE decodes only')
    require(list(result['products']) == NAMES, 'four registered products and order')
    require([x['name'] for x in result['operations']] == NAMES
            and all(x['kind'] == 'decode' for x in result['operations']), 'four decode operations')


def frame_error(a, b):
    require(a.dtype == np.uint8 and b.dtype == np.uint8 and a.shape == b.shape, 'same RGB8 geometry')
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).sum(dtype=np.int64)) / (a.size * 255)


class RGBReader:
    def __init__(self, entry):
        self.entry = entry
        ffmpeg = shutil.which('ffmpeg') or '/opt/homebrew/bin/ffmpeg'
        self.proc = subprocess.Popen([ffmpeg, '-v', 'error', '-threads', '1', '-i', entry['file'],
            '-map', '0:v:0', '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
            '-threads', '1', 'pipe:1'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.index = 0

    def next(self):
        raw = self.proc.stdout.read(PIXELS)
        require(len(raw) == PIXELS, 'complete decoded frame ' + str(self.index))
        require(hashlib.sha256(raw).hexdigest() == self.entry['rgb24_frame_sha256'][self.index],
                'lossless original RGB24 pixel hash ' + self.entry['file'] + ':' + str(self.index))
        self.index += 1
        return np.frombuffer(raw, dtype=np.uint8).reshape(768, 1152, 3)

    def finish(self):
        require(self.index == 158 and not self.proc.stdout.read(1), 'exactly 158 frames')
        error = self.proc.stderr.read().decode()
        require(self.proc.wait() == 0, 'ffmpeg decode: ' + error)
        self.proc.stdout.close(); self.proc.stderr.close()

    def close(self):
        if self.proc.poll() is None:
            self.proc.kill(); self.proc.wait()
        self.proc.stdout.close(); self.proc.stderr.close()


def checked_product(run, name, item):
    require(Path(item['file']).name == name + '.mp4', 'expected video basename')
    path = run / (name + '.mp4')
    require(sha(path) == item['sha256'], 'video SHA ' + name)
    require((item['frames'], item['fps'], item['width'], item['height']) == (158, 24, 1152, 768), 'geometry ' + name)
    require(item['lossless_pixel_verified'] is True and item['selected_full158_indices'] == list(range(158))
            and len(item['rgb24_frame_sha256']) == 158, 'producer lossless record ' + name)
    probe = shutil.which('ffprobe') or '/opt/homebrew/bin/ffprobe'
    s = json.loads(subprocess.check_output([probe, '-v', 'error', '-select_streams', 'v:0', '-count_frames',
        '-show_entries', 'stream=width,height,nb_read_frames,r_frame_rate', '-of', 'json', str(path)]))['streams'][0]
    require((s['width'], s['height'], s['nb_read_frames'], s['r_frame_rate']) == (1152, 768, '158', '24/1'), 'actual video geometry')
    return {**item, 'file': str(path), 'probe': s}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--exit-receipt', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    require(not args.out.exists(), 'preserve previous analysis')
    result, receipt = read(args.run/'RESULT.json'), read(args.exit_receipt)
    release_gate(result, receipt)
    require(sha(CODEC/'FREEZE.json') == EXPECTED_FREEZE == result['root_gate']['freeze_sha256'], 'codec producer freeze')
    for item in read(CODEC/'FREEZE.json')['files']:
        require(sha(CODEC/item['file']) == item['sha256'], 'codec producer file ' + item['file'])
    config = read(CODEC/'contract.json')
    require(sha(CODEC/'contract.json') == result['contract_sha256'] == result['root_gate']['contract_sha256'], 'contract binding')
    for name, digest in config['parent_files_sha256'].items():
        require(sha(PARENT/name) == digest, 'actual original input ' + name)
    require(result['root_gate']['parent_files_sha256'] == config['parent_files_sha256'], 'ready input binding')
    require(result['input_x0_signature']['sha256'] == config['input_x0_raw_sha256'], 'same original x0')
    for item in result['operations']:
        require(item['input_signature']['shape'] == config['shape'] and item['input_signature']['dtype'] == 'torch.float32', 'latent signature')
        require(sha(args.run/(item['name']+'.pt')) == item['input_file_sha256'], 'actual derived latent file')
        require(item['decoded_signature']['shape'] == config['geometry'] and item['decoded_signature']['dtype'] == 'torch.float32', 'decoded signature')
    original_run = PARENT/'outputs/attempt1'
    original = read(original_run/'RESULT.json')
    spec = importlib.util.spec_from_file_location('prior_verifier', PARENT/'analysis/consumer/verify_result.py')
    prior = importlib.util.module_from_spec(spec); spec.loader.exec_module(prior)
    prior.validate_release(original, read(PARENT/'audit/root_control_attempt1/ROOT_EXIT_RECEIPT.json'))
    expected = read(PARENT/'analysis/consumer/EXPECTED_COORDINATES.json')
    products = {name: checked_product(original_run, name, item) for name, item in original['products'].items()}
    products.update({name: checked_product(args.run, name, item) for name, item in result['products'].items()})
    args.out.mkdir(parents=True)
    write(args.out/'HISTORICAL_FLOAT_COMPARISONS.json', {'source_result_sha256':sha(original_run/'RESULT.json'),
        'domain':'original float32 RGB, retained verbatim; excluded from new RGB8 method comparisons',
        'comparisons':original['comparisons']})
    shared = [all(prior.groups(x['coordinates'])['common_valid147'][i] for x in expected.values()) for i in range(158)]
    detail, rows, frame_rows = {}, [], []
    for mapping in ['identity', 'shift3', 'offline_mapping']:
        coords = read(original_run/(mapping+'_coordinates.json'))
        require(coords == expected[mapping]['coordinates'], 'same frozen map and masks')
        masks = prior.groups(coords)
        masks['common_domain_shared_across_three_maps'] = shared
        masks['latent_interpolation_cross17_common'] = [v and coords['cross17_latent_interpolation'][o] for v,o in zip(masks['common_valid147'], coords['output_bin_index'])]
        masks['latent_source_block_change_common'] = [v and coords['cross17_latent_source_block'][o] for v,o in zip(masks['common_valid147'], coords['output_bin_index'])]
        masks['outside_decoder_overlap_common'] = [v and not x for v,x in zip(masks['common_valid147'],coords['decoder_overlap_first5'])]
        if mapping == 'identity':
            names = ['baseline_Dz', 'identity_RGB_roundtrip']
        else:
            names = [mapping+x for x in ['_RGB_target','_RGB_roundtrip','_latent_warp','_anchor','_transport']]
        readers = {n: RGBReader(products[n]) for n in names}
        errors = {n: [] for n in names[1:]}
        try:
            for i in range(158):
                frames = {n:r.next() for n,r in readers.items()}
                for n in names[1:]:
                    error = frame_error(frames[n], frames[names[0]])
                    errors[n].append(error)
                    frame_rows.append({'mapping':mapping,'method':n,'frame':i,'seconds':i/24,
                        'normalized_rgb8_mae':error,'common_valid':masks['common_valid147'][i]})
            for reader in readers.values(): reader.finish()
        finally:
            for reader in readers.values(): reader.close()
        detail[mapping] = {'target':names[0], 'coordinates':coords, 'masks':masks, 'methods':{}}
        for n, values in errors.items():
            groups = {g:{'frames':sum(mask),'normalized_rgb8_mae':prior.reduced(values,mask)['mean_absolute_rgb_error']} for g,mask in masks.items()}
            detail[mapping]['methods'][n] = {'frame_mae':values,'groups':groups}
            for g, values in groups.items(): rows.append({'mapping':mapping,'method':n,'region':g,**values})
        print(json.dumps({'mapping':mapping,'RGB8_verified':True}),flush=True)
    report = {'passed':True,'schema':'r70-codec-residual-rgb8-consumer-v1','result_sha256':sha(args.run/'RESULT.json'),
        'exit_receipt_sha256':sha(args.exit_receipt),'parent_result_sha256':sha(original_run/'RESULT.json'),
        'freeze_sha256':EXPECTED_FREEZE,'pid':result['pid'],'products':products,'maps':detail,
        'operations':result['operations'],'wall_seconds':result['wall_seconds'],
        'max_memory_reserved_bytes':result['max_memory_reserved_bytes'],
        'definition':'Mean absolute RGB channel error /255. Each method and target decoded losslessly to RGB8 and checked against all 158 producer frame hashes.',
        'scope':'Temporal rearrangement and codec reconstruction diagnostic on the same saved x0. Offline map uses final-output development fit. Photometric differences are not action timing accuracy.'}
    write(args.out/'VERIFIED.json',report)
    for name,table in [('RGB8_ERROR_TABLE.csv',rows),('RGB8_PER_FRAME.csv',frame_rows)]:
        with (args.out/name).open('w') as f:
            writer=csv.DictWriter(f,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
    print(json.dumps({'passed':True,'out':str(args.out)}))


if __name__ == '__main__': main()
