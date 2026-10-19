Completed independent CPU diagnostic. Start with REPORT.txt and VERIFICATION.json.

All writes are contained in this directory. Original data, online policy and benchmark results are read-only.
Existing interpreter: /Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv-current/bin/python

Completed commands used Python -B:
  pilot.py prepare
  pilot.py tests --attempt tests001
  pilot.py synthetic --attempt synthetic001
  pilot.py real --case CASE --attempt real_CASE_001
  verify_and_summarize.py

No installations. Runtime environment OMP_NUM_THREADS, OPENBLAS_NUM_THREADS, MKL_NUM_THREADS, VECLIB_MAXIMUM_THREADS, NUMEXPR_NUM_THREADS were1.
Each compute phase takes an exclusive nonblocking flock on the existing global CPU lock. BUSY exits75 and does not create an attempt. Existing attempts and summary exports are never overwritten.

Do not rerun prepare on completed artifacts. New execution requires a fresh attempt name and unchanged FREEZE/input SHA. For any algorithm change, preserve this completed version and create a separate explicitly versioned experiment. Current candidate is diagnostic only, not recommended for online intervention.
