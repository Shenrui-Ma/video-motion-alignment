"""Adapt only test fixture paths for Linux; leave sealed sources and tests unchanged."""
from pathlib import Path
import os,sys,tempfile,unittest,types,json,hashlib
ROOT=Path(__file__).resolve().parents[2]
TEMP=ROOT.parent/(ROOT.name+'_cpu_tests_tmp');TEMP.mkdir(exist_ok=True)
tempfile.tempdir=str(TEMP)
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions')]
suite=unittest.TestSuite();adaptations=[]
for path in sorted((ROOT/'tests').glob('test_*.py')):
 source=path.read_text();before=source
 source=source.replace('/Users/researcher/DevProjects/h3-timing-auto-source28289-r45-20261017','/data5/researcher/h3_runs/timing_auto_source28289_r45_20261017')
 source=source.replace("ROOT.parent/'h3-timing-auto-source28289-r45-20261017/configs/parent_captures.json'", "Path('/data5/researcher/h3_runs/timing_auto_source28289_r45_20261017/configs/parent_captures.json')")
 source=source.replace("'r50-' in ROOT.name", "'r50' in ROOT.name")
 module=types.ModuleType(path.stem);module.__file__=str(path);sys.modules[path.stem]=module
 exec(compile(source,str(path),'exec'),module.__dict__)
 suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
 if source!=before:adaptations.append({'test':path.name,'source_sha256':hashlib.sha256(before.encode()).hexdigest(),'only_test_fixture_paths':True})
result=unittest.TextTestRunner(verbosity=2).run(suite)
(ROOT/'audit/recovery/PORTABLE_CPU_RESULT.json').write_text(json.dumps({'tests':result.testsRun,'passed':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),'fixture_adaptations':adaptations,'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES')},indent=2)+'\n')
sys.exit(not result.wasSuccessful())
