"""Observe registered INT8 dispatch without selecting a backend or copying data.

Install after int8_row_chunking.install and before Comfy Core main. Counters are
process-wide attempted calls; a backend export can delegate to another export,
so counters are evidence of execution, not disjoint model-layer totals.
"""

import atexit
from copy import deepcopy
from functools import wraps
import importlib
import json
import os
from pathlib import Path
import sys
from threading import RLock
import time


BACKENDS = ("cuda", "triton", "eager")
OPERATIONS = ("int8_linear", "w4a8_int8_linear")
_active_auditor = None


def _tensor_metadata(value):
    if all(hasattr(value, field) for field in ("shape", "dtype", "device")):
        return {"shape": [int(size) for size in value.shape],
                "dtype": str(value.dtype), "device": str(value.device)}
    return None


def _call_metadata(args, kwargs):
    # No repr(), tensor values, .cpu(), synchronization, or nested traversal.
    metadata = {}
    for name, value in [(f"args[{i}]", value) for i, value in enumerate(args)] + list(kwargs.items()):
        item = _tensor_metadata(value)
        if item is not None:
            metadata[name] = item
    return metadata


class DispatchAudit:
    def __init__(self, log_path, flush_every):
        self.path = Path(log_path).resolve()
        self.flush_every = flush_every
        self.lock = RLock()
        self.hooks = []
        self.data = {
            "schema": "h3-backend-dispatch-audit-v1", "pid": os.getpid(),
            "started_unix_ns": time.time_ns(), "flush_every": flush_every,
            "count_semantics": "Attempted calls to backend exports, including nested backend delegation.",
            "count_freshness": "Periodic snapshots may lag; flush() or normal process exit captures current counts.",
            "backends": {}, "operations": {}, "logging_errors": [],
        }

    def flush(self):
        """Best-effort logging must never replace an operator result/exception."""
        with self.lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_name(self.path.name + f".{os.getpid()}.tmp")
                temporary.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
                os.replace(temporary, self.path)
            except Exception as error:
                if not self.data["logging_errors"]:
                    self.data["logging_errors"].append({"type": type(error).__name__, "message": str(error)})
                    print(f"H3 backend audit logging failed: {type(error).__name__}", file=sys.stderr)

    def _begin(self, key, args, kwargs):
        with self.lock:
            entry = self.data["operations"][key]
            entry["attempted_calls"] += 1
            first = entry["attempted_calls"] == 1
            if first:
                entry["first_call"] = {"unix_ns": time.time_ns(), "tensor_arguments": _call_metadata(args, kwargs)}
            return first, entry["attempted_calls"] % self.flush_every == 0

    def _end(self, key, first, periodic, error=None):
        with self.lock:
            entry = self.data["operations"][key]
            entry["successful_calls" if error is None else "failed_calls"] += 1
            if first:
                entry["first_call"]["outcome"] = "returned" if error is None else "raised"
                if error is not None:
                    entry["first_call"]["exception_type"] = type(error).__name__
            if first or periodic:
                self.flush()

    def wrap(self, original, backend, operation):
        key = backend + "." + operation

        @wraps(original)
        def observed(*args, **kwargs):
            first, periodic = False, False
            try:
                first, periodic = self._begin(key, args, kwargs)
            except Exception:
                # Even malformed metadata must leave original validation intact.
                pass
            try:
                result = original(*args, **kwargs)
            except BaseException as error:
                try:
                    self._end(key, first, periodic, error)
                except Exception:
                    pass
                raise
            try:
                self._end(key, first, periodic)
            except Exception:
                pass
            return result

        observed._h3_backend_dispatch_audit = self
        return observed

    def summary(self):
        with self.lock:
            return deepcopy(self.data)


def install(*, log_path, flush_every=1000):
    """Wrap only registered CUDA/Triton/eager exports; return JSON-safe status."""
    global _active_auditor
    if type(flush_every) is not int or flush_every < 1:
        raise ValueError("flush_every must be a positive integer")
    if _active_auditor is not None:
        if _active_auditor.path != Path(log_path).resolve() or _active_auditor.flush_every != flush_every:
            raise RuntimeError("dispatch audit already installed with a different configuration")
        registry = importlib.import_module("comfy_kitchen.registry").registry
        for module, operation, original, wrapped, backend in _active_auditor.hooks:
            if getattr(module, operation) is not wrapped or registry.get_implementation(operation, backend=backend) is not wrapped:
                raise RuntimeError("a backend export changed after dispatch audit installation")
        return _active_auditor.summary()

    audit = DispatchAudit(log_path, flush_every)
    registry = importlib.import_module("comfy_kitchen.registry").registry
    try:
        for backend in BACKENDS:
            try:
                module = importlib.import_module("comfy_kitchen.backends." + backend)
            except Exception as error:
                audit.data["backends"][backend] = {"status": "unavailable", "reason": type(error).__name__ + ": " + str(error)}
                continue
            audit.data["backends"][backend] = {"status": "imported"}
            for operation in OPERATIONS:
                key = backend + "." + operation
                original = getattr(module, operation, None)
                entry = {"status": "unavailable", "attempted_calls": 0, "successful_calls": 0, "failed_calls": 0}
                audit.data["operations"][key] = entry
                if not callable(original):
                    entry["reason"] = "backend does not export this operation"
                    continue
                try:
                    registered = registry.get_implementation(operation, backend=backend)
                except Exception as error:
                    entry["reason"] = "registry unavailable: " + type(error).__name__ + ": " + str(error)
                    continue
                if registered is not original:
                    raise RuntimeError(f"{key}: registered implementation differs from backend export")
                replacement = audit.wrap(original, backend, operation)
                setattr(module, operation, replacement)
                audit.hooks.append((module, operation, original, replacement, backend))
                if registry.get_implementation(operation, backend=backend) is not replacement:
                    raise RuntimeError(f"{key}: registry did not resolve the wrapped export")
                entry.update(status="installed", registry_resolves_wrapper=True,
                             wraps_existing_row_guard=hasattr(original, "_h3_row_chunk_policy"))
    except BaseException:
        for module, operation, original, replacement, backend in reversed(audit.hooks):
            setattr(module, operation, original)
        raise
    audit.flush()
    _active_auditor = audit
    atexit.register(audit.flush)
    return audit.summary()


def flush():
    """Persist final counts before copying evidence while a server remains up."""
    if _active_auditor is not None:
        _active_auditor.flush()
        return _active_auditor.summary()
    return None
