import unittest
from run_native import qualify

class Qualification(unittest.TestCase):
    def test_unknown_remains_unknown(self):
        self.assertEqual(qualify([None, 0])['status'], 'unknown')
        self.assertIsNone(qualify([None, 0])['lag_ms_at_confidence_03_05'][0])
    def test_three_frame_physical_tolerance(self):
        self.assertEqual(qualify([1, 4])['status'], 'qualified_exploratory')
        self.assertEqual(qualify([1, 5])['status'], 'unknown')
    def test_signed_lag_is_not_absolute(self):
        self.assertEqual(qualify([-3, -3])['lag_ms_at_confidence_03_05'], [-125.0, -125.0])

if __name__ == '__main__':
    unittest.main()
