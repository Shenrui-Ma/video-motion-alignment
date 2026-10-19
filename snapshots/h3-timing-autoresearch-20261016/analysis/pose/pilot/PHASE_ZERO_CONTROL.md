# Phase-coordinate zero-perturbation control

Formal run `s05_full_seed1_phase_zero_x0` succeeded (prompt `df158b8e-3a25-4ee1-bc19-cf11b17e38f7`), with the history-recorded file `s05_full_seed1_phase_zero_x0_00001_.mp4`. The output has 141 frames, 1312×736 pixels and 24fps, agreeing with its config.

Independent CPU decoding compared every final frame with `s05_full_seed1_native_x0_00001_.mp4`: all 141 RGB frames are exactly equal, maximum absolute channel difference is 0, and frame PTS/fps/geometry match. The MP4 container hashes differ, so container-byte equality is not claimed. This verifies the zero perturbation final-output control for this exact run; it is not an independent experimental sample.

At confidence 0.3, the original frozen four windows give both-arm lags +13/+10/+8/+4 frames. At 0.5 the first and final windows remain +13/+4, while low-coverage middle-window abstentions remain recorded. The preregistered ±36 first-window sensitivity also gives +13 at both thresholds; wrist lags +13/+12 and right-arm +13/+12 remain compatible. The larger search remains secondary and does not replace the frozen ±24 endpoint.

The upcoming ±12 manipulations perturb the reference's native relative RoPE coordinates. They do not first align the reference and canvas time-coordinate origins. The model's native coordinate gap is not an observed physical action lag; signed effects on the generated action timing must be measured empirically.

Evidence: `phase_zero_rgb_equality.json`; exact raw video/config/history/conditioning/noise/phase audit and pose outputs are archived under `s05_full_seed1_phase_zero_x0_provenance/archive_manifest.json`. Secondary error curves and rejection flags are separately retained under `../phase_sensitivity/s05_full_seed1_phase_zero_x0/`.
