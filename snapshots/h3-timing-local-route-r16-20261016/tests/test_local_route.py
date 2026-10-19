import copy
import ast
import hashlib
import json
from pathlib import Path
import sys
import unittest

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "extensions"))
from H3LocalTemporalRouter.core import route_attention
from H3TemporalRouter.core import route_attention as sealed_route
from H3LocalTemporalRouter.mask import (QueryGain, build_source_mask, capsule,
                                       distance_to_segment, load_mask, pose_at)


def dense_attention(q, k, v):
    logits = q @ k.transpose(-1, -2) / q.shape[-1]**0.5
    return logits.softmax(-1) @ v, logits.logsumexp(-1)


class LocalRouteTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        gen = torch.Generator().manual_seed(1921)
        self.q, self.k, self.v = [torch.randn((1, 2, 341, 4), generator=gen) for _ in range(3)]
        self.plan = {"frame_rows": 4, "latent_interval_half_open": [14, 20],
                     "query_interval_half_open": [229, 253], "reference_video_segment": [5, 173]}

    def run_route(self, gain, **kwargs):
        return route_attention(self.q, self.k, self.v, 2, self.plan, mode="mass_preserve",
                               attention=dense_attention, query_gain=gain, **kwargs)

    def test_zero_native_exact_and_one_full_exact(self):
        zero, one = [QueryGain(torch.full((6, 2, 2), x), (6, 2, 2)) for x in (0., 1.)]
        native = sealed_route(self.q, self.k, self.v, 2, self.plan, mode="native", attention=dense_attention)
        full = sealed_route(self.q, self.k, self.v, 2, self.plan, mode="mass_preserve", attention=dense_attention)
        self.assertTrue(torch.equal(self.run_route(zero), native))
        self.assertTrue(torch.equal(self.run_route(one), full))

    def test_partial_matches_dense_probability_mass_and_preserves_inputs(self):
        coefficients = torch.tensor([0., .25, .5, 1.]*6)
        gain = QueryGain(coefficients.reshape(6, 2, 2), (6, 2, 2))
        before = [x.clone() for x in (self.q, self.k, self.v)]
        rng = torch.get_rng_state().clone()
        got = self.run_route(gain)
        logits = self.q @ self.k.transpose(-1, -2) / 2
        weights = logits.softmax(-1)
        altered = weights.clone()
        for j in range(24):
            row = 229+j
            mass = weights[:, :, row, 5:173].sum(-1, keepdim=True)
            bin_index = 14 + j//4
            lo, hi = 5 + bin_index*4, 5 + (bin_index+1)*4
            aligned = logits[:, :, row, lo:hi].softmax(-1)
            altered[:, :, row, 5:173] *= 1-coefficients[j]
            altered[:, :, row, lo:hi] += coefficients[j]*mass*aligned
        expected = (altered @ self.v).transpose(1, 2).reshape(1, 341, 8)
        torch.testing.assert_close(got, expected, rtol=1e-5, atol=2e-6)
        torch.testing.assert_close(altered.sum(-1), weights.sum(-1), rtol=1e-6, atol=1e-6)
        torch.testing.assert_close(altered[:, :, :, 5:173].sum(-1),
                                   weights[:, :, :, 5:173].sum(-1), rtol=1e-6, atol=1e-6)
        self.assertTrue(torch.equal(altered[:, :, :, :5], weights[:, :, :, :5]))
        self.assertTrue(torch.equal(altered[:, :, :, 173:], weights[:, :, :, 173:]))
        native = sealed_route(self.q, self.k, self.v, 2, self.plan, mode="native", attention=dense_attention)
        unchanged = list(range(229)) + [229+j for j in range(24) if coefficients[j] == 0] + list(range(253, 341))
        self.assertTrue(torch.equal(got[:, unchanged], native[:, unchanged]))
        self.assertTrue(all(torch.equal(a,b) for a,b in zip(before, (self.q,self.k,self.v))))
        self.assertTrue(torch.equal(rng, torch.get_rng_state()))

    def test_invalid_gain_and_wrong_mode(self):
        for bad in (float("nan"), float("inf"), -0.1, 1.1):
            values = torch.zeros((6,2,2)); values[0,0,0] = bad
            with self.assertRaises(ValueError): QueryGain(values, (6,2,2))
        with self.assertRaises(ValueError): QueryGain(torch.zeros((1,)), (6,2,2))
        gain = QueryGain(torch.zeros((6,2,2)), (6,2,2))
        with self.assertRaises(ValueError):
            route_attention(self.q,self.k,self.v,2,self.plan,mode="hard_route",query_gain=gain,attention=dense_attention)
        with self.assertRaises(ValueError): gain.on(self.q, 25)

    def test_source_mask_reproducible_and_uniform_sum(self):
        expected = json.loads((ROOT/"configs/source_query_mask.json").read_text())
        self.assertEqual(json.loads(json.dumps(build_source_mask(ROOT/"configs/source_pose.json"))), expected)
        for row in expected["bin_statistics"]:
            self.assertLess(abs(row["roi_sum"]-row["uniform_sum"]), 1e-5)
        path = ROOT/"configs/source_query_mask.json"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        for variant in ("roi", "uniform"):
            gain, _ = load_mask(str(path), digest, variant)
            self.assertEqual(tuple(gain.tensor.shape), (1,1,5658,1))
        with self.assertRaises(ValueError):load_mask(str(path), "0"*64, "roi")
        with self.assertRaises(ValueError):load_mask(str(path), digest, "unknown")

    def test_geometry_interpolation_and_missing_detection(self):
        pose = json.loads((ROOT/"configs/source_pose.json").read_text())
        mid = pose_at(pose, 48.5); a=pose_at(pose,48); b=pose_at(pose,49)
        for joint in (7,8,9,10):
            for axis in (0,1):self.assertEqual(mid[joint][axis], (a[joint][axis]+b[joint][axis])/2)
        bad=copy.deepcopy(pose);bad["frames"][48]["persons"][0]["coco17_score"][7]=0.1
        with self.assertRaises(ValueError):pose_at(bad,48.5)
        self.assertEqual(capsule(32),1);self.assertEqual(capsule(64),0)
        self.assertAlmostEqual(capsule(48),.5)
        self.assertEqual(distance_to_segment((3,4),(0,0),(0,0)),5)
        self.assertEqual(distance_to_segment((5,3),(0,0),(10,0)),3)

    def test_frozen_graph_and_geometry_evidence(self):
        parent=json.loads((ROOT/"configs/parent_full_graph.json").read_text())
        for variant in ("roi","uniform"):
            name=f"r16_s05_{variant}_6to14"
            graph=json.loads((ROOT/"configs"/(name+".json")).read_text())
            self.assertEqual(graph['50']['inputs']['mask_variant'],variant)
            canonical=json.loads(json.dumps(graph).replace("timing_local_route_r16_20261016","timing_spatial_r3_20261016").replace(name,"r3_s05_full_6to14"))
            canonical['50']=parent['50'];self.assertEqual(canonical,parent)
        evidence=json.loads((ROOT/"configs/geometry_source_evidence.json").read_text())
        self.assertEqual(len(evidence['frames']),141)
        self.assertTrue(all(abs(f['time']-f['index']/24)<1e-8 and f['rotation'] in (None,0) for f in evidence['frames']))

    def test_auxiliary_audit_root_matches_both_formal_graphs(self):
        source=(ROOT/'extensions/H3EventAudit/__init__.py').read_text()
        constants=[node.value for node in ast.walk(ast.parse(source)) if isinstance(node,ast.Constant) and isinstance(node.value,str)]
        expected='/data5/researcher/h3_runs/timing_local_route_r16_20261016'
        self.assertIn(expected,constants)
        self.assertFalse(any('timing_spatial_r3_20261016' in value for value in constants))
        for variant in ('roi','uniform'):
            graph=json.loads((ROOT/'configs'/f'r16_s05_{variant}_6to14.json').read_text())
            for node in ('5','6'):
                self.assertEqual(graph[node]['inputs']['audit_dir'],expected+'/audit')


if __name__ == "__main__":
    unittest.main()
