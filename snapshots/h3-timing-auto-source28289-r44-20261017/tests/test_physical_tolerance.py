import unittest
import numpy as np
from physical_tolerance import rescore

def sample(delay=0, fps=24, constant=False):
    t=np.arange(round(6*fps))/fps
    phase=4*(t-delay/24)+.8*np.sin(2*(t-delay/24))
    if constant:phase[:]=0
    vec=np.stack([np.cos(phase),np.sin(phase)],axis=-1)[:,None,:]
    return {'frames':np.arange(len(t)), 'times':t, 'raw':{'video':{'fps':fps}},
            'arm_direction':np.repeat(vec,4,axis=1), 'arm_conf':np.ones((len(t),4))}

class Tests(unittest.TestCase):
    def test_identity(self):
        r=rescore(sample(),sample(),[40,71],0,'arm_direction')
        self.assertEqual(r['status'],'below_source_tolerance')
        self.assertAlmostEqual(r['proposal_cost'],0)
    def test_tolerated_delay(self):
        r=rescore(sample(),sample(2),[40,71],2,'arm_direction')
        self.assertEqual(r['status'],'below_source_tolerance')
    def test_larger_delay(self):
        r=rescore(sample(),sample(10),[40,71],10,'arm_direction')
        self.assertEqual(r['status'],'above_source_tolerance')
    def test_static(self):
        r=rescore(sample(constant=True),sample(constant=True),[40,71],10,'arm_direction')
        self.assertEqual(r['status'],'unknown_static_source')
    def test_missing_target(self):
        s,t=sample(),sample(10);t['arm_direction'][40:72,:]=np.nan
        r=rescore(s,t,[40,71],10,'arm_direction')
        self.assertEqual(r['status'],'unknown_common_support')
    def test_common_weights(self):
        s,t=sample(),sample(10);t['arm_conf'][50:82,:]=.4
        r=rescore(s,t,[40,71],10,'arm_direction')
        self.assertAlmostEqual(r['common_weight_sum'],32*4*.4)
        self.assertEqual(r['status'],'above_source_tolerance')
    def test_distinct_fps(self):
        r=rescore(sample(),sample(10,30),[40,71],10,'arm_direction')
        self.assertEqual(r['status'],'above_source_tolerance')

if __name__=='__main__':unittest.main()
