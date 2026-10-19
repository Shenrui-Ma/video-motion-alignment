# Independent review of the offline latent-change observer

Reviewed 2026-10-16, before any use as an online controller. This review does not modify the frozen pose endpoint, observer implementation, or its reported results.

The current four-window calculation has no obvious normalization, positional-time, or generated-output ROI leakage error. The reference is the stored native VAE video latent, not a reconstruction inferred from generated x0. The stored x0 video is after `process_latent_out`; the recorder's video-normalization check establishes that this operation leaves video values unchanged. Both inputs have shape `[1,24,42,46,82]`. The `[1,4,4,4,4]` positional span pattern, bin centers, and adjacent-center difference midpoints are applied consistently. These positional spans remain an approximation to temporal localization, not an assertion about exact VAE receptive fields.

The ROI is computed solely from the supplied source video's shoulder, elbow and wrist tracks, using the complete source clip and a fixed 10% margin. It is not chosen from generated outcomes. Having access to the full reference clip is consistent with the editing task. The selected event windows are still human supplied; this does not establish automatic localization of failing events.

`np.interp` uses constant endpoint extension, but the existing windows 50–65, 69–81, 80–92 and 99–111 with ±24-frame searches stay inside the actual difference-midpoint grid. Thus endpoint extrapolation is not an active explanation for these four results. Any new early/late window should explicitly check this boundary.

The principal missing reliability condition is abstention. `scan` excludes only norm products at or below `1e-10`, then returns an optimum even for a nearly flat curve, a noisy nonzero signal, a single valid frame, or separated similar minima. It reports a runner-up margin and boundary flag without using either to reject a lag. Consequently a returned integer lag is an estimate, not a reliable detected phase error. Six synthetic sanity checks establish algebraic toy behavior only; they do not establish accuracy on edited video or early x0.

The signal is channel-RMS magnitude of temporal latent change, not optical flow and not a signed direction of human movement. Identity, camera, illumination, occlusion and recurring motion energy can produce matching or spurious spatial patterns. Shared 17-frame VAE chunk structure is an additional candidate confound that the present toy checks do not exclude; this review has not demonstrated that it causes the observed result. The incorrect or ambiguous later-window estimates must remain in the record.

## Smallest independent validation

Freeze this exact observer and apply it without tuning to the already saved source07 reference latent and the source07 native/mass final sampler latents. Use source07's source-only ROI with the same joint set, threshold and margin, the same ±24-frame search, and its previously registered three windows 54–69, 75–88 and 98–111. Report every cell, full curves, margin, valid support and boundary status. Compare only with the already available frozen pose results; pose-unknown cells remain unvalidated rather than being called successes. This needs neither new inference, GPU allocation, video decoding nor new pose extraction. Agreement on these related but unused examples is a limited transfer check, not broad sensor validation or evidence of a functioning closed loop.

Reviewed source: `analysis/latent_observer/probe_motion_energy.py`, protocol, sanity and result files. The reference blob and x0 recorder normalization provenance were checked separately in `analysis/pose/encoded_reference_locator.json` and the existing recorder code/audits.

## Later encoder-control evidence

The parent subsequently ran same-VAE representation controls, archived in `analysis/vae_temporal_controls/run1/RESULTS.json`. The identical-RGB-every-frame control has a temporally nonconstant latent and an exact5-bin repetition. Thus an adjacent-latent difference is demonstrably nonzero without actual image motion; the earlier chunk-structure concern is now supported by a controlled example rather than merely hypothesized. This is a representation confound, not evidence of a bug in the frozen pose/time measurements.

The parent's delayed-RGB controls also did not reliably recover4/8-frame shifts with the signed latent observer (reported four-window estimates1/1/0/0 and−17/8/−17/17). The source07 trend agreement therefore does not justify deploying the current latent-change observer as a calibrated online trigger. These results limit this particular readout; they do not establish that all DiT feature or latent-based timing observers are impossible. No thresholds or main endpoints were changed after this evidence.
