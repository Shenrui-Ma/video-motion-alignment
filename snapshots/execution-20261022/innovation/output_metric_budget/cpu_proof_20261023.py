"""Local stdlib-only algebra checks; no models, GPU, network or runtime hooks.

The quantization example is a mathematical surrogate, not a CUDA-kernel test.
Run: python3 cpu_proof_20261023.py
"""
import ast
import hashlib
import json
import math
from pathlib import Path
import random
import time
import unittest

ROOT = Path(__file__).resolve().parent
MODEL = ROOT.parent / "partial_rope/sources/host41_model.py"


def dot(x, y):
    return sum(a * b for a, b in zip(x, y))


def mm(a, b):
    return [[dot(row, col) for col in zip(*b)] for row in a]


def transpose(a):
    return [list(x) for x in zip(*a)]


def quadratic(a, g):
    return sum(a[i] * g[i][j] * a[j]
               for i in range(len(a)) for j in range(len(a)))


def matrix_error(a, b):
    return max(abs(x-y) for ra, rb in zip(a, b) for x, y in zip(ra, rb))


def h4():
    return [[v / 2 for v in row] for row in
            [[1, 1, 1, -1], [1, 1, -1, 1],
             [1, -1, 1, 1], [-1, 1, 1, 1]]]


def gram(z):
    # z[probe][head][output]; common probes and coordinates for every head.
    h = len(z[0])
    return [[sum(dot(p[i], p[j]) for p in z) for j in range(h)]
            for i in range(h)]


def dense_effects(delta, weight, gates):
    """Independent dense linear oracle with actual per-probe output gate."""
    p_count, heads, width = len(delta), len(delta[0]), len(delta[0][0])
    result = []
    for p in range(p_count):
        rows = []
        for head in range(heads):
            full = [0.] * (heads * width)
            full[head*width:(head+1)*width] = delta[p][head]
            rows.append([dot(full, w) * gate
                         for w, gate in zip(weight, gates[p])])
        result.append(rows)
    return result


def paired_rotation_effects(delta, q_rot, scales, gates):
    """Tiny group=4/head=2 analogue of group=256/head=128 sparse path.

    Uses only the relevant four stored INT8 columns for each pair of heads.
    There is no full dequantized effective weight in this function.
    """
    rot = h4()
    p_count, heads = len(delta), len(delta[0])
    assert heads % 2 == 0 and len(delta[0][0]) == 2
    result = []
    for p in range(p_count):
        rows = []
        for head in range(heads):
            local_offset = (head % 2) * 2
            rotated = [sum(delta[p][head][i] * rot[local_offset+i][j]
                           for i in range(2)) for j in range(4)]
            group_start = (head // 2) * 4
            rows.append([
                dot(rotated, q[group_start:group_start+4]) * s * g
                for q, s, g in zip(q_rot, scales, gates[p])])
        result.append(rows)
    return result


def filter_candidate(candidate, g, prior=.25, cap=.5, near_null=1e-6):
    """Stdlib scalar transcription of the existing ray guard for CPU proofs.

    Returns the prior if the feasible ray loses linear utility; utility is
    checked by the caller. This filter does not solve the full convex QCQP.
    """
    base = [prior] * len(candidate)
    e0 = quadratic(base, g)
    diag = [g[i][i] for i in range(len(g))]
    d0 = sum(d * prior**2 for d in diag)
    if e0 <= near_null * d0 or d0 <= 0:
        return base, "near_null"
    x = [min(cap, max(0., v)) for v in candidate]
    e = quadratic(x, g)
    d = sum(w * v*v for w, v in zip(diag, x))
    scale = min(1., math.sqrt(e0 / e) if e > 0 else 1.,
                math.sqrt(d0 / d) if d > 0 else 1.)
    return [v*scale for v in x], "filtered"


def quantize_row_surrogate(row):
    scale = max(abs(v) for v in row) / 127
    if scale == 0:
        return list(row)
    return [round(v/scale) * scale for v in row]


def cost_table():
    h, d, i, o, p, group, tile, k, validation_p = 56, 128, 7168, 5376, 8, 256, 256, 32, 8
    return {
        "shape": {"heads":h,"head_dim":d,"input":i,"output":o,
                  "total_query_probes":p,"convrot_group":group,
                  "output_row_tile":tile,"sketch_k":k,"validation_queries":validation_p},
        "MAC": {
            "pair_sparse_projection":p*h*group*o,
            "rotate_sparse_head_inputs":p*h*d*group,
            "full_cross_head_gram":p*h*h*o,
            "pair_path_total":p*h*group*o+p*h*d*group+p*h*h*o,
            "one_gate_row_sketch_build":i*o*k,
            "blackbox_head_secants_base_plus_56_heads":p*(h+1)*i*o,
            "actual_quantized_validation_three_inputs":3*validation_p*i*o,
        },
        "bytes_FP32": {
            "temporary_weight_row_tile":tile*i*4,
            "temporary_effects_tile":p*h*tile*4,
            "rotated_sparse_inputs":p*h*group*4,
            "gram":h*h*4,
            "full_effects_if_retained":p*h*o*4,
            "full_float_weight_not_needed":i*o*4,
            "one_sketch_B":i*k*4,
        },
        "measured_runtime":False,
    }


class Proofs(unittest.TestCase):
    def test_pre_energy_equal_post_energy_unbounded(self):
        base, candidate = [.25,.25], [math.sqrt(.125),0.]
        self.assertAlmostEqual(dot(base,base), dot(candidate,candidate))
        for eps in [1e-1,1e-2,1e-3]:
            w = [1.,-1.+eps]
            ratio = dot(w,candidate)**2 / dot(w,base)**2
            self.assertAlmostEqual(ratio / (2/eps**2), 1., places=10)
            self.assertLessEqual(max(candidate), .5)

    def test_gate_changes_energy_even_for_identity_projection(self):
        base, candidate = [.25,.25], [math.sqrt(.125),0.]
        gate = [100.,1.]
        eb = sum((a*g)**2 for a,g in zip(base,gate))
        ec = sum((a*g)**2 for a,g in zip(candidate,gate))
        self.assertAlmostEqual(eb,625.0625)
        self.assertAlmostEqual(ec,1250.)
        self.assertGreater(ec/eb,1.999)

    def test_post_attention_residual_is_not_final_block_bound(self):
        # An allowed downstream linear map can multiply the local change.
        delta = .125
        for scale in [0.,1.,100.]:
            final_delta = delta + scale*delta
            self.assertAlmostEqual(final_delta**2/delta**2,(1+scale)**2)

    def test_cross_head_gram_psd_and_exact_linear_energy(self):
        rng = random.Random(20261023)
        delta = [[[rng.uniform(-1,1) for _ in range(2)] for _ in range(4)] for _ in range(3)]
        weight = [[rng.uniform(-1,1) for _ in range(8)] for _ in range(5)]
        gates = [[rng.uniform(-2,2) for _ in range(5)] for _ in range(3)]
        z = dense_effects(delta,weight,gates)
        g = gram(z)
        for _ in range(50):
            a = [rng.uniform(-1,1) for _ in range(4)]
            merged = [[sum(a[h]*p[h][o] for h in range(4)) for o in range(5)] for p in z]
            expected = sum(dot(row,row) for row in merged)
            self.assertGreaterEqual(quadratic(a,g),-1e-12)
            self.assertAlmostEqual(quadratic(a,g),expected,places=11)

    def test_sparse_group_rotation_equals_dense_effective_weight_with_gate(self):
        rng = random.Random(572)
        delta = [[[rng.uniform(-1,1) for _ in range(2)] for _ in range(4)] for _ in range(3)]
        q = [[rng.randint(-127,127) for _ in range(8)] for _ in range(7)]
        scales = [.003+i*.001 for i in range(7)]
        gates = [[rng.uniform(-2,2) for _ in range(7)] for _ in range(3)]
        weight = []
        for row,s in zip(q,scales):
            # Dense oracle explicitly reconstructs the effective matrix.
            weight.append([v*s for offset in [0,4]
                           for v in mm([row[offset:offset+4]],transpose(h4()))[0]])
        sparse = paired_rotation_effects(delta,q,scales,gates)
        dense = dense_effects(delta,weight,gates)
        for a,b in zip(sparse,dense):
            self.assertLess(matrix_error(a,b),1e-12)
        self.assertLess(matrix_error(gram(sparse),gram(dense)),1e-11)

    def test_gate_cannot_be_applied_after_lossy_sketch(self):
        r = [1/math.sqrt(2),1/math.sqrt(2)]
        a,b = [1.,-1.],[0.,0.]
        self.assertEqual(dot(a,r),dot(b,r))
        gate = [1.,0.]
        self.assertNotEqual(dot([x*g for x,g in zip(a,gate)],r),dot(b,r))

    def test_dynamic_quantization_invalidates_linear_increment(self):
        # In rotated coordinates; original coordinates can be obtained via H^T.
        x,d = [1.,.003,0.,0.],[0.,.002,0.,0.]
        f = lambda row: quantize_row_surrogate(row)[1]
        actual = f([a+b for a,b in zip(x,d)])-f(x)
        self.assertAlmostEqual(actual,1/127)
        self.assertAlmostEqual(f(d),.002)
        self.assertGreater(abs(actual-f(d)),.005)

    def test_equal_energy_surface_nonconvex_but_budget_sublevel_convex(self):
        a,b = [math.sqrt(.125),0.],[0.,math.sqrt(.125)]
        mid = [(x+y)/2 for x,y in zip(a,b)]
        self.assertAlmostEqual(dot(a,a),.125)
        self.assertAlmostEqual(dot(b,b),.125)
        self.assertAlmostEqual(dot(mid,mid),.0625)
        self.assertLess(dot(mid,mid),.125)

    def test_guard_feasible_and_cancelled_reference_falls_back(self):
        rng = random.Random(214)
        for _ in range(40):
            z = [[[rng.uniform(-2,2) for _ in range(5)] for _ in range(4)] for _ in range(3)]
            g = gram(z)
            x,status = filter_candidate([rng.uniform(-1,1) for _ in range(4)],g)
            self.assertEqual(status,"filtered")
            self.assertLessEqual(quadratic(x,g),quadratic([.25]*4,g)+1e-10)
            self.assertLessEqual(sum(g[i][i]*x[i]**2 for i in range(4)),
                                 sum(g[i][i]*.25**2 for i in range(4))+1e-10)
            self.assertTrue(all(0<=v<=.5 for v in x))
        self.assertEqual(filter_candidate([.5,0],[[1,-1],[-1,1]]),([.25,.25],"near_null"))

    def test_actual_projection_validator_rejects_overshoot(self):
        # Candidate validation is separate from proxy feasibility.
        def choose(candidate,actual_reference,actual_candidate,tolerance=.01):
            if actual_reference<=0 or not math.isfinite(actual_candidate) or actual_candidate>actual_reference*(1+tolerance):
                return [.25]*len(candidate)
            return candidate
        self.assertEqual(choose([.4,.1],1.,1.02),[.25,.25])
        self.assertEqual(choose([.4,.1],1.,.9),[.4,.1])
        self.assertEqual(choose([.4,.1],0.,0.),[.25,.25])

    def test_real_source_gate_scope_and_quantized_dispatch(self):
        tree = ast.parse(MODEL.read_text())
        classes = {n.name:n for n in tree.body if isinstance(n,ast.ClassDef)}
        block = next(n for n in classes['DiTBlock'].body if isinstance(n,ast.FunctionDef) and n.name=='forward')
        calls = [n for n in ast.walk(block) if isinstance(n,ast.Call)]
        attn = next(n for n in calls if isinstance(n.func,ast.Name) and n.func.id=='attention')
        self.assertEqual([k.arg for k in attn.keywords],['rope_freqs','transformer_options'])
        self.assertNotIn('gate_msa',ast.unparse(attn))
        gate = next(n for n in calls if isinstance(n.func,ast.Name) and n.func.id=='_mod_gate')
        self.assertEqual(ast.unparse(gate.args[1]),'gate_msa')
        self.assertIs(gate.args[2],attn)
        attention = next(n for n in classes['Attention'].body if isinstance(n,ast.FunctionDef) and n.name=='forward')
        ret = next(n for n in attention.body if isinstance(n,ast.Return))
        self.assertEqual(ast.unparse(ret.value.func),'self.out_proj')
        op = (ROOT/'feasibility_sources/kitchen_tensor_int8.py').read_text()
        self.assertIn('TensorWiseINT8Layout.get_plain_tensors(weight)',op)
        self.assertIn('torch.ops.comfy_kitchen.int8_linear(',op)
        backend = (ROOT/'feasibility_sources/kitchen_backends_cuda___init__.py').read_text()
        self.assertIn('quantize_int8_rowwise_convrot64(',backend)


if __name__ == '__main__':
    started=time.monotonic()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Proofs)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={
        'scope':'local CPU stdlib algebra and cached source-interface inspection',
        'tests_run':result.testsRun,'passed':result.wasSuccessful(),
        'failures':len(result.failures),'errors':len(result.errors),
        'elapsed_seconds':time.monotonic()-started,
        'test_file_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'model_source_sha256':hashlib.sha256(MODEL.read_bytes()).hexdigest(),
        'cost_table':cost_table(),
        'counterexample':{'pre_energy_base':.125,'pre_energy_candidate':.125,
            'eps':.001,'post_base':(.25*.001)**2,'post_candidate':.125,
            'post_energy_ratio':2000000},
        'not_run':['CUDA kernels','actual model projection','full video','runtime integration'],
    }
    (ROOT/'CPU_EVIDENCE_20261023.json').write_text(json.dumps(report,indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
