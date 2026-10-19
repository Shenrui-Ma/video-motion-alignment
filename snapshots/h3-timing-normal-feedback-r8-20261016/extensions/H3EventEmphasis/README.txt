H3 Event Emphasis: controlled inference-only pilot

Node class: H3EventEmphasis
Inputs: model, positive, factor (integer 1, 2 or 3; default 3), start_frame (39),
end_frame (44, inclusive), run_id (unique), audit_dir (absolute).
Output: cloned MODEL only. The positive conditioning is read for complete
reference metadata, never modified or returned differently.

The node installs patches_replace['dit'][('double_block', i)] on the clone.
For factor 1 the callback calls original_block with the original args object.
For factor 2 or 3 it temporarily installs optimized_attention_override in that
single block's copied transformer_options. The original H3 Attention.forward
still computes QKV, per-head Q/K RMSNorm and RoPE. The callback then receives
the native attention_pytorch function and its post-RoPE raw Q/K/V tensors.
It calls that function once normally, then recomputes only the event target
query rows with factor-1 additional copies of the selected reference-video
K/V rows. Factor 2 appends one copy; factor 3 appends two copies.
The original out_proj remains in the original Attention.forward and is called
exactly once on the merged result. No dense attention masks are constructed.

Reference image and video segments both have the native ref_img label.
This code reconstructs and validates the entire segment table from positive
minimax_refs, including optional audio, before selecting the video. It also
checks reference tensor shapes, target geometry, and first selected RoPE time
coordinates. Exactly one character reference image and one video are allowed.
Other attention overrides / existing DiT block patches are rejected.

For 42x46x82 video latents, each latent time slice contains 943 tokens.
The pixel interval [39,44] overlaps positional latent bins [12,14), which
cover source frames [39,46]. These bins are not exact VAE receptive fields.
The matching reference/target row intervals are segment_start+[11316,13202).
All 50 DiT blocks and all sampling forward calls are patched, with no
intervention in the TokenRefiner and no layer/timestep search.

Audit: <audit_dir>/<run_id>.json (atomic updates, refuses overwrite).
Includes metadata, complete layout, selected intervals, first numerical
samples, native backend, per-block and per-forward completed call counts.
First attention diagnostics include factor-1 appended copies, the resulting
K/V length and tensor-storage estimates for K/V concatenations and the local
output. These estimates exclude original tensors, attention workspace and
allocator overhead; they are not measured peak GPU memory.
The formal plan is recorded separately as formal_planned_sampling_steps=20.
Actual expected_sampling_steps is taken from runtime sample_sigmas length-1,
or remains null if that schedule is unavailable. Main runs plan 20 steps:
expect 1000 completed_calls, 20 completed_forward_calls,
calls_by_block=[20]*50, calls_by_forward=[50]*20, and no failed status.
Factors 2 and 3 expect 1000 native_override_calls; factor 1 expects 0.
Technical 2-step benchmark naturally has 100/2/100 instead. The JSON status
remains 'sampling' after the final block; completion of the sampler/output
must be established by the ComfyUI job history, not inferred from this hook.

Tests (use the existing environment; do not install a new torch):
  python -m unittest discover -s tests -p test_event_emphasis.py -v
  H3_EVENT_TEST_DEVICE=cuda python -m unittest discover -s tests -p test_event_emphasis.py -v
CPU torch numerical tests use float64; the optional CUDA test uses bfloat16.
On a host without torch, stdlib mapping/audit/math/noop tests run, and the
four tensor tests explicitly skip. The GPU command is not run by this node.

Research limits: strengthens all spatial content of selected reference time
slices (including identity/background), not an isolated motion feature.
Later layers can propagate effects outside the locally patched queries.
K/V duplication is exactly an added log(factor) attention-logit bias in real
arithmetic: factor 3 means log(3), not three times the final attention
probability. For prior selected-key mass p, the new mass is
factor*p/(1+(factor-1)*p). Floating-point kernels may differ. It is a diagnostic intervention,
not a proposed novel mechanism or proof of a general short-event remedy.
