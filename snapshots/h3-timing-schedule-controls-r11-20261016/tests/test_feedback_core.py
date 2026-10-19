import json
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import torch

from test_feedback_support import (config, make_state, make_guider, execute_toy,
                                   observation, cpu_attention, run_blocks)
from H3FeedbackRouter.core import FeedbackConfig, extract_reference, official_basic_guider_class
from H3FeedbackRouter.observer import next_decision, next_hold_decision


class FeedbackCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_decision_boundaries_and_hysteresis(self):
        active = False
        observed = []
        reasons = []
        for lag in [5, 3, 2, 3, -4, 4, None]:
            active, reason = next_decision(observation(lag), active)
            observed.append(active)
            reasons.append(reason)
        self.assertEqual(observed, [True, True, False, False, False, True, False])
        self.assertEqual(reasons[-3:], ["OFF_ADVANCED", "ON_DELAYED", "OFF_UNKNOWN"])
        for lag in (-2, -1, 0, 1, 2):
            self.assertEqual(next_decision(observation(lag), True), (False, "OFF_ALIGNED"))
        self.assertEqual(next_decision(observation(-3), True), (False, "OFF_ADVANCED"))

    def test_causal_prefix_terminal_and_fixed_replay(self):
        with tempfile.TemporaryDirectory() as d:
            # First observation after forward5 opens6; unknown pauses12; endpoint4 only audits.
            lags = [5, 3, 2, 3, -4, 4, None, 0, 0, 0, 0, 0, 0, 4, 4]
            state = make_state(d, lags)
            callbacks = []
            output = execute_toy(state, callback=lambda *args: callbacks.append(args))
            expected = [6, 7, 8, 9, 11, 19]
            self.assertEqual(state.active_indices, expected)
            self.assertEqual(state.audit["routed_by_forward"], [50 if i in expected else 0 for i in range(20)])
            self.assertEqual(state.audit["completed_calls"], 1000)
            self.assertEqual(state.audit["native_override_calls"], 1000)
            self.assertEqual([a[0] for a in callbacks], list(range(20)))
            records = state.audit["feedback"]["observations"]
            self.assertEqual([r["callback_index"] for r in records], list(range(5, 20)))
            self.assertFalse(records[0]["current_forward_active"])
            self.assertTrue(records[0]["next_active"])
            self.assertEqual(records[0]["next_forward_index"], 6)
            self.assertTrue(records[-1]["terminal_audit_only"])
            self.assertIsNone(records[-1]["next_forward_index"])
            self.assertIsNone(records[-1]["next_active"])
            self.assertEqual(state.pending_for, 19)
            self.assertEqual(state.audit["status"], "complete")
            self.assertEqual(records[2]["reason"], "HOLD_FIRST_ALIGNED")
            self.assertEqual(records[2]["aligned_streak_after"], 1)
            self.assertEqual(records[3]["aligned_streak_after"], 0)
            fixed = make_state(d, lags, policy="fixed", fixed="6,7,8,9,11,19", run_id="fixed")
            replay = execute_toy(fixed)
            self.assertTrue(torch.equal(output, replay))
            self.assertEqual(fixed.active_indices, expected)

    def test_hold_two_consecutive_only_and_all_reset_cases(self):
        for lag in (-2, -1, 0, 1, 2):
            self.assertEqual(next_hold_decision(observation(lag), True, 0),
                             (True, "HOLD_FIRST_ALIGNED", 1))
            self.assertEqual(next_hold_decision(observation(lag), True, 1),
                             (False, "OFF_ALIGNED", 0))
            self.assertEqual(next_hold_decision(observation(lag), False, 0),
                             (False, "OFF_ALIGNED", 0))
        for lag, expected in [(4, (True, "ON_DELAYED", 0)),
                              (3, (True, "HOLD_LAG3", 0)),
                              (-3, (False, "OFF_ADVANCED", 0)),
                              (None, (False, "OFF_UNKNOWN", 0))]:
            self.assertEqual(next_hold_decision(observation(lag), True, 1), expected)
        for invalid in (-1, 2, True, 0.0):
            with self.assertRaises(ValueError):
                next_hold_decision(observation(0), True, invalid)

    def test_runtime_stops_after_two_and_resets_interruption(self):
        with tempfile.TemporaryDirectory() as d:
            lags = [5, 0, 0, 4, 0, 3, 0, 0, None, 4, -3, 4, 0, 0, 0]
            state = make_state(d, lags)
            execute_toy(state)
            self.assertEqual(state.active_indices, [6, 7, 9, 10, 11, 12, 15, 17, 18])
            rows = state.audit["feedback"]["observations"]
            self.assertEqual([r["aligned_streak_after"] for r in rows],
                             [0, 1, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0])
            self.assertEqual(rows[2]["reason"], "OFF_ALIGNED")
            self.assertEqual(rows[5]["reason"], "HOLD_LAG3")

    def test_terminal_proposal_cannot_mutate_streak_or_next_state(self):
        with tempfile.TemporaryDirectory() as d:
            state = make_state(d, [0] * 13 + [4, 0])
            execute_toy(state)
            row = state.audit["feedback"]["observations"][-1]
            self.assertEqual(row["reason"], "HOLD_FIRST_ALIGNED")
            self.assertEqual(row["aligned_streak_proposed"], 1)
            self.assertEqual(row["aligned_streak_before"], 0)
            self.assertEqual(row["aligned_streak_after"], 0)
            self.assertEqual(state.aligned_streak, 0)
            self.assertEqual(state.pending_for, 19)

    def test_off_and_all_aligned_are_identical_for_packed_and_nested(self):
        with tempfile.TemporaryDirectory() as d:
            a = make_state(d, [7], policy="off", run_id="off")
            b = make_state(d, [0], run_id="aligned")
            out_a = execute_toy(a)
            out_b = execute_toy(b, nested_callback=True)
            self.assertTrue(torch.equal(out_a, out_b))
            self.assertEqual(a.active_indices, [])
            self.assertEqual(a.audit["feedback"]["observations"][0]["applied_reason"], "POLICY_OFF")

    def test_serial_cfg_double_forward_rejected_before_callback(self):
        with tempfile.TemporaryDirectory() as d:
            state = make_state(d)
            with self.assertRaisesRegex(ValueError, "preceding completed"):
                execute_toy(state, double_forward=True)
            self.assertEqual(state.audit["status"], "failed")

    def test_incomplete_sampler_fails(self):
        with tempfile.TemporaryDirectory() as d:
            state = make_state(d)
            with self.assertRaisesRegex(ValueError, "incomplete Euler20"):
                execute_toy(state, steps=19)

    def test_original_callback_exception_not_swallowed(self):
        with tempfile.TemporaryDirectory() as d:
            state = make_state(d)
            def fail(*_):
                raise RuntimeError("callback failure sentinel")
            with self.assertRaisesRegex(RuntimeError, "sentinel"):
                execute_toy(state, callback=fail)
            self.assertTrue(state.sampler_finished)
            self.assertEqual(state.audit["status"], "failed")

    def test_duplicate_run_and_used_state_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            state = make_state(d)
            with self.assertRaises(FileExistsError):
                make_state(d)
            execute_toy(state)
            with self.assertRaisesRegex(ValueError, "single-use"):
                execute_toy(state)

    def test_stale_decision_and_unstarted_forward_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            state = make_state(d)
            with self.assertRaisesRegex(ValueError, "outside"):
                state.latch_forward()
            state.sampler_entered = True
            state.forward_index = 5
            state.callback_count = 6
            state.audit["completed_forward_calls"] = 6
            state.pending_for = 5
            with self.assertRaisesRegex(ValueError, "stale"):
                state.latch_forward()

    def test_cfg_hook_and_wrong_reference_rejected(self):
        for kind in ("cfg", "negative", "hook", "reference", "state"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as d:
                state = make_state(d)
                guider = make_guider(state)
                if kind == "cfg":
                    guider.cfg = 2
                elif kind == "negative":
                    guider.original_conds["negative"] = []
                elif kind == "hook":
                    guider.model_options["disable_cfg1_optimization"] = True
                elif kind == "reference":
                    guider.original_conds["positive"][0]["minimax_refs"][0]["latent"] += 1
                else:
                    guider.model_options["transformer_options"]["patches_replace"]["dit"].pop(("double_block", 49))
                with self.assertRaises(ValueError):
                    execute_toy(state, guider=guider)

    def test_wrong_normalization_fails(self):
        with tempfile.TemporaryDirectory() as d:
            state = make_state(d)
            guider = make_guider(state)
            guider.inner_model.process_latent_out = lambda value: value
            with self.assertRaisesRegex(ValueError, "normalization"):
                execute_toy(state, guider=guider)

    def test_config_frozen_geometry_and_fixed_indices(self):
        with tempfile.TemporaryDirectory() as d:
            for fixed in ("5", "20", "6,6", "7,6", "6,", "a", "-1"):
                with self.subTest(fixed=fixed), self.assertRaises(ValueError):
                    config(d, policy="fixed", fixed=fixed)
            with self.assertRaises(ValueError):
                config(d, fixed="6")
            with self.assertRaises(ValueError):
                FeedbackConfig("feedback", "", 51, 65, 1312, 736, 141, "bad", d)
            self.assertEqual(config(d, policy="fixed", fixed="6, 19").indices, (6, 19))

    def test_reference_selected_by_kind_copied_and_metadata_has_no_tensor(self):
        with tempfile.TemporaryDirectory() as d:
            c = config(d)
            original = torch.zeros(c.shapes[0])
            video = {"kind": "video", "latent": original, "latent_t": 42,
                     "latent_h": 46, "latent_w": 82, "ref_audio_t": 0}
            image = {"kind": "image", "latent": torch.zeros((1, 24, 1, 2, 2)),
                     "latent_h": 2, "latent_w": 2}
            for refs in ([image, video], [video, image]):
                metadata, copied = extract_reference([[torch.zeros((1, 2, 3)), {"minimax_refs": refs}]], c)
                json.dumps(metadata)
                self.assertTrue(torch.equal(copied, original))
                self.assertNotEqual(copied.data_ptr(), original.data_ptr())
            with self.assertRaises(ValueError):
                extract_reference([[torch.zeros((1, 2, 3)), {"minimax_refs": [image, video, video]}]], c)

    def test_official_guider_module_alias_is_narrowly_recognized(self):
        class CFGBase:
            pass
        source = "class Guider_Basic(CFGBase):\n    def set_conds(self, positive):\n        self.inner_set_conds({'positive': positive})\n"
        loaded = []
        def load(path, name, contents=source):
            module_spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(module_spec)
            module.CFGBase = CFGBase
            sys.modules[name] = module
            loaded.append(name)
            exec(compile(contents, str(path), "exec"), module.__dict__)
            return module.Guider_Basic
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "nodes_custom_sampler.py"
            path.write_text(source)
            try:
                canonical = load(path, "_feedback_test_canonical")
                actual = load(path, str(path.with_suffix("")))
                self.assertIsNot(actual, canonical)
                self.assertTrue(official_basic_guider_class(actual, canonical))
                self.assertTrue(official_basic_guider_class(canonical, canonical))
                foreign = load(Path(d) / "other.py", "_feedback_test_foreign")
                self.assertFalse(official_basic_guider_class(foreign, canonical))
                modified = load(path, "_feedback_test_modified", source.replace("'positive': positive", "'negative': positive"))
                self.assertFalse(official_basic_guider_class(modified, canonical))
                subclass = type("Guider_Basic", (actual,), {})
                self.assertFalse(official_basic_guider_class(subclass, canonical))
                actual.predict_noise = lambda *_: None
                self.assertFalse(official_basic_guider_class(actual, canonical))
            finally:
                for name in loaded:
                    sys.modules.pop(name, None)


if __name__ == "__main__":
    unittest.main()
