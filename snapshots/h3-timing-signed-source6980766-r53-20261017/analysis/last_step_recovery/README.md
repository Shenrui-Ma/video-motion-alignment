# R53 final-observation recovery

The original signed-controller run stopped during the final Native observer admission. Its frozen producer, failure archive, 20 Native endpoints and 19 chosen updates remain unchanged. This directory records a separate recovery.

## Bound inputs

`CONTEXT.json` (SHA `b1f4ba19ffb07b3c17e91a0c40ded4b0cb4df70a7038a7253cdac789a3dd35ab`) records the real Native019 endpoint, the original failed request, all prior19 actual observation paths and decisions, and the exact CPU x14→x19 reconstruction. `intake.py` read the complete failure audit once and reproduced all prior19 decisions with the frozen Controller. The full audit remains in its original remote failure archive.

## Decoder

`decode_recovery.py` imports the original frozen `decode_live_child.py`. It substitutes only recovery request admission and a fresh exact supervisor lifetime. The snapshot normalization, FP16 VAE, fallback guard and RGB writer execute the original functions. Root admitted GPU2 with the exact R50 GPU3 service as a peer, then supplied a PID-bound go record. No DiT model was loaded.

The child completed successfully. Its supervisor then failed importing a release helper absent from the frozen R53 producer. The failed supervisor log and child exit record remain. `finalize_release.py` independently checked the successful child exit, exact process identity absence and strict GPU idle before writing `DECODER_RELEASED.json`. It uses the byte-identical already tested R50 bounded release helper copied into this recovery directory. The observed GPU2 state was 8 MiB, 0% utilization and no compute processes.

## CPU decision

`pose_and_decision.py` requires the exact context SHA, the actual recovery decode hashes and the decoder release record. It runs the frozen CPU DWPose probe and whole-timeline observer under the shared pose lock, then replays the archived prior19 measurements and evaluates the recovered Native019 observation with the frozen signed Controller. CUDA is hidden.

The resulting `runs/native019/DECISION19.json` reports one of:

- `requires_one_Full_model_forward`: the actual final decision is ON. A same-input Full prediction remains necessary.
- `OFF_final_Euler_update_required`: the final decision is OFF. The final Euler update still requires actual GPU arithmetic verification and final video decoding.

The decoded Native endpoint is an observation artifact, not an already completed edited result. Both outcomes retain `original_run_completed: false`, `GPU_arithmetic_unverified: true`, and `final_video_exists: false`.

## Checks

Thirteen CPU tests passed. They cover GPU peer identities and reuse, the two-card cap, occupied-target rejection, frozen decoder imports, context source binding, ordered prior19 coverage, completion provenance, and actual archived prior19 observer inputs. The final synthetic unknown-visibility test only checks the OFF control path; it does not predict the real step019 result.

All new files are contained in `analysis/last_step_recovery`. GPU launches and subsequent final-trajectory recovery remain root-owned.
