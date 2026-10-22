"""CPU-only instrumentation regression checks; no Core server or GPU required."""

from copy import deepcopy
import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TensorMetadata:
    shape = (2, 3)
    dtype = "torch.float32"
    device = "cpu"

    def cpu(self):
        raise AssertionError("backend auditor must not copy tensor data")

    def __repr__(self):
        raise AssertionError("backend auditor must not inspect tensor values")


class BackendAuditTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.log = Path(self.directory.name) / "dispatch.json"
        self.audit = load_file("backend_dispatch_test", ROOT / "scripts/backend_dispatch_audit.py")
        self.result = object()
        self.calls = []

        def operator(x, weight=None, *, bias=None):
            """Fake backend operator."""
            self.calls.append((x, weight, bias))
            return self.result

        self.original = operator
        self.other = object()
        self.backends = {
            name: types.SimpleNamespace(int8_linear=operator, w4a8_int8_linear=operator,
                                        unrelated=self.other)
            for name in self.audit.BACKENDS
        }
        self.registry = types.SimpleNamespace(get_implementation=lambda op, *, backend:
                                              getattr(self.backends[backend], op))

        def importer(name):
            if name == "comfy_kitchen.registry":
                return types.SimpleNamespace(registry=self.registry)
            backend = name.rsplit(".", 1)[-1]
            if backend not in self.backends:
                raise ImportError("fixture backend unavailable")
            return self.backends[backend]

        self.importer = patch.object(self.audit.importlib, "import_module", side_effect=importer)
        self.importer.start()
        self.addCleanup(self.importer.stop)
        self.atexit = patch.object(self.audit.atexit, "register")
        self.atexit.start()
        self.addCleanup(self.atexit.stop)

    def install(self, **kwargs):
        return self.audit.install(log_path=self.log, **kwargs)

    def test_exports_registry_and_call_identity_are_preserved(self):
        self.original._h3_row_chunk_policy = {"fixture": True}
        summary = self.install()
        tensor, weight, bias = TensorMetadata(), object(), object()
        for backend in self.backends:
            for op in self.audit.OPERATIONS:
                function = getattr(self.backends[backend], op)
                self.assertIs(self.registry.get_implementation(op, backend=backend), function)
                self.assertIs(function.__wrapped__, self.original)
                self.assertEqual(inspect.signature(function), inspect.signature(self.original))
                self.assertEqual(function.__name__, self.original.__name__)
                self.assertIs(function(tensor, weight, bias=bias), self.result)
                self.assertTrue(summary["operations"][backend + "." + op]["wraps_existing_row_guard"])
            self.assertIs(self.backends[backend].unrelated, self.other)
        self.assertTrue(all(x is tensor and w is weight and b is bias for x, w, b in self.calls))
        stored = json.loads(self.log.read_text())
        for entry in stored["operations"].values():
            self.assertEqual(entry["attempted_calls"], 1)
            self.assertEqual(entry["successful_calls"], 1)
            self.assertEqual(entry["first_call"]["tensor_arguments"], {
                "args[0]": {"shape": [2, 3], "dtype": "torch.float32", "device": "cpu"}})

    def test_exception_object_and_arguments_are_preserved(self):
        failure = ValueError("original failure")
        tensor = TensorMetadata()

        def raising(*args, **kwargs):
            self.assertIs(kwargs["x"], tensor)
            raise failure

        self.backends["cuda"].int8_linear = raising
        self.install()
        with self.assertRaises(ValueError) as caught:
            self.backends["cuda"].int8_linear(x=tensor)
        self.assertIs(caught.exception, failure)
        entry = json.loads(self.log.read_text())["operations"]["cuda.int8_linear"]
        self.assertEqual(entry["failed_calls"], 1)
        self.assertEqual(entry["first_call"]["outcome"], "raised")
        self.assertEqual(entry["first_call"]["exception_type"], "ValueError")

    def test_first_call_periodic_and_explicit_flush(self):
        self.install(flush_every=3)
        function = self.backends["triton"].int8_linear
        function(TensorMetadata())
        first = json.loads(self.log.read_text())["operations"]["triton.int8_linear"]["first_call"]
        function(object())
        self.assertEqual(json.loads(self.log.read_text())["operations"]["triton.int8_linear"]["attempted_calls"], 1)
        function(object())
        self.assertEqual(json.loads(self.log.read_text())["operations"]["triton.int8_linear"]["attempted_calls"], 3)
        function(object())
        self.audit.flush()
        entry = json.loads(self.log.read_text())["operations"]["triton.int8_linear"]
        self.assertEqual(entry["attempted_calls"], 4)
        self.assertEqual(entry["first_call"], first)

    def test_missing_backend_or_operation_is_recorded(self):
        del self.backends["triton"]
        del self.backends["eager"].w4a8_int8_linear
        summary = self.install()
        self.assertEqual(summary["backends"]["triton"]["status"], "unavailable")
        self.assertEqual(summary["operations"]["eager.w4a8_int8_linear"]["status"], "unavailable")

    def test_unregistered_export_is_left_untouched(self):
        original_lookup = self.registry.get_implementation

        def lookup(op, *, backend):
            if backend == "eager":
                raise ValueError("disabled")
            return original_lookup(op, backend=backend)

        self.registry.get_implementation = lookup
        summary = self.install()
        self.assertEqual(summary["operations"]["eager.int8_linear"]["status"], "unavailable")
        self.assertIs(self.backends["eager"].int8_linear, self.original)

    def test_failed_registry_verification_rolls_back_all_exports(self):
        original_lookup = self.registry.get_implementation

        def lookup(op, *, backend):
            if backend == "triton":
                return self.original  # Simulate a registry caching the old alias.
            return original_lookup(op, backend=backend)

        self.registry.get_implementation = lookup
        with self.assertRaisesRegex(RuntimeError, "did not resolve"):
            self.install()
        for backend in self.backends.values():
            for op in self.audit.OPERATIONS:
                self.assertIs(getattr(backend, op), self.original)
        self.assertIsNone(self.audit._active_auditor)

    def test_reinstall_is_idempotent_and_rejects_changed_hooks(self):
        self.install()
        function = self.backends["cuda"].int8_linear
        self.install()
        self.assertIs(self.backends["cuda"].int8_linear, function)
        self.backends["cuda"].int8_linear = self.original
        with self.assertRaisesRegex(RuntimeError, "changed"):
            self.install()

    def test_logging_failures_do_not_replace_results_or_exceptions(self):
        failure = ValueError("operator failure during log outage")

        def raising(x):
            raise failure

        self.backends["triton"].int8_linear = raising
        self.install()
        with patch.object(self.audit.os, "replace", side_effect=OSError("fixture write failure")):
            self.assertIs(self.backends["cuda"].int8_linear(TensorMetadata()), self.result)
            with self.assertRaises(ValueError) as caught:
                self.backends["triton"].int8_linear(TensorMetadata())
            self.assertIs(caught.exception, failure)
        self.assertEqual(len(self.audit._active_auditor.data["logging_errors"]), 1)


try:
    import torch
except ImportError:
    torch = None


@unittest.skipIf(torch is None, "snapshot CPU checks require existing torch; no installation needed")
class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.module = load_file("pair_snapshot_test", ROOT / "extensions/H3PairAudit/__init__.py")
        self.refs = [
            {"kind": "image", "latent_h": 2, "latent_w": 2,
             "latent": torch.arange(96, dtype=torch.float32).reshape(1, 24, 1, 2, 2)},
            {"kind": "video", "latent_t": 2, "latent_h": 2, "latent_w": 2, "ref_audio_t": 0,
             "latent": torch.arange(192, dtype=torch.float32).reshape(1, 24, 2, 2, 2)},
        ]
        self.positive = [[torch.arange(12, dtype=torch.bfloat16).reshape(1, 3, 4), {
            "minimax_token_tags": torch.arange(3, dtype=torch.int64), "minimax_refs": self.refs}]]
        self.streams = (torch.zeros(1, 24, 2, 2, 2), torch.zeros(1, 32, 2, 4))
        self.target = {"samples": types.SimpleNamespace(unbind=lambda: self.streams)}
        self.positions = torch.arange(24, dtype=torch.float64).reshape(8, 3)
        self.segments = [(0, 3, "text"), (3, 8, "video")]
        owner = self

        class Layout:
            def __init__(self, text_len, t, h, w, audio_t, refs):
                owner.assertEqual((text_len, t, h, w, audio_t), (3, 2, 2, 2, 4))
                owner.assertIs(refs, owner.refs)
                self.seq_len, self.segments, self.position_ids = 8, owner.segments, owner.positions

        self.patch = patch.dict(sys.modules, {"comfy.ldm.minimax.model": types.SimpleNamespace(PackedLayout=Layout)})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        info = self.module._tensor_info
        self.common = {
            "schema": "h3-event-audit-v1", "run_id": "shared", "prompt": "fixture",
            "native_vae_calls": [{"latent": dict(info(ref["latent"]), tensor_file=f"tensor_blobs/{i}.pt"),
                                  "prepared_frames": {"tensor_file": f"tensor_blobs/prepared{i}.pt"}}
                                 for i, ref in enumerate(self.refs)],
            "qwen_presentation": [{"source": "shared encoder"}],
            "conditioning_embedding": info(self.positive[0][0]),
            "token_tags": dict(info(self.positive[0][1]["minimax_token_tags"]), tensor_file="tensor_blobs/tags.pt"),
            "target_latent_shapes": [list(t.shape) for t in self.streams],
            "packed_layout": {"seq_len": 8, "segments": [list(s) for s in self.segments],
                              "position_ids": dict(info(self.positions), tensor_file="tensor_blobs/positions.pt")},
        }
        self.source = self.root / "shared_conditioning.json"
        self.source.write_text(json.dumps(self.common))

    def snapshot(self, **kwargs):
        args = dict(positive=self.positive, target=self.target, source_audit_dir=str(self.root),
                    source_run_id="shared", run_id="baseline")
        args.update(kwargs)
        return self.module.H3PairConditionSnapshot().snapshot(**args)

    def test_snapshot_preserves_identity_values_rng_and_source_provenance(self):
        rng = torch.get_rng_state().clone()
        tensors = [self.positive[0][0], self.positive[0][1]["minimax_token_tags"]] + [ref["latent"] for ref in self.refs] + list(self.streams)
        before = [t.clone() for t in tensors]
        source_bytes = self.source.read_bytes()
        positive, target = self.snapshot()
        self.assertIs(positive, self.positive)
        self.assertIs(target, self.target)
        self.assertTrue(torch.equal(rng, torch.get_rng_state()))
        self.assertTrue(all(torch.equal(a, b) for a, b in zip(tensors, before)))
        manifest = json.loads((self.root / "baseline_conditioning.json").read_text())
        self.assertEqual(self.source.read_bytes(), source_bytes)
        verification = manifest.pop("pair_snapshot")
        manifest["run_id"] = "shared"
        self.assertEqual(manifest, self.common)
        self.assertTrue(verification["verified"])
        self.assertFalse(verification["cache_usage"]["verified"])
        self.assertEqual(len(verification["actual"]["references"]), 2)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["baseline_conditioning.json", "shared_conditioning.json"])

    def test_embedding_ref_tags_and_target_drift_fail_without_output(self):
        variants = ("embedding", "refs", "tags", "target")
        for variant in variants:
            with self.subTest(variant=variant):
                positive = deepcopy(self.positive)
                target = self.target
                if variant == "embedding":
                    positive[0][0][0, 0, 0] += 1
                elif variant == "refs":
                    positive[0][1]["minimax_refs"][0]["latent"][0, 0, 0, 0, 0] += 1
                elif variant == "tags":
                    positive[0][1]["minimax_token_tags"][0] += 1
                else:
                    target = {"samples": types.SimpleNamespace(unbind=lambda: (self.streams[0], torch.zeros(1, 32, 2, 5)))}
                with self.assertRaises(ValueError):
                    self.snapshot(positive=positive, target=target)
                self.assertFalse((self.root / "baseline_conditioning.json").exists())

    def test_ref_metadata_and_dtype_drift_fail(self):
        self.refs[0]["latent_h"] = 4
        with self.assertRaisesRegex(ValueError, "metadata"):
            self.snapshot()
        self.refs[0]["latent_h"] = 2
        self.refs[0]["latent"] = self.refs[0]["latent"].to(torch.float64)
        with self.assertRaisesRegex(ValueError, "reference 0"):
            self.snapshot()

    def test_layout_drift_and_source_overwrite_fail(self):
        self.positions[0, 0] += 1
        with self.assertRaisesRegex(ValueError, "position_ids"):
            self.snapshot()
        with self.assertRaisesRegex(ValueError, "overwrite"):
            self.snapshot(run_id="shared")
        with self.assertRaisesRegex(ValueError, "filename"):
            self.snapshot(run_id="../escape")


class ImportTests(unittest.TestCase):
    def test_modules_do_not_import_torch_or_comfy_at_import_time(self):
        snippet = "import importlib.util, sys\n"
        for index, path in enumerate((ROOT / "scripts/backend_dispatch_audit.py", ROOT / "extensions/H3PairAudit/__init__.py")):
            snippet += f"s = importlib.util.spec_from_file_location('audit{index}', {str(path)!r}); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
        snippet += "assert 'torch' not in sys.modules; assert 'comfy' not in sys.modules\n"
        result = subprocess.run([sys.executable, "-c", snippet], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
