"""Causal Euler20 observer/router integration for one fixed-geometry pilot."""
from dataclasses import dataclass
import json
from pathlib import Path
import sys
import time

import torch

from .dependencies import layout, readout, router
from .observer import FrozenGap5Observer, PROTOCOL_SHA, SOURCE_SHA, next_decision

WRAPPER_KEY = "H3FeedbackRouter/causal-gap5-v1"
POLICIES = ("feedback", "off", "fixed")


@dataclass(frozen=True)
class FeedbackConfig:
    policy: str
    fixed_indices: str
    start_frame: int
    end_frame: int
    width: int
    height: int
    length: int
    run_id: str
    audit_dir: str

    def __post_init__(self):
        readout.CaptureConfig(self.run_id, self.audit_dir, self.width, self.height, self.length)
        if self.policy not in POLICIES:
            raise ValueError("unknown feedback policy")
        if (self.width, self.height, self.length, self.start_frame, self.end_frame) != (1024, 576, 141, 50, 65):
            raise ValueError("this pilot is frozen to 1024x576x141 and source window50..65")
        indices = self.indices
        if self.policy != "fixed" and indices:
            raise ValueError("fixed_indices must be empty for feedback/off")

    @property
    def indices(self):
        if not isinstance(self.fixed_indices, str):
            raise ValueError("fixed_indices must be a comma-separated string")
        if not self.fixed_indices.strip():
            return ()
        parts = [part.strip() for part in self.fixed_indices.split(",")]
        if any(not part.isdecimal() for part in parts):
            raise ValueError("fixed_indices must contain integer indices")
        indices = tuple(int(part) for part in parts)
        if len(set(indices)) != len(indices) or tuple(sorted(indices)) != indices or any(not 6 <= i <= 19 for i in indices):
            raise ValueError("fixed_indices must be unique increasing zero-based indices6..19")
        return indices

    @property
    def shapes(self):
        return readout.CaptureConfig(self.run_id, self.audit_dir, self.width, self.height, self.length).shapes


def extract_reference(positive, config):
    metadata = layout.conditioning_metadata(positive)
    refs = [r for r in positive[0][1]["minimax_refs"] if r["kind"] in ("video", "video_audio")]
    if len(refs) != 1 or refs[0]["kind"] != "video":
        raise ValueError("feedback pilot requires exactly one silent reference video")
    original = refs[0]["latent"]
    if tuple(original.shape) != config.shapes[0] or original.dtype != torch.float32:
        raise ValueError("reference must be the unscaled float32 VAE output at frozen geometry")
    reference = original.detach().to(device="cpu", copy=True).contiguous()
    if not bool(torch.isfinite(reference).all()):
        raise ValueError("nonfinite reference")
    return metadata, reference


class FeedbackState(router.RouterState):
    def __init__(self, metadata, reference, config, *, observer=None):
        self.config = config
        self.reference = reference.detach().to(device="cpu", copy=True).contiguous()
        self.reference_signature = readout.tensor_signature(self.reference)
        self.observer = observer if observer is not None else FrozenGap5Observer(self.reference)
        self.callback_count = 0
        self.sampler_entered = False
        self.sampler_finished = False
        self.pending_active = False
        self.pending_for = None
        self.forward_active = False
        self.active_indices = []
        self.latched = []
        self.grid = None
        root = Path(config.audit_dir)
        root.mkdir(parents=True, exist_ok=True)
        # RouterState's JSON replacement is atomic but not an exclusive reservation.
        # A second node/run using the same ID must fail before it can overwrite it.
        with (root / (config.run_id + ".feedback-reservation")).open("x") as handle:
            handle.write("reserved for one sampler invocation\n")
        super().__init__(metadata, "mass_preserve", 1.0, 0, 0,
                         config.start_frame, config.end_frame, 0, 50, 6, 20,
                         config.run_id, config.audit_dir)
        self.audit["feedback"] = {
            "schema": "h3-feedback-controller-v1", "new_method_claim": False,
            "policy": config.policy, "fixed_indices": list(config.indices),
            "reference": self.reference_signature,
            "reference_semantics": "unscaled clean reference from positive minimax_refs; CPU copy",
            "observer_source_sha256": SOURCE_SHA, "observer_protocol_sha256": PROTOCOL_SHA,
            "observer": "full-frame same_phase_gap5 signed cosine;49 integer lags[-24,24]",
            "gap_physical_frames": 17, "event_frames_inclusive": [50, 65],
            "event_latent_bins_half_open": [14, 20],
            "query_nominal_coverage_inclusive": [47, 67],
            "geometry_limit": "coverage centers are positional bins, not neural receptive fields",
            "interpretation_limit": "previously normal1024 source control; inspect independent early/final pose; no unseen generalization claim",
            "normalization": "process_latent_out on CPU copies: video scale1 unchanged/audio divided4",
            "frozen_audio_scale": 4.0, "frozen_video_scale": 1.0,
            "first_observation_callback_index": 5, "decision_callback_indices": list(range(5, 19)),
            "terminal_audit_callback_index": 19, "first_possible_active_forward_index": 6,
            "active_indices": self.active_indices, "latched_forwards": self.latched,
            "observations": [], "callback_count": 0, "observer_seconds_total": 0.0,
        }
        self.write()

    def latch_forward(self):
        index = self.forward_index + 1
        if not self.sampler_entered or self.sampler_finished or not 0 <= index < 20:
            raise ValueError("forward outside the single authorized Euler20 sampling invocation")
        if self.next_block != 0 or self.callback_count != index or self.audit["completed_forward_calls"] != index:
            raise ValueError("each forward must follow the preceding completed forward and callback")
        if index >= 6 and self.pending_for != index:
            raise ValueError("missing/stale decision for this exact next forward")
        if index < 6 or self.config.policy == "off":
            active, reason = False, "PREFIX_NATIVE" if index < 6 else "POLICY_OFF"
        elif self.config.policy == "fixed":
            active, reason = index in self.config.indices, "FIXED_MASK"
        else:
            active, reason = self.pending_active, "PREVIOUS_CALLBACK_DECISION"
        self.forward_active = bool(active)
        if active:
            self.active_indices.append(index)
        self.latched.append({"forward_index": index, "active": bool(active), "reason": reason,
                             "decision_callback_index": index - 1 if index >= 6 else None})

    def selected(self, block):
        if not self.latched or self.latched[-1]["forward_index"] != self.forward_index:
            raise ValueError("missing forward-specific latched state")
        return self.forward_active and 0 <= block < 50


class FeedbackBlockPatch(router.EventBlockPatch):
    def __call__(self, args, extra_args):
        if self.block_index == 0:
            self.state.latch_forward()
        return super().__call__(args, extra_args)


def official_basic_guider_class(actual, expected):
    """Accept the official class loaded under Comfy's absolute-path module alias.

    Comfy's node loader uses the file path without .py as the module name,
    whereas importing comfy_extras.nodes_custom_sampler creates another class.
    Permit only the same source file, direct base and exact class method code.
    A similarly named class, subclass or modified class remains unsupported.
    """
    if actual is expected:
        return True
    if actual.__name__ != "Guider_Basic" or expected.__name__ != "Guider_Basic":
        return False
    actual_module = sys.modules.get(actual.__module__)
    expected_module = sys.modules.get(expected.__module__)
    if actual_module is None or expected_module is None:
        return False
    actual_file = getattr(actual_module, "__file__", None)
    expected_file = getattr(expected_module, "__file__", None)
    if not actual_file or not expected_file:
        return False
    if Path(expected_file).name != "nodes_custom_sampler.py" or Path(actual_file).resolve() != Path(expected_file).resolve():
        return False
    if getattr(actual_module, "Guider_Basic", None) is not actual or actual.__bases__ != expected.__bases__:
        return False
    if set(vars(actual)) != set(vars(expected)) or actual.__qualname__ != expected.__qualname__:
        return False
    method = vars(actual).get("set_conds")
    expected_method = vars(expected).get("set_conds")
    if getattr(method, "__code__", None) is None or method.__code__ != getattr(expected_method, "__code__", None):
        return False
    # The official class only overrides set_conds. Refuse any future additional
    # class implementation until the frozen sampling contract is re-audited.
    return set(vars(actual)) == {"__module__", "set_conds", "__doc__"}


def validate_guider(model_wrap, extra_args, state, *, guider_class=None):
    if guider_class is None:
        from comfy_extras.nodes_custom_sampler import Guider_Basic
        guider_class = Guider_Basic
    actual_class = type(model_wrap)
    state.audit["feedback"]["guider_contract"] = {
        "actual_class": actual_class.__qualname__, "actual_module": actual_class.__module__,
        "canonical_class": guider_class.__qualname__, "canonical_module": guider_class.__module__,
        "same_class_object": actual_class is guider_class, "cfg": getattr(model_wrap, "cfg", None),
        "accepted_official_class": official_basic_guider_class(actual_class, guider_class),
    }
    if not official_basic_guider_class(actual_class, guider_class) or getattr(model_wrap, "cfg", None) != 1.0:
        raise ValueError("only unmodified BasicGuider CFG1 is supported")
    conds = getattr(model_wrap, "original_conds", {})
    if set(conds) != {"positive"} or len(conds["positive"]) != 1:
        raise ValueError("exactly one positive and no negative conditioning required")
    options = conds["positive"][0]
    if any(options.get(k) is not None for k in ("hooks", "control", "mask", "area")):
        raise ValueError("conditional hooks/regions/control are unsupported")
    refs = [r for r in options.get("minimax_refs", ()) if r["kind"] in ("video", "video_audio")]
    if len(refs) != 1 or readout.tensor_signature(refs[0]["latent"]) != state.reference_signature:
        raise ValueError("runtime conditioning reference differs from observer reference")
    for model_options in (getattr(model_wrap, "model_options", {}), extra_args.get("model_options", {})):
        for key in ("sampler_cfg_function", "sampler_pre_cfg_function", "sampler_post_cfg_function",
                    "disable_cfg1_optimization", "multigpu_thread_pool"):
            if model_options.get(key):
                raise ValueError("CFG hooks/multigpu are unsupported: " + key)
        transformer = model_options.get("transformer_options", {})
        wrappers = transformer.get("wrappers", {})
        if any(v for key, v in wrappers.items() if key != "sampler_sample"):
            raise ValueError("additional per-forward wrappers are unsupported")
        patches = transformer.get("patches_replace", {}).get("dit", {})
        if len(patches) != 50 or any(not isinstance(patches.get(("double_block", i)), FeedbackBlockPatch)
                                   or patches[("double_block", i)].state is not state for i in range(50)):
            raise ValueError("cloned model does not share the same50 feedback block states")


class FeedbackRecorder:
    def __init__(self, state, *, unpack=None, nested_factory=None, guider_class=None):
        self.state = state
        self.unpack = unpack
        self.nested_factory = nested_factory
        self.guider_class = guider_class

    def __call__(self, executor, model_wrap, sigmas, extra_args, callback, noise,
                 latent_image=None, denoise_mask=None, disable_pbar=False):
        state = self.state
        if state.sampler_entered:
            raise ValueError("feedback state is single-use; create a new node/run_id for every sampling run")
        state.sampler_entered = True
        try:
            validate_guider(model_wrap, extra_args, state, guider_class=self.guider_class)
            if denoise_mask is not None:
                raise ValueError("denoise masks are outside this pilot")
            model = model_wrap.inner_model
            shapes = tuple(tuple(s) for s in model.latent_shapes)
            if shapes != state.config.shapes:
                raise ValueError("model target latent geometry differs from frozen pilot")
            sampler = executor.class_obj
            if getattr(sampler.sampler_function, "__name__", None) != "sample_euler" or getattr(sampler, "extra_options", {}).get("s_churn", 0) != 0:
                raise ValueError("requires audited Euler with no churn")
            if getattr(sampler, "inpaint_options", {}).get("random", False):
                raise ValueError("random inpaint noise is outside this paired pilot")
            grid = sigmas.detach().to(device="cpu", dtype=torch.float64, copy=True)
            if grid.ndim != 1 or len(grid) != 21 or not bool(torch.isfinite(grid).all()) or grid[-1].item() != 0 or not bool((grid[:-1] > grid[1:]).all()):
                raise ValueError("requires exactly20 strictly decreasing Euler steps ending at zero")
            if float(model.audio_scale()) != 4.0 or float(model.latent_format.scale_factor) != 1.0:
                raise ValueError("requires audited H3 audio scale4 and video scale1")
            state.grid = grid
            if self.unpack is None:
                from comfy.utils import unpack_latents
                from comfy.nested_tensor import NestedTensor
                unpack, nested = unpack_latents, NestedTensor
            else:
                unpack, nested = self.unpack, self.nested_factory
            state.audit["feedback"].update(sigmas_video=grid.tolist(), sampler="sample_euler",
                                            audio_scale=float(model.audio_scale()),
                                            video_latent_scale_factor=float(model.latent_format.scale_factor),
                                            seed=extra_args.get("seed"), noise=readout.tensor_signature(noise))
            state.write()

            def record(index, x0, x, total_steps):
                if type(index) is not int or total_steps != 20 or index != state.callback_count or not 0 <= index < 20:
                    raise ValueError("duplicate/skipped/out-of-order/non20 callback")
                if state.forward_index != index or state.next_block != 0 or state.audit["completed_forward_calls"] != index + 1:
                    raise ValueError("callback must follow exactly one complete50-block forward")
                if state.audit["calls_by_forward"][index] != 50:
                    raise ValueError("callback observed incomplete DiT forward")
                expected_routes = 50 if state.forward_active else 0
                if state.audit["routed_by_forward"][index] != expected_routes:
                    raise ValueError("route state changed during a forward")
                state.callback_count += 1
                feedback = state.audit["feedback"]
                feedback["callback_count"] = state.callback_count
                if index >= 5:
                    started = time.perf_counter()
                    leaves = readout.split_streams(x0, shapes, unpack)
                    raw = [leaf.detach().to(device="cpu", copy=True).contiguous() for leaf in leaves]
                    raw_signatures = [readout.tensor_signature(leaf) for leaf in raw]
                    if not all(bool(torch.isfinite(leaf).all()) for leaf in raw):
                        raise ValueError("nonfinite current endpoint")
                    copied = time.perf_counter()
                    # Separate input copies also catch a future in-place process_latent_out.
                    with torch.no_grad():
                        ready = list(model.process_latent_out(nested([v.clone() for v in raw])).unbind())
                    if len(ready) != 2 or any(tuple(v.shape) != shape or v.device.type != "cpu" or v.dtype != torch.float32 for v, shape in zip(ready, shapes)):
                        raise ValueError("process_latent_out changed geometry/device/dtype")
                    if not torch.equal(ready[0], raw[0]) or not torch.equal(ready[1], raw[1] * 0.25):
                        raise ValueError("unexpected normalization; video must be identity and audio divided4")
                    normalized = time.perf_counter()
                    observation = state.observer(ready[0])
                    observed = time.perf_counter()
                    proposed, reason = next_decision(observation, state.pending_active)
                    terminal = index == 19
                    if not terminal:
                        state.pending_for = index + 1
                        if state.config.policy == "feedback":
                            state.pending_active = proposed
                        elif state.config.policy == "fixed":
                            state.pending_active = index + 1 in state.config.indices
                        else:
                            state.pending_active = False
                    seconds = time.perf_counter() - started
                    feedback["observer_seconds_total"] += seconds
                    row = {"callback_index": index, "completed_forward_calls": index + 1,
                           "current_forward_active": state.forward_active,
                           "terminal_audit_only": terminal,
                           "next_forward_index": None if terminal else index + 1,
                           "next_active": None if terminal else state.pending_active,
                           "observer_proposed_active": proposed, "reason": reason,
                           "applied_reason": ("TERMINAL_AUDIT_ONLY" if terminal else reason
                                              if state.config.policy == "feedback" else
                                              "FIXED_MASK" if state.config.policy == "fixed" else "POLICY_OFF"),
                           "policy": state.config.policy, "readout_seconds": seconds,
                           "copy_hash_finite_seconds": copied - started,
                           "normalization_seconds": normalized - copied,
                           "observer_compute_seconds": observed - normalized,
                           "time_scope": "synchronous CPU copy, validation, normalization, observer and decision; JSON write excluded",
                           "sigma_video": float(grid[index]), "sigma_next_video": float(grid[index + 1]),
                           "x0_raw_video": raw_signatures[0], "x0_raw_audio": raw_signatures[1],
                           "observation": observation}
                    # The terminal proposal is diagnostic and can never activate forward20.
                    feedback["observations"].append(row)
                state.write()
                if callback is not None:
                    return callback(index, x0, x, total_steps)

            result = executor(model_wrap, sigmas, extra_args, record, noise,
                              latent_image, denoise_mask, disable_pbar)
            if state.callback_count != 20 or state.audit["completed_forward_calls"] != 20 or state.next_block != 0:
                raise ValueError("incomplete Euler20 sampling")
            if readout.tensor_signature(state.reference) != state.reference_signature:
                raise ValueError("observer reference mutated")
            state.audit["feedback"]["active_forward_count"] = len(state.active_indices)
            state.audit["feedback"]["active_sigma_intervals"] = [
                {"forward_index": i, "sigma": float(grid[i]), "sigma_next": float(grid[i + 1]),
                 "delta_sigma": float(grid[i] - grid[i + 1]), "routed_blocks": 50}
                for i in state.active_indices]
            state.audit["feedback"]["sigma_dose"] = sum(float(grid[i] - grid[i + 1]) for i in state.active_indices)
            state.audit["status"] = "complete"
            return result
        except BaseException as error:
            state.audit["status"], state.audit["error"] = "failed", f"{type(error).__name__}: {error}"
            raise
        finally:
            state.sampler_finished = True
            state.audit["feedback"]["finished_unix"] = time.time()
            state.write()
