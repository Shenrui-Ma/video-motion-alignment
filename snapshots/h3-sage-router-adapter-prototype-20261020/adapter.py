"""Isolated engineering adapter for the H3 attention(q, k, v) -> (O, ln LSE) seam."""

from importlib import import_module


class SageAttentionLSE:
    """HND router tensors in/out; the audited Sage public API receives NHD.

    The default path requires CUDA and never falls back to another backend.
    An explicitly injected backend may run on CPU for contract tests. Its
    contract is the same as sageattn_qk_int8_pv_fp16_cuda, including natural LSE.
    This class does not patch a model, node, forward method, or production file.
    """

    def __init__(self, backend=None, *, smooth_k=True):
        if backend is not None and not callable(backend):
            raise TypeError("backend must be callable")
        if type(smooth_k) is not bool:
            raise TypeError("smooth_k must be boolean")
        self.backend = backend
        self.smooth_k = smooth_k

    def __call__(self, q, k, v):
        import torch

        if any(not isinstance(x, torch.Tensor) or x.ndim != 4 for x in (q, k, v)):
            raise ValueError("expected [B,H,N,D] tensors")
        batch, heads, queries, dim = q.shape
        if min(q.shape) < 1 or min(k.shape) < 1:
            raise ValueError("empty attention dimensions are unsupported")
        if (k.shape != v.shape or k.shape[:2] != (batch, heads)
                or k.shape[-1] != dim):
            raise ValueError("Q/K/V batch, heads, head dimension, or K/V length mismatch")
        if dim > 128:
            raise ValueError("audited Sage backend supports head dimensions <= 128")
        if q.dtype not in (torch.float16, torch.bfloat16):
            raise ValueError("expected fp16 or bf16 Q/K/V")
        if any(x.dtype != q.dtype or x.device != q.device for x in (k, v)):
            raise ValueError("Q/K/V dtype or device mismatch")
        backend = self.backend
        if backend is None:
            if q.device.type != "cuda":
                raise ValueError("real Sage backend requires CUDA; no fallback is provided")
            backend = import_module("sageattention.core").sageattn_qk_int8_pv_fp16_cuda
        # The cached public wrapper reads heads with size(2); NHD avoids its
        # incorrect interpretation of HND sequence length as head count.
        q_nhd, k_nhd, v_nhd = (x.transpose(1, 2).contiguous() for x in (q, k, v))
        result = backend(
            q_nhd, k_nhd, v_nhd,
            tensor_layout="NHD",
            is_causal=False,
            qk_quant_gran="per_warp",
            sm_scale=dim ** -0.5,
            pv_accum_dtype="fp32",
            smooth_k=self.smooth_k,
            smooth_v=False,
            return_lse=True,
        )
        if not isinstance(result, tuple) or len(result) != 2:
            raise ValueError("backend must return (output, natural_log_lse)")
        out, lse = result
        if not isinstance(out, torch.Tensor) or out.shape != (batch, queries, heads, dim):
            raise ValueError("backend output must have NHD query shape")
        if not isinstance(lse, torch.Tensor) or lse.shape != (batch, heads, queries):
            raise ValueError("backend LSE must have [B,H,Q] shape")
        if out.dtype != q.dtype or out.device != q.device:
            raise ValueError("backend output dtype/device mismatch")
        if lse.dtype != torch.float32 or lse.device != q.device:
            raise ValueError("backend LSE must be fp32 on the query device")
        # Public return_lse=True already converts log2 -> ln and restores the
        # smooth_k mean shift. Do not apply either correction a second time.
        return out.transpose(1, 2).contiguous(), lse
