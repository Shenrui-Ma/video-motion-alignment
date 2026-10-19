"""CPU toy harness; existing attention and block patch code execute unchanged."""
import contextlib
import math
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "extensions"))
from H3FeedbackRouter.core import FeedbackConfig, FeedbackState, FeedbackBlockPatch, FeedbackRecorder
from H3FeedbackRouter.dependencies import router


class Nested:
    is_nested = True
    def __init__(self, values):
        self.values = values
    def unbind(self):
        return self.values


def unpack(value, shapes):
    cursor, leaves = 0, []
    for shape in shapes:
        count = math.prod(shape)
        leaves.append(value.reshape(-1)[cursor:cursor + count].reshape(shape))
        cursor += count
    return leaves


class FakeModel:
    def __init__(self, shapes):
        self.latent_shapes = list(shapes)
        self.latent_format = SimpleNamespace(scale_factor=1.0)
    def audio_scale(self):
        return 4.0
    def process_latent_out(self, value):
        video, audio = value.unbind()
        return Nested([video, audio * 0.25])


class FakeGuider:
    cfg = 1.0


def config(root, run_id="case", policy="feedback", fixed=""):
    return FeedbackConfig(policy, fixed, 50, 65, 1312, 736, 141, run_id, str(root))


def observation(lag):
    return {"accepted": lag is not None, "best": None if lag is None else {"lag_frames": lag},
            "rejection_reasons": [] if lag is not None else ["ambiguous_separated_lag"],
            "curve": [{"lag_frames": i, "signed_cosine_error": None} for i in range(-24, 25)]}


class Observations:
    def __init__(self, lags):
        self.lags = list(lags)
        self.count = 0
    def __call__(self, video):
        value = self.lags[min(self.count, len(self.lags) - 1)]
        self.count += 1
        return observation(value)


def make_state(root, lags=(0,), policy="feedback", fixed="", run_id="case"):
    c = config(root, run_id, policy, fixed)
    reference = torch.zeros(c.shapes[0], dtype=torch.float32)
    state = FeedbackState({"refs": []}, reference, c, observer=Observations(lags))
    plan = {"seq_len": 84, "frame_rows": 1, "latent_interval_half_open": [14, 20],
            "query_interval_half_open": [56, 62], "reference_video_segment": [0, 42]}
    state.plan_for = lambda _: plan  # Only packed geometry is toy; block/counter/kernel code is real.
    return state


def dense_attention(q, k, v):
    logits = q @ k.transpose(-1, -2) / math.sqrt(q.shape[-1])
    return logits.softmax(-1) @ v, logits.logsumexp(-1)


@contextlib.contextmanager
def cpu_attention():
    original = router.route_attention
    def route(*args, **kwargs):
        return original(*args, **kwargs, attention=dense_attention)
    with patch.object(router, "route_attention", route):
        yield


def run_blocks(state, patches, *, sigmas=None):
    q = torch.arange(168, dtype=torch.float32).reshape(1, 1, 84, 2) / 100
    k = q.flip(-2).contiguous()
    v = torch.sin(q * 3)
    layout = object()
    value = None
    def attention_pytorch(*args, **kwargs):
        raise AssertionError("the override must intercept native dispatch")
    def original(args):
        nonlocal value
        override = args["transformer_options"]["optimized_attention_override"]
        value = override(attention_pytorch, q, k, v, 1, skip_reshape=True)
        return {"img": value}
    for i in range(50):
        options = {"block_index": i, "minimax_h3_layout": layout}
        if sigmas is not None:
            options["sample_sigmas"] = sigmas
        patches[("double_block", i)]({"layout": layout, "transformer_options": options},
                                      {"original_block": original})
    return value


def make_guider(state):
    guider = FakeGuider()
    guider.inner_model = FakeModel(state.config.shapes)
    guider.original_conds = {"positive": [{"minimax_refs": [{"kind": "video", "latent": state.reference.clone()}]}]}
    guider.model_options = {"transformer_options": {"patches_replace": {"dit": {
        ("double_block", i): FeedbackBlockPatch(state, i) for i in range(50)}}}}
    return guider


def execute_toy(state, *, nested_callback=False, callback=None, double_forward=False,
                steps=20, options=None, guider=None):
    guider = make_guider(state) if guider is None else guider
    shapes = state.config.shapes
    count = sum(math.prod(s) for s in shapes)
    noise = torch.arange(count, dtype=torch.float32).reshape(1, 1, -1) / count
    sigmas = torch.linspace(1, 0, 21)
    patches = guider.model_options["transformer_options"]["patches_replace"]["dit"]
    class Executor:
        class_obj = SimpleNamespace(sampler_function=SimpleNamespace(__name__="sample_euler"), extra_options={})
        def __call__(self, model_wrap, grid, extra_args, cb, noise, latent_image, mask, disable):
            x = noise.clone()
            for i in range(steps):
                value = run_blocks(state, patches, sigmas=grid)
                if double_forward:
                    run_blocks(state, patches, sigmas=grid)
                x0 = x * 0.25 + value.mean() * 0.001
                xo, xx = (Nested(unpack(x0, shapes)), Nested(unpack(x, shapes))) if nested_callback else (x0, x)
                before = x0.clone(), x.clone()
                cb(i, xo, xx, 20)
                assert torch.equal(x0, before[0]) and torch.equal(x, before[1])
                x = x0
            return x
    recorder = FeedbackRecorder(state, unpack=unpack, nested_factory=Nested, guider_class=FakeGuider)
    rng = torch.random.get_rng_state().clone()
    noise_before, sigmas_before = noise.clone(), sigmas.clone()
    with cpu_attention():
        result = recorder(Executor(), guider, sigmas,
                          {"seed": 123, "model_options": options or guider.model_options},
                          callback, noise, torch.zeros_like(noise), None, True)
    assert torch.equal(noise, noise_before) and torch.equal(sigmas, sigmas_before)
    assert torch.equal(rng, torch.random.get_rng_state())
    return result
