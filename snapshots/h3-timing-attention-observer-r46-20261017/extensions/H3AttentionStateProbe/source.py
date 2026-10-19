"""Restore only individually hash-bound historical tensors; no encoders."""
import hashlib
import json
from pathlib import Path
import uuid
import torch
from .dependencies import readout
from .signatures import signature_tree

ROOT = Path(__file__).resolve().parents[2]
SHAPES = ((1, 24, 42, 46, 82), (1, 32, 2, 235))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


class Source:
    def __init__(self, label, root=ROOT):
        root = Path(root)
        self.protocol = json.loads((root / 'configs/SCIENCE_PROTOCOL.json').read_text())
        path = root / 'configs/sources.json'
        require(sha(path) == self.protocol['source_binding_sha256'], 'source binding changed')
        sources = json.loads(path.read_text())
        require(label in ('bad', 'normal') and set(sources) == {'bad', 'normal'}, 'unregistered state')
        self.s = sources[label]
        self.root = Path(self.s['source_root'])
        self.label = label
        self.condition = self.s['condition']
        require(self.s['raw_input']['physical_index'] == 4 and self.s['endpoint']['physical_index'] == 4,
                'only actual pre-Full index4 is supported')

    def load(self, path):
        path = Path(path)
        if path.is_absolute():
            require(path.is_relative_to(self.root), 'parent path escaped')
            rel = str(path.relative_to(self.root))
        else:
            rel = str(path); path = self.root / path
        require('..' not in Path(rel).parts and rel in self.s['files'], 'unbound source tensor')
        expected = self.s['files'][rel]
        require(not path.is_symlink() and path.resolve().is_relative_to(self.root.resolve()), 'parent symlink escape')
        require(path.stat().st_size == expected['bytes'] and sha(path) == expected['sha256'], 'source PT differs: ' + rel)
        return torch.load(path, map_location='cpu', weights_only=True)

    def blob(self, name):
        row = self.s['blobs'][name]
        value = self.load(row['remote_path'])
        got = readout.tensor_signature(value)
        require(all(got[k] == row['signature'][k] for k in ('shape', 'dtype', 'sha256')), 'source blob bytes differ')
        return value

    def positive(self):
        original = self.condition['tree']['original']['positive'][0]
        refs = []
        for i, row in enumerate(original['minimax_refs']):
            ref = {k: v for k, v in row.items() if k != 'latent'}
            ref['latent'] = self.blob('portrait_latent' if i == 0 else 'video_latent')
            refs.append(ref)
        return [[self.blob('original_embedding'), {'minimax_refs': refs,
                'minimax_token_tags': self.blob('text_token_tags'), 'pooled_output': None}]]

    def restore_original_uuid(self, guider):
        expected = self.condition['tree']['original']
        actual = signature_tree(guider.original_conds)
        require(set(actual) == {'positive'} and len(actual['positive']) == 1, 'single positive BasicGuider')
        old = expected['positive'][0]['uuid']
        actual['positive'][0]['uuid'] = old
        require(actual == expected, 'original conditions differ beyond authorized UUID')
        guider.original_conds['positive'][0]['uuid'] = uuid.UUID(old)
        require(signature_tree(guider.original_conds) == expected, 'UUID restoration failed')

    def input(self):
        row = self.s['raw_input']; data = self.load(row['file'])
        require(data['metadata'] == {k: v for k, v in row.items() if k not in ('file', 'file_sha256', 'archive_seconds')},
                'raw input metadata differs')
        x = data['packed']
        require(readout.tensor_signature(x) == row['packed_signature'] and x.dtype == torch.float32 and
                tuple(x.shape) == (1, 1, 3817216) and bool(torch.isfinite(x).all()), 'raw packed input differs')
        return x

    def noise(self):
        data = self.load(self.s['noise']['path'])
        values = data['tensors']
        require(len(values) == 2 and [tuple(x.shape) for x in values] == list(SHAPES), 'noise streams differ')
        from comfy.utils import pack_latents
        packed, _ = pack_latents(values)
        require(readout.tensor_signature(packed) == self.s['noise']['packed_signature'], 'packed noise differs')
        return values

    def endpoint(self):
        row = self.s['endpoint']; data = self.load(row['file'])
        for k in ('physical_index', 'branch', 'nfe_index', 'sigma', 'sigma_next', 'seed',
                  'condition_sha256', 'reference_sha256'):
            expected = self.s['seed'] if k == 'seed' else row[k]
            require(data['metadata'][k] == expected, 'endpoint metadata differs: ' + k)
        normal = [data['video'], data['audio']]
        require([readout.tensor_signature(x) for x in normal] == row['normalized_stream_signatures'], 'endpoint normalized bytes differ')
        raw = [normal[0], normal[1] * 4.0]
        require([readout.tensor_signature(x) for x in raw] == row['raw_stream_signatures'], 'endpoint raw conversion differs')
        return raw
