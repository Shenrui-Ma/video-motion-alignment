# Passive x0 recorder control

Formal native replay with capture (`s05_full_seed1_native_x0`) completed successfully under prompt `5de5b00a-ecae-43f4-a402-eb060bfe20da`. Exact-history output is `s05_full_seed1_native_x0_00001_.mp4`.

Compared with the no-capture `s05_full_seed1_native_00001_.mp4`, all **141/141 decoded RGB frames are byte-identical**, with maximum channel difference0. Frame geometry1312×736,24fps and decoder presentation timestamps also match. Both clips completely decode to the container-declared141frames. Thus, for this precise replay, the passive recorder did not alter the encoded visual result. This does not establish equivalence for other seeds or configurations.

The MP4 container hashes differ (`7a65463d6cd54517851a1aa3bf3a3670d6bf07a28f0ca46e7b267e03799ec30b` with capture versus `e5d74ae7b7650e717b4c65955a98c3bd349da49f8ee15c92cee8097f692ca6d8` without), illustrating why file hashes alone are insufficient for passive-output comparison.

Frozen pose measurements exactly reproduce the no-capture results: both-arm lags at confidence0.3 are+13,+10,+8,+4frames across the existing four windows. The0.5 threshold retains the same reliable/rejected windows and signed estimates. This is a control replay, not an independent experimental sample.

Evidence: `native_x0_passive_rgb_equality.json` preserves all per-frame RGB hashes, maximum/mean differences and presentation timestamps. `s05_full_seed1_native_x0_provenance/archive_manifest.json` lists copied raw video, exact history, config, conditioning, noise, router audit and pose files with SHA256 hashes. Offline x0 checkpoint encodes have a different encoding path and require their own endpoint checks; their encoded-pixel equality is not implied here.
