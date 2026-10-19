# Frozen phase observer: synthetic calibration

The frozen observer correctly recovers signed shifts in the clean primary window and abstains on unidentifiable or unreliable signals. This is a limited coordinate-level calibration. It does **not** validate pose detection on noisy intermediate H3 reconstructions or implement an amplitude/missing-action classifier.

Protocol was written before running. `timing_metrics.py` was unchanged, with SHA256 `eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e`. The executable refuses a different observer hash. Twenty-five deterministic synthetic cases produce 800 diagnostics across four windows, four features, and two confidence thresholds. Every case, curve, rejection, and coordinate array is retained.

## Primary window: source05 frames50–65

Primary feature is `arm_direction`. Each count below includes confidence thresholds0.3 and0.5; these are correlated stress tests, not independent statistical samples.

| Synthetic family | Diagnoses | Accepted | Result |
|---|---:|---:|---|
| Exact temporal shifts0, ±2, ±7, ±13 | 14 | 14 | All signed lags exactly recovered |
| Right-arm occlusion, all-low confidence, 10%/35% masking; shift0/+7 | 16 | 0 | All abstained, including input-guard failures for all-low confidence |
| Repeating period20; shift0/+7 | 4 | 0 | Multiple equivalent matching phases rejected |
| Flat pose; shift0/+7 | 4 | 0 | Undefined phase rejected |
| Motion-excursion scaling0.5/1.5; shift0/±7 | 12 | 12 | All signed lags exactly recovered |

The random10% confidence mask also caused primary-window rejection. This observer is conservative; this is a loss of availability, not proof of accurate detection under missing observations.

## All four predeclared windows

| Feature | Clean shifts: accepted/exact out of56 | Amplitude confound: accepted/exact out of48 | False phase alarms from amplitude alone |
|---|---:|---:|---:|
| Both-arm direction | 52/52 | 44/38 | 0 |
| Right-arm direction | 46/46 | 40/40 | 0 |
| Torso-normalized body coordinates | 56/56 | 48/48 | 0 |
| Shoulder-relative wrist coordinates | 52/52 | 41/29 | 1 |

All128 repeated/flat diagnoses across four features rejected a unique phase. None of the accepted clean-shift or masked-confidence estimates had a wrong signed lag. Accepted confidence-mask estimates exactly recovered their known shift, but acceptance was sparse (both-arm7/64, right-arm5/64, body19/64, wrist0/64).

The amplitude confound matters. For source05 frames80–92, scaling arm-coordinate excursion by1.5 without any temporal shift produced an accepted wrist-coordinate lag of−3frames at confidence0.3. At0.5 the accepted estimate was−2frames. The both-arm-direction feature reported+1frame for both thresholds. With the same amplitude change plus true−7/+7frame shifts, wrist-coordinate estimates became−10/+4frames at0.3. These failures are retained; the observer was not retuned. The preregistered false-alarm criterion is accepted |lag|>2 when true lag is zero. A two-frame error is still an error even when it is below that reporting threshold.

Thus, wrist-distance mismatch alone is insufficient evidence for phase drift. Direction and position can disagree when motion amplitude or pose geometry changes. These results do not justify automatically selecting whichever feature supports the desired conclusion.

## What the synthetic definitions mean

For signed delay d, edited[t]=source[clip(t−d,0,140)]; positive d means later edited motion. Confidence moves with the copied coordinates. The repeated sequence tiles original frames40–59 and the flat sequence repeats frame55. This intentionally retains multiple exactly matching phases or no temporal information.

Amplitude is a coordinate excursion perturbation: for elbow/wrist relative to its shoulder, replace r(t) by mean(r)+alpha·(r(t)−mean(r)). It can change bone geometry and is not a physically valid rendered human. Other joints remain unchanged, so the excellent body-coordinate result partly benefits from unchanged lower-body information. It must not be interpreted as general amplitude robustness.

Synthetic shifted signals share the same original detector errors, so clean recovery is easier than independently estimating an edited character. This verifies sign conventions, confidence handling, ambiguity rejection, and selected confounds. Earlier actual-video source/VAE/Sam calibration remains separate evidence. No generated video was created for this test, and no GPU was used.

## Implications for passive x0 monitoring

- Early low-confidence pose estimates must be `unknown`, not `action missing` and not evidence to activate guidance.
- A late checkpoint with confident but feature-disagreeing estimates still needs inspection; a single accepted scalar lag is inadequate.
- No amplitude or occlusion type classifier exists in this implementation. The amplitude tests merely reveal potential false phase attribution.
- Synthetic validity alone cannot authorize an active control policy. Actual checkpoint reconstruction, detector confidence, pose fidelity, and final-video agreement remain to be tested with the observer frozen.

Files: `results/all_results.json` contains full curves; `results/primary_results.json` and `results/summary.csv` provide compact results; `results/synthetic_coordinates.npz` preserves all transformed arrays. `PREREGISTERED_SYNTHETICS.md` fixes the definitions and criteria; `scripts/calibrate_phase_observer.py` reproduces them using the existing CPU environment.
