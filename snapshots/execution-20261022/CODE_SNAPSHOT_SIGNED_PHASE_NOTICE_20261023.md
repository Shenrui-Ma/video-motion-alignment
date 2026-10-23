# Signed-phase source snapshot

This is a sanitized source backup, not a deployment bundle. It preserves mathematical counterexamples, finite historical replay, passive observation of complete native/weak trajectories, numerical Q/K definition checks, and downstream calibration tools.

The corresponding snapshot JSON records both original and exported SHA256 for every source. Operational paths and host aliases are placeholders. Credentials, SSH configuration, runtime ownership/status, deployed job manifests, tensors, checkpoints and media are excluded. Operational READY files are not copied because their inventories include excluded deployment assets; the source inventory is the snapshot manifest instead.

The small `replay/sources` and `replay_live_pair/sources` files are frozen upstream H3/ComfyUI/kitchen excerpts used as CPU test oracles. Their JSON source records retain source-file SHA and AST definitions. They are reference fixtures, not newly authored algorithms. The project-authored observer, reconstruction, math and analysis code surrounds these fixtures. The two text kernel files in replay_diagnostics are likewise numeric-definition fixtures.

The exported tests were run on CPU with CUDA disabled: 113 passed, none skipped. Temporary graph-builder inputs were generated only for tests and were removed with the temporary directory; no job was submitted. One export-only portability change replaces exact equality to integer 5 in a floating-point static-mean test with a 14-decimal comparison. Original execution sources, equations and frozen test files remain untouched.

Historical same-state replay failed its historical-output gate despite exact hook-on/off agreement. Its failed gate must stay failed. The later live-pair path instead binds its observations to its own complete newly generated videos, with separate event annotations and full trajectory checks. Neither CPU tests nor source backup establish semantic phase calibration.
