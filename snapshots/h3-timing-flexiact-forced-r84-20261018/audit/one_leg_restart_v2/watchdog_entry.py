"""Use the reviewed watchdog policy with per-attempt receipt isolation."""
import argparse,importlib.util,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(add_help=False);p.add_argument('--receipt-dir',type=Path,required=True)
a,rest=p.parse_known_args();dest=a.receipt_dir.resolve()
if not dest.is_relative_to(ROOT/'audit'):raise ValueError('receipt directory outside run audit')
spec=importlib.util.spec_from_file_location('reviewed_r84_watchdog_v2',ROOT/'audit/watchdog_recovery_v2/watchdog_v2.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.HERE=dest;sys.argv=[sys.argv[0]]+rest;m.main()
