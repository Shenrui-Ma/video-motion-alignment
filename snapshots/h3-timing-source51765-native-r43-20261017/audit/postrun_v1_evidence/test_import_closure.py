import os,subprocess,sys,unittest
from pathlib import Path
class ImportClosureTests(unittest.TestCase):
 def test_standalone_final_evaluator_dependencies(self):
  folder=Path(__file__).resolve().parent
  code="import sys;sys.path.insert(0,"+repr(str(folder))+");import contract,consume,one_phase,remote_consume,evaluate,scan_current_pose,pairwise_gain,physical_tolerance,timing_metrics,presentation;assert callable(scan_current_pose.observe);assert callable(physical_tolerance.align)"
  result=subprocess.run([sys.executable,'-c',code],env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONPATH=''),capture_output=True,text=True,timeout=20)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
if __name__=='__main__':unittest.main()
