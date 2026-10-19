# Static native versus mass-routing trajectories

The all-steps mass-routing run has near-zero target-window phase already in its earliest sampled x0 snapshot, step005. Native has a delayed target pose: its primary two-arm gate abstains at step005, then consistently reports+13frames from step010 onward. This compares two static inference trajectories, not an online correction after detection.

For source frames50–65, using the unchanged dual-threshold observer:

| Checkpoint | Native direction lag0.3 /0.5 | Native primary gate | All-steps mass direction lag0.3 /0.5 | Mass gate |
|---|---|---|---|---|
| step005 | unknown / unknown | Unknown | 0 /0 | Near zero; no intervention |
| step010 | +13 /+13 | Phase available | 0 /0 | Near zero; no intervention |
| step015 | +13 /+13 | Phase available | 0 /0 | Near zero; no intervention |
| step019 | +13 /+13 | Endpoint sanity | 0 /0 | Near zero; no intervention |
| sampler_final | +13 /+13 | Final check | 0 /0 | Near zero; no intervention |

The shoulder-relative wrist phase is also0 at both thresholds in every mass snapshot. Primary arm-direction coverage is100% at threshold0.3 and96.9–98.4% at0.5. Each mass snapshot has zero missing-person, multiple-person or ambiguous-selection frames. The step005/frame55 overlay was checked: the raised-arm and bent-leg pose is visible, skeleton alignment is reasonable, and the gray top/dark trousers remain. Thus, the primary near-zero result is not produced by rejecting most target joints or by an obviously empty/damaged frame.

Mass window80–92 is likewise near zero at every sampled checkpoint;99–111 is−1frame, inside the declared deadzone. Window69–81 remains unknown under the stricter coverage gate, even though some threshold0.3 estimates are0/−1. No rejected window was dropped or retuned.

Native step005 is visually clear. Its two-arm unknown is mainly a right-arm confidence-coverage limitation; the left arm and normalized body already give about+12/+13frames. See `NATIVE_X0_OBSERVABILITY_REPORT.md` for the separate-arm results. The comparison must not be described as native motion becoming visible only at step010.

These observations leave an important causal question open: can intervention starting after the step010 observation still change the target phase? All-steps mass may have established the correct motion before step005. The preregistered `mass_late11` run tests this separately, retaining native steps0–10 and intervening only on11–19. It is a chosen fixed late schedule, not a live feedback controller. Its early snapshots must first match native exactly before interpreting final differences.

Hard masking and signed phase controls are also pending. These two trajectories do not isolate the value of attention-mass preservation, establish automatic action localization, or demonstrate a novel closed-loop system.

All ten snapshot analyses and decode manifests are saved in the two run directories. `native_mass_observer_comparison.json` combines their unchanged observer summaries. Parent decoder audits retain pre-encode hashes and endpoint tensor checks; offline encoder differences are not treated as a failed model-equivalence control.
