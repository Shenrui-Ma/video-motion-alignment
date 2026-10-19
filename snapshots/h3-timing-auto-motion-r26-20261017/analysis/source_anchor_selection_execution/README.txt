Source anchor selection CPU prototype

Status: code preparation and synthetic verification only. Real numerical scoring needs a later root-approved authorization file. No new dependencies, GPU, remote changes, or model execution.

Existing Python:
/Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv-current/bin/python

Working directory:
/Users/researcher/DevProjects/h3-timing-auto-motion-r26-20261017/analysis/source_anchor_selection_execution

Read EXECUTION_ADDENDUM.txt and ../source_anchor_selection_review/INDEPENDENT_REVIEW.txt before interpreting output.

Safe preparation commands (each uses the shared Mac CPU lock):
  <python> run_once.py self-test --report audit/synthetic_attemptNNN.json
  <python> run_once.py check --report audit/metadata_attemptNNN.json
Output reports are exclusive-create; choose a fresh filename. Busy CPU lock returns status 75 without numerical work. There is no retry daemon.

After root reviews the exact FREEZE.json, root can create AUTHORIZATION.json with:
  approved: true
  authorizer: "root"
  execution_freeze_sha256: actual SHA256 of this FREEZE.json
  design_freeze_sha256: actual SHA256 of sibling design/FREEZE.json
  source_ids: ["source05"]
  actions: ["source", "endpoint", "finalize"]
  run_ids: ["r27_s05_bad1311_auto", "r27_s05_normal1313_auto"]
  endpoint_indices: [0,1,2,...,19]
No approved authorization is included in this package.

Numerical commands, ONLY after that separate root approval:
  <python> run_once.py source --source-id source05 --authorization AUTHORIZATION.json
  <python> run_once.py endpoint --source-id source05 --run-id r27_s05_bad1311_auto --index 0 --authorization AUTHORIZATION.json
  Repeat the endpoint command as individually admitted bounded calls for each index 0..19, then the other entire R27 trajectory.
  <python> run_once.py finalize --source-id source05 --run-id r27_s05_bad1311_auto --authorization AUTHORIZATION.json
  <python> run_once.py finalize --source-id source05 --run-id r27_s05_normal1313_auto --authorization AUTHORIZATION.json

Outputs are under results/source05. SOURCE_SELECTION and SOURCE_COMPLETE must exist and pass provenance before any target numerical loading. Source selection includes every 279 candidate, every integer competitor, all view-pair evidence and unknowns. Target endpoint files retain every selected/partial baseline row, 279 full-scan rows and 186 historical rows, with complete original curves. Finalization requires all 20 endpoint files. No endpoint-specific success filtering is permitted.

Source40372 migration is bound as a future target set, but current source flip/pad16 views are absent. Its numerical phase fails closed until a new separately reviewed source binding/version exists. Source07 has no target trajectory in this diagnosis. No manual source05 moments may be copied to either source.

If a phase fails after creating a partial output file, keep that evidence and ask root to create an explicitly reviewed recovery version. Never overwrite a result or change score parameters to get a nonempty selection.

Implementation:
anchor_selection.py — source-only relative margin, non-overlapping 0..3 observer positions, four strict budget baselines.
target_diagnostic.py — frozen target measurements and explicit nominal/support coverage, UNKNOWN and denominator handling.
run_once.py — immutable bindings, root authorization gate, bounded one-phase CPU entry point.
vendor/ — four exact original R27 files, source SHA in VENDOR_BINDING.json.
tests/test_source_anchor.py — synthetic geometry, same-view score saturation, hidden rivals, strict budgets, original R27 equivalence, phase gates.

Claims supported by this package alone: implementation exists; synthetic tests and byte/format checks are recorded. It supplies no empirical source selection, target accuracy, control efficacy, architecture innovation, or cross-source generalization result.
