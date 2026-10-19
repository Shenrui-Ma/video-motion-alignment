v4 pairwise-support candidate, synthetic-only execution.

Main scientific source: profile_v4.py. Shared frozen v3 selection and v1/v2 generation are imported read-only through bindings.py.
CODE_FREEZE.json seal002 binds the scientific runner and11 correctness tests. prior_seal001 retains the pre-review version. The two revisions restore the existing cross-null merge gate in the main assessment and enforce case/code/protocol plus two-file commit identity; no profile/operator change.

run_once.py case --case-id <registered id> --attempt <unique attempt>
run_once.py finalize --attempt <unique attempt>

Every call obtains the existing shared Mac CPU lock nonblocking, limits threads to4 and uses a120-second alarm. Exit75 is BUSY. All55 cases are registered in CASE_MANIFEST.json; original43 arrays/truth match the old manifest. Each original43 phase also reproduces the old v3 scientific RESULT exactly apart from timing. RESULT and EVIDENCE are committed atomically through COMPLETE.

audit_results.py is an additional reporting script, outside the scientific CODE_FREEZE; its own SHA is recorded in its bounded postrun receipt. It does not change scientific case results, and is run only after all55 and finalize. The primary comparison reports physical-frame denominators; old49 common-support checks and new witness checks remain separate.

Current permission scope excludes real63 rescoring, new pose, model/GPU changes and online deployment. All zero/shape/occlusion failures remain reportable. Root decides whether the completed evidence warrants a separate real-data phase.
