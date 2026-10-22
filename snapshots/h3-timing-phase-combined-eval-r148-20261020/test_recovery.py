"""Small synthetic receipt tests against the real reviewed book source binding."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import prepare_comparison as pc
import prepare_recovered_book as rb


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=pc.ROOT)
        self.root = Path(self.tmp.name)
        self.case = next(c for c in pc.read(pc.ROOT / "EVALUATION_MANIFEST.json")["cases"]
                         if c["source_id"] == "long_0039")
        self.binding = Path(self.case["R148"]["producer_case"]) / "audit/recovery_decode/BINDING.json"
        d = pc.read(self.binding)
        run = d["run_id"]
        self.video = self.root / (run + "_recovered.mp4")
        self.video.write_bytes(b"synthetic recovered video")
        owner = dict(pid=900, uid=1004, start_ticks="100", cmdline_sha256="c" * 64,
                     boot_id="151f0a91-4214-411e-b9f1-9a2f5ae44371")
        source = {
            "snapshot": d["files"][f"audit/x0/{run}/sampler_final.pt"],
            "manifest": d["files"][f"audit/x0/{run}/manifest.json"],
            "router": d["files"][f"audit/router/{run}.json"],
            "original_nfe": 20, "original_routed_calls": 450,
            "original_attention_calls": 1000, "new_dit_forwards": 0,
            "metadata": dict(snapshot_kind="sampler_final", sigma_video=0, sigma_audio=0,
                             normalization_stage="after_process_latent_out",
                             run_id=run, geometry=d["geometry"], seed=self.case["seed"], total_steps=20),
        }
        video = dict(file=d["case_root"] + "/audit/recovery_decode/attempt1/" + self.video.name,
                     bytes=self.video.stat().st_size, sha256=pc.bound(self.video)["sha256"],
                     properties=dict(width=1312, height=736, frames=107, fps="24/1"))
        self.result = dict(
            schema="r148-book-final-decode-result-v1", passed=True, run_id=run,
            role="fixed_phase", decoder_owner=copy.deepcopy(owner), source=source,
            producer_seal_sha256=d["producer_seal_sha256"], binding_sha256=rb.BINDING_SHA,
            recovery_script_sha256=rb.SCRIPT_SHA, video=video, valid_frames=106,
            crop=None, native_audio_preserved=True, started_unix=100, finished_unix=120,
        )
        self.release = dict(schema="r148-book-decode-release-v1", decoder_owner=copy.deepcopy(owner),
                            exit_code=0, process_absent=True, own_cuda_absent=True,
                            released=True, failure=None)
        self.gate = dict(schema="r148-book-final-decode-recovery-gate-v1", passed=True,
                         run_id=run, role="fixed_phase", source_attempt_complete=False,
                         source_attempt=d["source_attempt"], producer_seal_sha256=d["producer_seal_sha256"],
                         binding_sha256=rb.BINDING_SHA, decoder_owner=owner, video=video,
                         source=source, valid_frames=106, new_dit_forwards=0)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self):
        result, release, gate = [self.root / n for n in
                                 ("DECODE_RESULT.json", "RELEASE.json", "RECOVERY_GATE.json")]
        result.write_text(json.dumps(self.result))
        release.write_text(json.dumps(self.release))
        self.gate["decode_result"], self.gate["release"] = pc.bound(result), pc.bound(release)
        gate.write_text(json.dumps(self.gate))
        props = dict(width=1312, height=736, nb_read_frames="107", avg_frame_rate="24/1")
        with patch.object(rb, "inspect", return_value=props):
            return rb.validate_recovery(self.case, self.video, gate, result, release, self.binding)

    def test_recovery_retains_interruption_and_zero_new_dit(self):
        proof = self.check()
        self.assertFalse(proof["source_attempt_complete"])
        self.assertEqual(proof["new_dit_forwards"], 0)
        self.assertNotIn("complete", proof)

    def test_old_attempt_must_remain_incomplete(self):
        self.gate["source_attempt_complete"] = True
        with self.assertRaisesRegex(ValueError, "interrupted"):
            self.check()

    def test_nonfinal_snapshot_rejected(self):
        self.result["source"]["metadata"]["sigma_video"] = 0.1
        with self.assertRaisesRegex(ValueError, "endpoint"):
            self.check()

    def test_extra_dit_rejected(self):
        self.gate["new_dit_forwards"] = 1
        with self.assertRaisesRegex(ValueError, "gate"):
            self.check()

    def test_other_owner_release_rejected(self):
        self.release["decoder_owner"]["start_ticks"] = "101"
        with self.assertRaisesRegex(ValueError, "generation"):
            self.check()

    def test_unreleased_decoder_rejected(self):
        self.release["own_cuda_absent"] = False
        with self.assertRaisesRegex(ValueError, "release"):
            self.check()

    def test_changed_output_rejected(self):
        self.video.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "video differs"):
            self.check()

    def test_wrong_effective_domain_rejected(self):
        self.gate["valid_frames"] = 107
        with self.assertRaisesRegex(ValueError, "gate"):
            self.check()


if __name__ == "__main__":
    unittest.main()
