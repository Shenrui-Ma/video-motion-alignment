import unittest
import numpy as np
from test_physical_tolerance import sample
from pairwise_gain import compare

class Tests(unittest.TestCase):
    def test_identical(self):
        self.assertEqual(compare(sample(),sample(),[40,71],0,'arm_direction')['min_gain'],0)
    def test_tolerated(self):
        self.assertLessEqual(compare(sample(),sample(2),[40,71],2,'arm_direction')['min_gain'],0)
    def test_large_shift(self):
        self.assertGreater(compare(sample(),sample(10),[40,71],10,'arm_direction')['min_gain'],.5)
    def test_static(self):
        self.assertEqual(compare(sample(constant=True),sample(constant=True),[40,71],10,'arm_direction')['min_gain'],0)
    def test_missing(self):
        s,t=sample(),sample(10);t['arm_direction'][40:72]=np.nan
        self.assertEqual(compare(s,t,[40,71],10,'arm_direction')['status'],'unknown')
    def test_separate_support(self):
        s,t=sample(),sample(10);t['arm_direction'][40]=np.nan
        result=compare(s,t,[40,71],10,'arm_direction')
        self.assertEqual(result['status'],'measured')
        self.assertGreater(result['min_gain'],.5)
    def test_physical_time(self):
        self.assertGreater(compare(sample(),sample(10,30),[40,71],10,'arm_direction')['min_gain'],.5)

if __name__=='__main__':unittest.main()
