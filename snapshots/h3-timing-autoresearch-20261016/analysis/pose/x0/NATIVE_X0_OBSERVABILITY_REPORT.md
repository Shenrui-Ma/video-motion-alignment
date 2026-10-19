# Native x0: the target-window delay is observable before the last sampled step

For the single deterministic Sam05 replay, the predeclared pose gate detects the target-window delay in snapshot step010, with nine model calls still remaining. This meets an **observability prerequisite** for feedback. It does not demonstrate that those remaining steps can correct the error, that the detector locates actions automatically, or that this is a new architecture.

All five complete offline decodes passed manifest status, MP4 SHA256 and141×736×1312×3 geometry checks before CPU measurement. The same frozen metric code, confidence thresholds0.3/0.5, ±24frame search and existing four source windows were used. Full videos were decoded; temporal latent crops were not substituted. All outputs, per-person detections, confidence values, curves and abstentions are retained.

## Target source window50–65

| Snapshot (zero-based model index) | Model call | Video sigma | Both-arm lag at0.3 /0.5 | Wrist-position lag at0.3 /0.5 | Frozen gate |
|---|---:|---:|---|---|---|
| step005 | 6 | 0.972973 | unknown / unknown | unknown / unknown | Unknown |
| step010 | 11 | 0.923077 | +13 /+13 | +13 /+12 | Phase available for manual review |
| step015 | 16 | 0.800000 | +13 /+13 | +13 /+12 | Phase available for manual review |
| step019 | 20 | 0.387097 | +13 /+13 | +13 /+12 | Endpoint sanity only |
| sampler_final | 20 | 0 | +13 /+13 | +13 /+12 | Final trajectory check |

Positive lag means the edited pose occurs later;13frames at24fps is0.542seconds. Step010 is the earliest **sampled** checkpoint passing the primary gate. Steps006–009 were not measured, and this does not establish the moment at which the deviation first appeared.

The passive-capture final MP4 is exactly RGB-identical to the no-capture native final in141/141frames. The separately encoded offline sampler_final has small pose/confidence changes, but reproduces the main first-window+13 and last-window+4 phases. Float/tensor endpoint comparisons belong to the decoder audit; encoded MP4 equality across encoders is not required.

## Why step005 is unknown even though its image is clear

The unknown status is an observer limitation. Frame55 is a clear person/room image with the wrong current phase, not an unreadable noisy image. The primary both-arm estimate fails same-frame confidence coverage, primarily because of the right arm.

| step005, window50–65 feature | Confidence0.3 | Confidence0.5 |
|---|---|---|
| Both-arm direction | Coverage65.6%; rejected | Coverage45.3%; rejected |
| Right-arm direction | Coverage31.3%; rejected | Coverage6.25%; rejected |
| Left-arm direction | Coverage100%; reliable+13 | Coverage84.4%; reliable+12 |
| Normalized body coordinates | Coverage90.6%; reliable+13 | Coverage82.8%; reliable+13 |

The right-arm unqualified minimum is near+12frames, but it is not an accepted estimate. It must not be relabeled reliable because it agrees with later output. At frame50, edited right-elbow/right-wrist raw detector scores are0.146/0.227; at frame55, the right-wrist score is0.356. These scores are detector outputs, not calibrated probabilities. Overlay inspection shows a visible but locally difficult arm/hand configuration. It does not establish that occlusion alone is the cause.

Thus, early left-arm and body information already supports a phase discrepancy. The primary two-arm gate abstains because the target local evidence is insufficient, not because every feature is uninformative. No threshold or feature selection was changed to convert this early checkpoint into a primary success. There is no evidence here of a rejected multiple-matching-phase minimum or opposing signed left/right accepted lags.

## Other predeclared windows

- Window69–81 remains unknown at every sampled checkpoint because the stricter threshold rejects the phase estimate.
- Window80–92 often gives about+8 in direction features, but the wrist-position comparison is unavailable at0.5; the conservative confound check remains unknown.
- Window99–111 passes from step005 onward: both-arm+4 at both thresholds; position is generally+4 (step015+3). This is a separate window and cannot replace the primary target window.

No person is completely missed or ambiguously selected in these five snapshot extractions. Missing local joints still matter despite successful whole-person detection.

## What remains unproved

The snapshots are predictions on one generation trajectory, not independent samples. Their early appearance can evolve during sampling. A known source window was supplied manually, so this is not automatic discovery of missing actions or localization of an arbitrary temporal error. The method uses an existing trained pose model without additional training or a generative teacher. No amplitude/action-omission classifier exists.

The immediate next causal test is whether an intervention starting after the observation can improve the same final window without harming edit identity, other phases or already-correct cases. Fixed full-trajectory interventions and posthoc retiming remain necessary competing explanations/baselines. A passing observer does not justify claiming closed-loop control efficacy.

CPU extraction took approximately63–68seconds per complete141frame checkpoint. These offline measurements are not an optimized online-controller overhead benchmark; full VAE decoding cost is additional and separately logged. No GPU was used by the pose analysis.

## Artifacts

`s05_full_seed1_native_x0/batch_results.json` summarizes all checkpoints. Each checkpoint retains its `.pose.json`, `.observability.json`, `.decode_manifest.json`, extraction/evaluation logs and fixed overlay frames55/63/86/105. `INTERMEDIATE_PROTOCOL.txt` records the corrected pre-decode window list; the parent project records the original transcription correction. `evaluate_x0.py` applies the reporting gate while preserving the frozen metric implementation.
