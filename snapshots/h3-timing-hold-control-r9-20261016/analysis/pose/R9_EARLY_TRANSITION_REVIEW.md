# R9 early endpoint check: delayed native endpoint confirmed, guided alignment unverified

The independent pose result does **not** establish a full “aligned, then rebounded” sequence. The native endpoint at zero-based index8 is independently measured at +14 frames on both thresholds and both direction/wrist features. The guided endpoints at indices6 and7 have low joint coverage and remain unknown under the frozen gate. Their internal latent-reader lag of +1 must not substitute for independent pose evidence.

## Admission and prefix reuse

The three actual decode records are complete; tensor file SHA, capture metadata, decode MP4 SHA and actual geometry141×736×1312 at24fps pass. The frozen pose, timing and intermediate-gate tools and source-pose hashes were checked. The CPU evaluator used one shared lock, four CPU threads and no GPU. Each snapshot yielded141 person detections, with zero missing/multiple/ambiguous-person frames; valid *joint* coverage is a separate issue.

Index5 was not decoded again. Its video and audio tensors are bitwise equal to R6 index5. R6's existing decode/MP4/pose hashes close, and the R9 decoded records use the same VAE SHA, dtype, core path, flags, full-latent decode and quantization/encoding recipe. Its independent main-window direction and wrist lags `[14,14]` are inherited with this explicit provenance in `early/inherited_index005_pose_gate.json`. This is reuse, not another sample or an additional independent observation.

## Main window50–65

| Zero-based index | Actual forward | Internal reader | Independent direction(.3/.5) | Independent wrist(.3/.5) | Frozen combined gate |
|---:|---|---:|---|---|---|
| 5 | Native prefix, inherited | +11 | +14 / +14 | +14 / +14 | Phase observable |
| 6 | Guided | +1 | unknown / unknown | unknown / unknown | Unknown |
| 7 | Guided by hold2 | +1 | unknown / unknown | unknown / unknown | Unknown |
| 8 | Native after stopping | +11 | +14 / +14 | +14 / +14 | Phase observable |

The reason for the two guided unknowns is specifically insufficient detection coverage. The unqualified near-zero optima are disclosed below only to explain rejection, and are not accepted lag estimates:

| Index | Feature | Threshold | Unqualified optimum | Coverage at that optimum |
|---:|---|---:|---:|---:|
| 6 | Direction | .3 | 0 | .796875 |
| 6 | Direction | .5 | +1 | .625000 |
| 6 | Wrist | .3 | +1 | .687500 |
| 6 | Wrist | .5 | +1 | .500000 |
| 7 | Direction | .3 | +2 | .796875 |
| 7 | Direction | .5 | +1 | .640625 |
| 7 | Wrist | .3 | +1 | .656250 |
| 7 | Wrist | .5 | +1 | .531250 |

The .8 gate is not relaxed, and the direction-only near-miss does not replace the joint direction/wrist gate. At index8, accepted best-lag direction coverage is1.0/.96875 and wrist coverage1.0/.9375.

## Other preselected windows

All four windows were evaluated without reselection. At index6 all four combined results are unknown. At index7 only99–111 has observable phase: direction `[4,4]`, wrist `[4,3]`. At index8, besides the main window,99–111 is observable: direction `[5,6]`, wrist `[5,5]`;69–81 and80–92 remain unknown. Across the three new snapshots there are3 observable cells and9 unknown cells out of12. None is an accepted near-zero main-window result.

## Fixed frame55 inspection and interpretation

The same preselected video frame55 was viewed in all three decoded snapshots. Guided endpoints6/7 visibly alter the pose and exhibit substantial translucent/ghosted body and limb contours. At7, one hand is visibly near the head. At8 the body is clearer, with arms held low/in front and bent knees. The room layout remains recognizable. The low joint coverage is therefore not missing-person detection, and these early endpoint renders should not be treated as clean final frames.

These observations support a change in predicted endpoint appearance/pose under the actuator and a delayed native endpoint once it stops. They leave the precise intermediate phase unverified. They do not prove persistent sampled-latent correction, a complete quantitative rebound, or a general estimator failure rate. R6 index6/7/8 were never saved and remain unavailable; R9 cannot fill that historical gap. The final R9 result remains unsuccessful under the frozen repair gates.
