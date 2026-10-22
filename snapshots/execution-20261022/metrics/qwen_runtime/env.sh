#!/usr/bin/env bash
QWEN_RUNTIME_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export TMPDIR="$QWEN_RUNTIME_ROOT/tmp"
export XDG_CACHE_HOME="$QWEN_RUNTIME_ROOT/cache"
export HF_HOME="$QWEN_RUNTIME_ROOT/cache/huggingface"
export TORCH_HOME="$QWEN_RUNTIME_ROOT/cache/torch"
export TRITON_CACHE_DIR="$QWEN_RUNTIME_ROOT/cache/triton"
export PIP_CACHE_DIR="$QWEN_RUNTIME_ROOT/cache/pip"
export PYTHONNOUSERSITE=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
export PATH="$QWEN_RUNTIME_ROOT/bin:$QWEN_RUNTIME_ROOT/venv/bin:$PATH"
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
export NO_PROXY='*' no_proxy='*'
