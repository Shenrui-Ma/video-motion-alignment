"""CPU-only integration checks; generates no model answer and never loads weights."""
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ['CUDA_VISIBLE_DEVICES'] = ''
import batch_eval as batch
import torch
from PIL import Image
from transformers import AutoConfig, AutoProcessor, Qwen2_5_VLForConditionalGeneration

MODEL = batch.ROOT.parent / 'weights/Qwen2.5-VL-72B-Instruct-AWQ'


class RuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(4)
        cls.modules = batch.official_modules()
        cls.processor = AutoProcessor.from_pretrained(str(MODEL), local_files_only=True)

    def test_config_and_backend_import(self):
        from awq.modules.linear import gemm
        config = AutoConfig.from_pretrained(str(MODEL), local_files_only=True)
        self.assertEqual(config.quantization_config['bits'], 4)
        self.assertEqual(config.quantization_config['version'], 'gemm')
        self.assertEqual(config.num_hidden_layers, 80)
        self.assertTrue(gemm.TRITON_AVAILABLE or gemm.awq_ext is not None)
        self.assertFalse(torch.cuda.is_initialized())

    def test_device_map_covers_checkpoint_without_cpu(self):
        mapping = batch.explicit_device_map()
        weights = json.loads((MODEL / 'model.safetensors.index.json').read_text())['weight_map']
        for key in weights:
            self.assertTrue(any(key == prefix or key.startswith(prefix + '.') for prefix in mapping), key)
        self.assertEqual(set(mapping.values()), {0, 1})

    def test_gpu_gate_refuses_busy_and_aliases(self):
        with patch('batch_eval.subprocess.check_output', side_effect=['GPU-A\n', 'GPU-A, 39000, 40960']):
            with self.assertRaisesRegex(RuntimeError, 'existing compute process'):
                batch.gpu_admission('0,1')
        with patch('batch_eval.subprocess.check_output', side_effect=['', 'GPU-A, 39000, 40960', 'GPU-A, 39000, 40960']):
            with self.assertRaisesRegex(RuntimeError, 'same physical'):
                batch.gpu_admission('0,GPU-A')
        with self.assertRaisesRegex(RuntimeError, 'Exactly two'):
            batch.gpu_admission('0')

    def test_remap_preserves_original(self):
        original = {'metadata_file': '/remote/root/metadata/a.json', 'video': '/remote/root2/a.mp4'}
        actual = batch.remap_job(original, [('/remote/root', '/staged')])
        self.assertEqual(actual['metadata_file'], '/staged/metadata/a.json')
        self.assertEqual(actual['video'], original['video'])
        self.assertEqual(original['metadata_file'], '/remote/root/metadata/a.json')

    def test_staged_job_requires_complete_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            frames = root / 'frames/sample'
            frames.mkdir(parents=True)
            metadata = root / 'meta.json'
            metadata.write_text('[]')
            job = {'metadata': {'src_video_name': 'sample.mp4'}, 'metadata_file': str(metadata),
                   'source_frames_parent': str(root / 'frames'), 'target_frames_parent': str(root / 'frames'),
                   'valid_frames': 2}
            self.assertFalse(batch.job_ready(job))
            (frames / 'PREPARED.json').write_text('{"frames": 2}')
            (frames / '000001.png').touch()
            self.assertFalse(batch.job_ready(job))
            (frames / '000002.png').touch()
            self.assertTrue(batch.job_ready(job))

    def test_official_preprocess_prompt_and_result_schema(self):
        processor = self.processor
        responses = []

        class FakeGenerator:
            device = torch.device('cpu')

            def generate(self, **kwargs):
                self.tokens = kwargs.pop('max_new_tokens')
                responses.append({'max_new_tokens': self.tokens,
                                  'input_shape': list(kwargs['input_ids'].shape),
                                  'video_shape': list(kwargs['pixel_values_videos'].shape)})
                ids = torch.tensor([processor.tokenizer.encode('[4] [CPU test stub]', add_special_tokens=False)])
                return torch.cat([kwargs['input_ids'], ids], dim=1)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source/sample'
            target = root / 'target/sample'
            source.mkdir(parents=True)
            target.mkdir(parents=True)
            for i in range(30):
                image = Image.new('RGB', (96, 64), (i * 5, 30, 70))
                for folder in (source, target):
                    image.save(folder / f'{i+1:06d}.png')
            metadata = {'id': 1, 'src_video_name': 'sample.mp4', 'category': 'subject_editing',
                        'subcategory': 'replace existing subject', 'source_prompt': 'source',
                        'target_prompt': 'target', 'edit_prompt': 'Replace red with blue'}
            metadata_path = root / 'metadata.json'
            metadata_path.write_text(json.dumps([metadata]))
            job = {'id': 'sample__test', 'task_id': 'sample', 'dataset': 'TEST', 'method': 'stub',
                   'metadata': metadata, 'metadata_file': str(metadata_path),
                   'source_frames_parent': str(root / 'source'), 'target_frames_parent': str(root / 'target')}
            self.assertTrue(batch.job_ready(job))
            for metric, (package, class_name) in batch.METRICS.items():
                evaluator_class = getattr(self.modules[metric], class_name)
                evaluator = evaluator_class.__new__(evaluator_class)
                evaluator.model = FakeGenerator()
                evaluator.processor = processor
                evaluator.process_vision_info = importlib.import_module(package + '.qwen_vl_utils').process_vision_info
                with patch.object(processor, 'apply_chat_template', wraps=processor.apply_chat_template) as capture:
                    result_path = root / (metric + '.json')
                    self.assertTrue(batch.evaluate_one(job, metric, self.modules[metric], evaluator,
                                                       result_path, {'test_stub': True}))
                    content = capture.call_args.args[0][0]['content']
                    self.assertEqual([item['type'] for item in content], ['video', 'text', 'video', 'text'])
                    prompt = content[-1]['text']
                    self.assertIn(metadata['edit_prompt'], prompt)
                    self.assertIn('1 to 5', prompt)
                    self.assertIn('expected result' if metric == 'instruction_satisfaction' else 'strictly preserve', prompt)
                result = json.loads(result_path.read_text())
                self.assertEqual(result['score'], 4.0)
                self.assertEqual(result['status'], 'done')
                self.assertTrue(result['evaluator']['test_stub'])
                self.assertEqual(evaluator._parse_score('no valid answer'), -1.0)
                self.assertFalse(torch.cuda.is_initialized())
            self.assertTrue((source / '000001.png').exists())
            self.assertFalse((source / '00001.png').exists())
            self.assertEqual(len(responses), 2)
            self.assertTrue(all(row['max_new_tokens'] == 1280 for row in responses))
            batch.atomic(batch.ROOT / 'cpu_preprocess_shapes.json', {'synthetic_stub_only': True, 'calls': responses})


if __name__ == '__main__':
    unittest.main(verbosity=2)
