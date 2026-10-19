import math
from pathlib import Path
import sys
import unittest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'extensions'))
from H3TemporalRouter import core


def dense(q, k, v):
    logits = q @ k.transpose(-1, -2) / math.sqrt(q.shape[-1])
    return logits.softmax(-1) @ v, logits.logsumexp(-1)


class SoftBand(unittest.TestCase):
    def test_explicit_reference_band_at_both_edges_and_middle(self):
        generator = torch.Generator().manual_seed(316)
        q, k, v = [torch.randn(1, 2, 22, 4, generator=generator) for _ in range(3)]
        plan = {'reference_video_segment': [3, 12], 'query_interval_half_open': [13, 22],
                'latent_interval_half_open': [0, 3], 'frame_rows': 3, 'seq_len': 22}
        logits = q @ k.transpose(-1, -2) / 2
        a = logits.softmax(-1)
        expected = a @ v
        for token in range(13, 22):
            t = (token - 13) // 3
            lo, hi = 3 + max(0, t - 1) * 3, 3 + min(3, t + 2) * 3
            m = a[:, :, token, 3:12].sum(-1, keepdim=True)
            original_reference = logits[:, :, token, 3:12].softmax(-1).unsqueeze(-2) @ v[:, :, 3:12]
            band_reference = logits[:, :, token, lo:hi].softmax(-1).unsqueeze(-2) @ v[:, :, lo:hi]
            expected[:, :, token] += m * (band_reference - original_reference).squeeze(-2)
        actual = core.route_attention(q, k, v, 2, plan, mode='mass_preserve', radius=1, attention=dense)
        wanted = expected.transpose(1, 2).reshape(1, 22, 8)
        torch.testing.assert_close(actual, wanted, rtol=1e-5, atol=2e-6)
        native = core.route_attention(q, k, v, 2, plan, mode='native', attention=dense)
        self.assertTrue(torch.equal(actual[:, :13], native[:, :13]))


if __name__ == '__main__':
    unittest.main()
