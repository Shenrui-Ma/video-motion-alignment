"""Expose the task's allocator limit to Comfy's weight offload scheduler.

Physical CUDA free memory can increase when another user exits. PyTorch's
per-process fraction remains fixed; Comfy must account for both constraints.
Only this process's model_management.get_free_memory is wrapped.
"""
import functools
import importlib.abc
import importlib.machinery
import sys


def bounded_free(physical_plus_cache, cache_unused, active, cap):
    available = max(0, min(physical_plus_cache, cap - active))
    return available, max(0, min(cache_unused, available))


def patch(module, torch, cap):
    original = module.get_free_memory
    if hasattr(original, '_h3_allocator_cap'):
        if original._h3_allocator_cap != cap:
            raise RuntimeError('Conflicting allocator memory budget')
        return
    @functools.wraps(original)
    def limited(dev=None, torch_free_too=False):
        dev = module.get_torch_device() if dev is None else dev
        if getattr(dev, 'type', None) != 'cuda':
            return original(dev, torch_free_too)
        index = dev.index if dev.index is not None else torch.cuda.current_device()
        if index != 0:
            return original(dev, torch_free_too)
        physical, unused = original(dev, True)
        active = torch.cuda.memory_stats(dev)['active_bytes.all.current']
        total, cached = bounded_free(physical, unused, active, cap)
        return (total, cached) if torch_free_too else total
    limited._h3_allocator_cap = cap
    module.get_free_memory = limited


def install(torch, cap):
    target = 'comfy.model_management'
    class Loader(importlib.abc.Loader):
        def __init__(self, original): self.original = original
        def create_module(self, spec): return self.original.create_module(spec)
        def exec_module(self, module):
            self.original.exec_module(module)
            patch(module, torch, cap)
    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path, target=None):
            if fullname != 'comfy.model_management': return None
            spec = importlib.machinery.PathFinder.find_spec(fullname, path)
            if spec is not None: spec.loader = Loader(spec.loader)
            return spec
    if target in sys.modules: patch(sys.modules[target], torch, cap)
    else: sys.meta_path.insert(0, Finder())
