# Source07 native: known timing failure with important abstentions

Formal run `s07_full_seed1_native_x0` succeeded with prompt `97b7f386-0d1a-4994-9b2a-c43c107240c0`; geometry is 1312×736, 141 frames, 24 fps. MP4 SHA256 is `a4b0f8bdefa545638904ae027e50e9a00c494fce6586a1077851da944f56a32c`. Exact history, input/noise/router audits, raw video and all pose data are archived with the isolated transfer-root provenance.

| Original source07 window | Both arms, confidence0.3 | Both arms, confidence0.5 | Right arm, both thresholds |
|---|---|---|---|
| 54–69 | Reliable +15 | Rejected coverage | Reliable +15 |
| 75–88 | Rejected shape/multiple phases | Rejected shape | Rejected shape; additional multiple-phase flag at0.5 |
| 98–111 | Reliable −5 | Rejected coverage | Reliable −5 |

Positive lag means the edited event occurs later. The first-window right-arm best-shift residual is0.08259 at both thresholds with93.75% same-frame support. Combined-arm coverage is87.5% at0.3 but78.125% at0.5; the frozen80% gate therefore refuses the latter. We retain right-arm sensitivity as predeclared and do not silently replace the failed combined-arm primary endpoint.

The middle-window combined-arm best residual is0.75896/0.73717 and right-arm0.83257/0.84805, above the frozen0.5 threshold. It cannot be summarized as a single reliable delay. Final-window right-arm residual0.04149 supports a −5-frame local lead, while combined-arm high-threshold coverage is only76.8%. This is a nonuniform sequence, not simply a globally slower playback rate.

Fixed55/86 overlays retain the bedroom layout and coarse gray-shirt/dark-trouser edited person. Some fast/bright hand regions remain difficult for the estimator. These snapshots are not a full identity, finger, texture or flicker assessment. The paired mass output is pending; no new intervention success is inferred from native alone.

A full decoded comparison to the archived `07_sam_s1_baseline_00001_.mp4` verifies identical length/FPS/geometry/PTS but **not bitwise RGB equality**:0/141 frames exactly equal, max channel difference48. Do not call this an exact replay. It is still a rerun of a known case and chosen seed, not an independent new random sample merely because decoded pixels differ. Input/backend/encoding attribution remains a separate root audit. The equality record is `source07_native_vs_archived_rgb.json`.

Root actual-input audit subsequently verified all checked conditioning/noise inputs equal (prompt, source video, actual native VAE calls, Qwen presentation/tokenization/embedding, token tags, latent shapes, packed layout, noise streams/signature). I read the saved audit at `analysis/replication/source07_actual_input_reuse_audit.json`. Known graph differences include the historical factor1 EventEmphasis wrapper versus current native TemporalRouter interface and passive x0 callback. Their numerical/encoding contributions have not been causally isolated. This strengthens matched-input provenance while leaving the observed RGB inequality and non-independent-seed classification unchanged.
