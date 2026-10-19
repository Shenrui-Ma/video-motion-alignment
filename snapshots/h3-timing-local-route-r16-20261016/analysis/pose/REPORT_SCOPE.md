# R16 independent evaluation scope (frozen before outcome)

This round tests source-derived forearm ROI versus an equal per-time-bin alpha-sum uniform query gain on the known source05/Sam/seed2026101311 development failure. The shared reference route is the existing Full same-time reference route. Both new arms use zero-based prediction indices 6–14, all 50 layers, 20 Euler updates, and no extra model predictions.

The primary evaluation remains the original windows 50–65, 69–81, 80–92, 99–111 and confidence thresholds 0.3/0.5. Reliable direction and wrist phase are reported separately; unknown is retained. Strict primary near-alignment requires all four known estimates within ±2 frames, not merely the older wrapper’s permissive near-zero label. No new threshold or peak selection will be fitted to these outcomes.

Common-support comparisons will use the intersection of native, Full, ROI and uniform valid features. The report will separately show source-ROI time-bin region 47–67, preceding frames 0–46, following frames 68–140, and tail 112–140. These supplementary bins measure effects outside the target; they cannot establish semantic action deletion. Frozen lower-body auxiliary results use pairwise support and must not be misrepresented as a four-arm common-support comparison.

Fixed-frame inspection uses frames 55, 86, 105; the frozen video segment is [42,82). This can detect gross room/person or motion artifacts, not certify face likeness, fine fingers, or full-sequence quality. All failure outputs remain part of the result.

Equal sums of alpha are not equal attention-mass-weighted correction doses. ROI is derived from source pose and is not an automatic detector of generated errors. Subsequent layers and updates can propagate a local modification elsewhere. Better ROI performance would support a useful distribution choice in this case, not prove an optimal mask or novelty. If uniform performs similarly, spatial specificity has not been demonstrated. Retaining native leg motion is not automatically desirable because native legs also have a time error.

Runtime completion requires exact successful history, actual conditions/noise and prefix005 equality, 20×50 completed blocks with exactly 450 routed blocks, eight distinct registered x0 snapshots plus final, finite bound tensors, and exact original bundle hashes except the parent-recorded administrative R17 admission change. The frozen Router intentionally retains status=sampling at the final block; independent completion gates must be used. Only new v2 evaluation files may correct schema assumptions; sealed originals remain untouched.

This round records NFE, callback/update counts, wall time and CPU analysis cost. It does not diagnose inference efficiency or add speed trials.
