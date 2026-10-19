# Original-resolution native replay: strong local delay reproduced

Formal run `s05_full_seed1_native`, prompt UUID `d976ff77-1f65-452e-98d4-aed4d9900c29`, completed successfully. The exact SaveVideo output from history is `s05_full_seed1_native_00001_.mp4`; decoded geometry is1312×736,141frames,24fps, matching its job config. The original MP4 is copied to local `outputs/`. History, config, conditioning, noise and router audit are preserved under `analysis/pose/pilot/fullnative_provenance/`.

The frozen CPU pose observer measured the following positive lags, meaning edited motion occurs later:

| Source window | Both-arm lag at0.3 | Right-arm lag at0.3 | Both-arm same-frame error | Best locally shifted error |
|---|---:|---:|---:|---:|
| 50–65 | +13frames /0.542s | +13 | 1.125878 | 0.184423 |
| 69–81 | +10frames /0.417s | +10 | 1.273705 | 0.429514 |
| 80–92 | +8frames /0.333s | +8 | 1.136994 | 0.133602 |
| 99–111 | +4frames /0.167s | +4 | 0.411914 | 0.118754 |

At confidence0.5, both-arm first-window lag remains+13 (right-arm+12), right-arm window80–92 remains+8, and last-window both/right-arm remains+4. The69–81 window and both-arm80–92 window reject due to insufficient coverage. Rejected estimates are not replaced by hand-picked values.

Right-wrist geometric crossings at0.3 occur at63/77/85/108, compared with source49/66/76/106. These are operational wrist-above-shoulder events, not manually annotated semantic action boundaries. Changing local lag over time supports nonuniform phase drift, rather than a universal constant playback delay. It does not establish that every short action is lost.

All141frames have a selected person, with no multiple-person or selection-ambiguity frames. Frame55 overlay was visually inspected: visible elbows/wrists and legs agree with detected bones; the right arm is still bent around chest height where the source's earlier calibration shows the raised-arm event. This supports the local pose finding but does not substitute for full motion-quality assessment.

## Replay versus independent replication

The new MP4 SHA256 is `e5d74ae7b7650e717b4c65955a98c3bd349da49f8ee15c92cee8097f692ca6d8`; the archived baseline MP4 hash differs. Nevertheless, every saved person coordinate/score and selected-person value is exactly equal to the old Sam05 baseline extraction, and timing numbers are exactly equal. Treat this as a deterministic replay of the known failure, **not** an independent seed or expanded sample. Container metadata can change a file hash without changing decoded pixels; the leader is separately auditing decoded-video equality, conditioning and noise provenance.

This restores a valid failure case for controlled intervention, while the1024native/mass pair remains a correct-case safety control. Neither this one replay nor the low-resolution comparison proves a general causal effect of resolution.

Original VAE roundtrip control previously measured zero reliable lag on these windows. This excludes that tested roundtrip's fixed decoding offset as an explanation for the13frame first-event delay, but does not prove preservation of all VAE motion details.
