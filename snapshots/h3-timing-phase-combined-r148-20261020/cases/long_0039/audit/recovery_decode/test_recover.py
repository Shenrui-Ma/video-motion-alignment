import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("recover", Path(__file__).with_name("recover.py"))
recover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recover)


class EndpointContract(unittest.TestCase):
    def setUp(self):
        self.d = {"run_id": "book", "geometry": {"frames": 107}}
        self.meta = {"snapshot_kind": "sampler_final", "sigma_video": 0, "sigma_audio": 0,
                     "normalization_stage": "after_process_latent_out", "run_id": "book",
                     "geometry": {"frames": 107}, "seed": 2026101701, "total_steps": 20}
        self.manifest = {"status": "complete", "callback_count": 20,
                         "captures": [{"step_zero_based": i} for i in range(20)],
                         "final_sampler_result": {"file": "sampler_final.pt", **self.meta}}
        self.router = {"run_id": "book", "completed_forward_calls": 20,
                       "completed_calls": 1000, "native_override_calls": 1000,
                       "routed_calls": 450, "calls_by_forward": [50] * 20,
                       "routed_by_forward": [0] * 6 + [50] * 9 + [0] * 5}

    def check(self):
        recover.validate_records(self.d, self.meta, self.manifest, self.router)

    def test_true_endpoint(self):
        self.check()

    def test_last_x0_rejected_even_with_twenty_callbacks(self):
        self.meta["snapshot_kind"] = "x0_estimate"
        self.meta["sigma_video"] = .38709676
        with self.assertRaisesRegex(ValueError, "sigma-zero"):
            self.check()

    def test_partial_sampling_rejected(self):
        self.manifest["callback_count"] = 15
        with self.assertRaisesRegex(ValueError, "incomplete sampler"):
            self.check()

    def test_route_budget_rejected(self):
        self.router["routed_calls"] = 400
        with self.assertRaisesRegex(ValueError, "runtime execution"):
            self.check()

    def test_mismatched_metadata_rejected(self):
        self.manifest["final_sampler_result"]["seed"] += 1
        with self.assertRaisesRegex(ValueError, "metadata mismatch"):
            self.check()

    def test_native_encoder_preserves_original_arguments(self):
        observed = {}
        class Video:
            def save_to(self, filename, **kwargs):
                observed.update(file=filename, **kwargs)
        class Create:
            @staticmethod
            def execute(images, **kwargs):
                observed["create"] = {"images": images, **kwargs}
                return type("Result", (), {"result": [Video()]})()
        class Types:
            VideoContainer = staticmethod(lambda x: x)
            VideoCodec = staticmethod(lambda x: x)
        graph = {"13": {"inputs": {"fps": 24.0, "bit_depth": 8}},
                 "14": {"inputs": {"format": "mp4", "codec": "h264",
                                  "codec.encoding.crf": 16.0}}}
        original = copy.deepcopy(graph)
        recover.encode("pixels", "audio", graph, Path("out.mp4"), Create, Types)
        self.assertEqual(observed["create"], {"images": "pixels", "audio": "audio",
                                              "fps": 24.0, "bit_depth": 8})
        self.assertEqual((observed["format"], observed["codec"], observed["crf"]),
                         ("mp4", "h264", 16.0))
        self.assertEqual(graph, original)


if __name__ == "__main__":
    unittest.main()
