import itertools
import unittest
import numpy as np
import profile as p
import synthetic as s


class Correctness(unittest.TestCase):
    def test_old_inputs_exact_replay(self):
        value=s.features()
        for bone in range(4):
            t=np.arange(141,dtype=float)
            angle=.013*t+.00019*t*t+.17*np.sin(.083*t+.4*bone)
            expected=np.stack((np.cos(angle),np.sin(angle)),axis=-1)
            np.testing.assert_array_equal(value['directions'][:,bone],expected)
        old=[r for r in s.cases() if r['group']=='old8']
        self.assertEqual(len(old),8)
        for row in old:
            rotation=row['sign']*row['amplitude']*np.where((np.arange(141)//row['block'])%2,-1,1)
            _,target=s.build(row)
            for bone in range(4):
                t=np.arange(141,dtype=float)
                angle=.013*t+.00019*t*t+.17*np.sin(.083*t+.4*bone)+rotation
                np.testing.assert_array_equal(target['directions'][:,bone],np.stack((np.cos(angle),np.sin(angle)),axis=-1))

    def test_interval_and_edge_sums(self):
        a=np.array([2,3,5,7])
        self.assertEqual(p.interval_sums(a)[1,3],15)
        self.assertEqual(p.edge_sums(a)[1,3],12)
        self.assertEqual(p.edge_sums(a)[1,1],0)

    def test_profile_closed_form_and_rotation(self):
        a=s.features('identifiable');b=s.features('identifiable',6,s.ROTATION)
        g=p.grid(a,b,'left_arm',.5)
        x,y,mask,w=p.contexts(a,b,'left_arm',.5)
        aa,bb,index=30,90,30
        c=(x[aa:bb+1]*y[index,aa:bb+1].conj()*w[aa:bb+1]).sum(axis=0)
        r=c/np.abs(c)
        direct=(w[aa:bb+1]*np.abs(x[aa:bb+1]-r*y[index,aa:bb+1])**2).sum()/w[aa:bb+1].sum()
        self.assertAlmostEqual(g['loss'][index,aa,bb],direct,places=12)
        np.testing.assert_allclose(np.angle(r),-s.ROTATION[:2],atol=1e-12)
        original=p.grid(a,s.features('identifiable',6),'left_arm',.5)
        valid=np.isfinite(g['loss'])&np.isfinite(original['loss'])
        np.testing.assert_allclose(g['loss'][valid],original['loss'][valid],atol=2e-12,rtol=0)

    def test_nonfinite_confidence_and_coordinates(self):
        a=s.features('identifiable');b=s.features('identifiable')
        b['confidence'][70,0]=np.inf;b['confidence'][80,1]=np.nan
        b['directions'][60,0]=np.nan
        _,_,mask,w=p.contexts(a,b,'left_arm',.5)
        self.assertFalse(mask[70,0]);self.assertFalse(mask[80,1]);self.assertFalse(mask[60,0])
        self.assertEqual(w[70,0],0)
        self.assertFalse(mask[:24].any());self.assertFalse(mask[-24:].any())
        b['confidence'][70,0]=.2
        self.assertFalse(p.contexts(a,b,'left_arm',.3)[2][70,0])

    def test_malformed_data_exits(self):
        a=s.features()
        with self.assertRaises(ValueError):p.validate(a|{'directions':a['directions'][:3]})
        a['times'][5]=np.nan
        with self.assertRaises(ValueError):p.validate(a)

    def test_uniform_conditional_information_zero(self):
        g=p.grid(s.features('uniform'),s.features('uniform',6,s.ROTATION),'right_arm',.5)
        self.assertLess(g['source_J'][24,116],1e-14)
        self.assertLess(g['target_J'][30,24,116],1e-14)

    def test_DP_against_exhaustive(self):
        rows=[{'start':a,'end':b,'value':v,'lag':d,'part':'left_arm'} for a,b,v,d in
              [(0,7,2,6),(4,11,3,5),(8,15,4,6),(0,15,6,6),(16,23,1,6)]]
        possibilities=[]
        for flags in itertools.product((0,1),repeat=len(rows)):
            chosen=sorted([r for r,f in zip(rows,flags) if f],key=p.key)
            if all(x['end']<y['start'] for x,y in zip(chosen,chosen[1:])):
                possibilities.append((sum(r['value'] for r in chosen),chosen))
        winner=sorted(possibilities,key=lambda x:(-x[0],len(x[1]),tuple(map(p.key,x[1]))))[0]
        actual=p.solve(rows,24)
        self.assertEqual(actual['selected'],winner[1])
        self.assertEqual(p.solve([],24)['K'],0)


if __name__=='__main__':unittest.main()
