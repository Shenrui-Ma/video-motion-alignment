import math
import unittest
from direction_gate import GateConfig, direction_gate, equal_energy_uniform_alpha


class DirectionGateTests(unittest.TestCase):
    def run_gate(self, d=(1., 0.), p=(1., 0., 0.), **kw):
        return direction_gate(d, kw.pop('previous', (0., 0.)), kw.pop('next_', (2., 0.)), p, 1,
                              previous_bin=0, next_bin=2, **kw)

    def test_forward_and_backward_internal_routing(self):
        a = self.run_gate(); b = self.run_gate(d=(-1., 0.), p=(0., 0., 1.))
        self.assertEqual((a.status, b.status), ('ACTIVE', 'ACTIVE'))
        self.assertAlmostEqual(a.gate, 1.)
        self.assertEqual(a.correction, (.45, 0.))
        self.assertEqual(b.correction, (-.45, 0.))

    def test_orthogonal_and_conflicting_directions(self):
        self.assertEqual(self.run_gate(d=(0., 1.)).gate, 0.)
        self.assertEqual(self.run_gate(d=(-1., 0.)).status, 'SKIP')

    def test_unknown_skips_feedback(self):
        for r in (self.run_gate(p=(1., 1., 1.)), self.run_gate(p=(0., 1., 0.)),
                  self.run_gate(next_=(0., 0.)), self.run_gate(d=(math.nan, 0.))):
            self.assertEqual(r.status, 'UNKNOWN')
            self.assertEqual(r.correction, (0., 0.))

    def test_soft_gate_is_squared_cosine(self):
        r = self.run_gate(d=(1., 1.))
        self.assertAlmostEqual(r.gate, .5)
        self.assertAlmostEqual(r.correction[0], .225)

    def test_preserves_convex_reference_combination(self):
        # m=.3, S=(3,1), R=(1,1), other contribution=(.2,.4)
        m=.3; same=(3., 1.); ref=(1., 1.); other=(.2, .4)
        d=tuple(m*(s-r) for s,r in zip(same,ref)); r=self.run_gate(d=d)
        original=tuple(o+m*x for o,x in zip(other,ref))
        result=tuple(o+c for o,c in zip(original,r.correction))
        expected=tuple(o+m*((1-r.alpha_effective)*v+r.alpha_effective*s)
                       for o,v,s in zip(other,ref,same))
        for a,b in zip(result,expected):self.assertAlmostEqual(a,b)

    def test_one_sided_boundary(self):
        r=direction_gate((-1.,), (0.,), (1.,), (0.,1.),0,previous_bin=0,next_bin=1)
        self.assertEqual(r.status,'ACTIVE')

    def test_equal_energy_control(self):
        a=equal_energy_uniform_alpha([(2.,0.),(0.,2.)],[(1.,0.),(0.,0.)])
        self.assertAlmostEqual(a,math.sqrt(1/8))
        self.assertAlmostEqual(a*a*8,1.)

    def test_invalid_shapes(self):
        with self.assertRaises(ValueError):self.run_gate(d=(1.,))
        with self.assertRaises(ValueError):equal_energy_uniform_alpha([(1.,)],[])

if __name__ == '__main__':unittest.main()
