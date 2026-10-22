"""Validated per-query gain, copied from frozen R16. No pose ROI builder."""
SHAPE = (42, 23, 41)

class QueryGain:
    """One validated CPU constant and its device copy; unchanged across steps/heads."""
    def __init__(self, values, expected_shape=SHAPE):
        import torch
        tensor = torch.as_tensor(values, device="cpu", dtype=torch.float32).clone().contiguous()
        if tuple(tensor.shape) != tuple(expected_shape):
            raise ValueError("query mask shape mismatch")
        if not bool(torch.isfinite(tensor).all()) or not bool(((tensor >= 0) & (tensor <= 1)).all()):
            raise ValueError("query mask must be finite within[0,1]")
        self.tensor = tensor.reshape(1, 1, -1, 1)
        self.indices = torch.nonzero(tensor.reshape(-1) > 0, as_tuple=False).flatten()
        self.all_zero = len(self.indices) == 0
        self.all_one = bool((tensor == 1).all())
        self._cache = {}

    def on(self, q, rows):
        if rows != self.tensor.shape[2]:
            raise ValueError("query mask length disagrees with actual packed interval")
        key = str(q.device)
        if key not in self._cache:
            self._cache[key] = (self.tensor.to(q.device, copy=True),
                                self.indices.to(q.device, copy=True))
        return self._cache[key]

