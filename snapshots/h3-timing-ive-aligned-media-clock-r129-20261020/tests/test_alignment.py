import ast
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

import torch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("alignment", ROOT / "extensions/H3TemporalRouter/alignment.py")
alignment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alignment)


def model_definitions(canonical=False):
    source = (ROOT / "design/H3_model.py").read_text()
    if hashlib.sha256(source.encode()).hexdigest() != "0d5edcf32b4b98d704eaa51de60ed71f507d0c7d9845947f566647dc76fb8dfe":
        raise ValueError("bound model source changed")
    if canonical:
        source = source.replace("cursor += max(float(rt), sum(_video_t_spans(vt)))", "cursor += 0.0")
    names = {"_axis_from_sqrt_area", "_frame_grid", "_video_t_spans", "_video_t_grid",
             "_ref_t_span", "_audio_grid", "_video_grid", "PackedLayout", "rope_rotation_table"}
    nodes = [n for n in ast.parse(source).body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    if {n.name for n in nodes} != names:
        raise ValueError("bound model definitions incomplete")
    module = ast.Module(body=nodes, type_ignores=[])
    env = {"torch": torch, "math": math, "FRAME_PER_TOKEN": (1, 4, 4, 4, 4), "FRAME_RESCALE": 5.0 / 3.0}
    exec(compile(module, "bound_H3_definitions", "exec"), env)
    return env


MODEL = model_definitions()
CANONICAL = model_definitions(True)
ACTUAL = json.loads((ROOT / "design/R122_actual_native_router.json").read_text())


def fixture(small=False):
    metadata = copy.deepcopy(ACTUAL["metadata"])
    if small:
        metadata.update(text_len=7, context_shape=[1, 7, 5120])
        metadata["refs"][0].update(latent_t=3, latent_h=4, latent_w=6, latent_shape=[1, 24, 3, 4, 6], frame_rows=6)
    r = metadata["refs"][0]
    args = (metadata["text_len"], r["latent_t"], r["latent_h"], r["latent_w"], 5 if small else 178)
    return metadata, MODEL["PackedLayout"](*args, refs=metadata["refs"]), args


class Diffusion:
    def rope_freqs(self, positions, device):
        inv = torch.exp(-math.log(10000.0) * torch.arange(16, dtype=torch.float32) / 16).to(device)
        half = (positions.to(torch.float32).to(device).unsqueeze(-1) * inv).reshape(-1, 48)
        return torch.cat((half, half), -1)


class AlignmentTests(unittest.TestCase):
    def test_actual_registered_shape_and_origin(self):
        meta, layout, _ = fixture()
        before = layout.position_ids.clone()
        result, report = alignment.aligned_positions(layout, meta)
        self.assertEqual(report["reference_origin"], 4839.0)
        self.assertAlmostEqual(report["original_target_origin"], 5017.333333333333)
        self.assertTrue(torch.equal(layout.position_ids, before))
        self.assertTrue(report["target_video_matches_reference_all_coordinates"])
        self.assertFalse(torch.equal(result, before))

    def test_matches_actual_layout_with_reference_cursor_advance_disabled(self):
        for small in (False, True):
            meta, layout, args = fixture(small)
            canonical = CANONICAL["PackedLayout"](*args, refs=meta["refs"])
            result, _ = alignment.aligned_positions(layout, meta)
            self.assertTrue(torch.equal(result, canonical.position_ids))
            self.assertEqual(layout.segments, canonical.segments)
            self.assertTrue(torch.equal(layout.img_pos, canonical.img_pos))
            self.assertTrue(torch.equal(layout.img_update, canonical.img_update))
            self.assertTrue(torch.equal(layout.audio_pos, canonical.audio_pos))

    def test_preserves_text_reference_space_and_target_relative_time(self):
        meta, layout, _ = fixture()
        result, _ = alignment.aligned_positions(layout, meta)
        aa = layout.segments[2][0]
        self.assertTrue(torch.equal(result[:aa], layout.position_ids[:aa]))
        self.assertTrue(torch.equal(result[:, 1:], layout.position_ids[:, 1:]))
        old = layout.position_ids[aa:, 0]
        new = result[aa:, 0]
        self.assertTrue(torch.allclose(new - new[0], old - old[0], atol=1e-10, rtol=0))

    def test_no_rng_consumption(self):
        meta, layout, _ = fixture(True)
        before = torch.random.get_rng_state().clone()
        alignment.aligned_positions(layout, meta)
        self.assertTrue(torch.equal(before, torch.random.get_rng_state()))

    def test_rejects_reference_scope_and_batch(self):
        for change in ("two_refs", "image", "ref_audio", "mixed_batch", "grid"):
            meta, layout, _ = fixture(True)
            if change == "two_refs": meta["refs"].append(copy.deepcopy(meta["refs"][0]))
            if change == "image": meta["refs"][0]["kind"] = "image"
            if change == "ref_audio": meta["refs"][0]["ref_audio_t"] = 5
            if change == "mixed_batch": meta["context_shape"][0] = 2
            if change == "grid": meta["refs"][0]["latent_w"] += 2
            with self.subTest(change=change), self.assertRaises(ValueError):
                alignment.aligned_positions(layout, meta)

    def test_rejects_position_or_segment_changes(self):
        for change in ("spatial", "time", "audio", "kind", "dtype"):
            meta, layout, _ = fixture(True)
            if change == "spatial": layout.position_ids[-1, 1] += 1
            if change == "time": layout.position_ids[-1, 0] += 1
            if change == "audio": layout.position_ids[layout.segments[2][0], 0] += 1
            if change == "kind": layout.segments[1] = (*layout.segments[1][:2], "cond")
            if change == "dtype": layout.position_ids = layout.position_ids.float()
            with self.subTest(change=change), self.assertRaises(ValueError):
                alignment.aligned_positions(layout, meta)

    def state(self, directory, enabled=True):
        meta, layout, _ = fixture(True)
        diffusion = Diffusion()
        table = MODEL["rope_rotation_table"](diffusion.rope_freqs(layout.position_ids, "cpu"), torch.float32)
        state = alignment.AlignmentState(meta, diffusion, MODEL["rope_rotation_table"], "test", directory, enabled)
        args = {"layout": layout, "rope_freqs": table, "img": torch.ones(layout.seq_len, 3), "transformer_options": {}}
        return state, args

    def test_1000_blocks_and_cached_table_do_not_modify_original_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            state, args = self.state(directory)
            original = args["rope_freqs"].clone()
            img = args["img"]
            seen = []
            def native(local, extra):
                self.assertIs(local["layout"], args["layout"])
                self.assertIs(local["img"], img)
                self.assertIs(local["transformer_options"], args["transformer_options"])
                seen.append(local["rope_freqs"])
                return {"img": local["img"]}
            patches = [alignment.AlignedBlockPatch(state, native, i) for i in range(50)]
            rng = torch.random.get_rng_state().clone()
            for _ in range(20):
                for patch in patches:
                    self.assertIs(patch(args, {})["img"], img)
            self.assertEqual(state.audit["calls_by_block"], [20] * 50)
            self.assertEqual(state.audit["calls_by_forward"], [50] * 20)
            self.assertEqual(state.audit["rotation_table_builds"], 1)
            self.assertEqual(state.audit["status"], "complete")
            self.assertTrue(all(t is seen[0] for t in seen))
            self.assertTrue(torch.equal(args["rope_freqs"], original))
            self.assertTrue(torch.equal(rng, torch.random.get_rng_state()))
            with self.assertRaises(ValueError): patches[0](args, {})

    def test_disabled_passes_original_table_by_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            state, args = self.state(directory, False)
            self.assertIs(state.rotation_for(args, 0), args["rope_freqs"])
            self.assertEqual(state.audit["rotation_table_builds"], 0)

    def test_rejects_mutated_layout_between_steps(self):
        with tempfile.TemporaryDirectory() as directory:
            state, args = self.state(directory)
            for i in range(50): state.rotation_for(args, i); state.completed(i)
            args["layout"].position_ids[0, 0] += 1
            with self.assertRaises(ValueError): state.rotation_for(args, 0)

    def test_rejects_wrong_order_new_layout_or_dtype(self):
        with tempfile.TemporaryDirectory() as directory:
            state, args = self.state(directory)
            with self.assertRaises(ValueError): state.rotation_for(args, 1)
            state.rotation_for(args, 0); state.completed(0)
            wrong = dict(args); wrong["layout"] = copy.deepcopy(args["layout"])
            with self.assertRaises(ValueError): state.rotation_for(wrong, 1)
            wrong = dict(args); wrong["rope_freqs"] = args["rope_freqs"].double()
            with self.assertRaises(ValueError): state.rotation_for(wrong, 1)


if __name__ == "__main__":
    torch.set_num_threads(2)
    unittest.main()
