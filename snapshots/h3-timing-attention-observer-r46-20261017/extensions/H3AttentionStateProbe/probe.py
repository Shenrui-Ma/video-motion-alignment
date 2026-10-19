"""Fixed post-RoPE reference-time readout; never receives writable original QKV."""
import math
import torch

HEADS = (0, 14, 28, 42)
ROWS = (2, 6, 11, 16, 20)
COLS = (4, 12, 20, 28, 36)
SPANS = tuple((1, 4, 4, 4, 4)[i % 5] for i in range(42))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def mapping(plan, positions):
    require(plan['seq_len'] == 87592 and plan['frame_rows'] == 943, 'frozen packed geometry')
    require(plan['reference_video_segment'] == [7910, 47516] and
            plan['target_video_segment'] == [47986, 87592], 'frozen segments')
    require(tuple(positions.shape) == (87592, 3) and positions.dtype == torch.float64,
            'full actual position tensor required')
    ra, rb = plan['reference_video_segment']; ta, tb = plan['target_video_segment']
    area = math.sqrt(46 * 82)
    hh = (torch.arange(23, dtype=torch.float64) * (46 / area / 23) + (1 - 46 / area) / 2) * 32
    ww = (torch.arange(41, dtype=torch.float64) * (82 / area / 41) + (1 - 82 / area) / 2) * 32
    h, w = torch.meshgrid(hh, ww, indexing='ij')
    spatial = torch.stack((h.reshape(-1), w.reshape(-1)), -1)
    spans = torch.tensor(SPANS, dtype=torch.float64) * (5.0 / 3.0)
    times = torch.cat((torch.zeros(1, dtype=torch.float64), spans[:-1].cumsum(0)))
    for a, b, origin in ((ra, rb, 6961.0), (ta, tb, 7196.0)):
        actual = positions[a:b].detach().cpu().reshape(42, 943, 3)
        require(torch.equal(actual[:, :, 1:], spatial[None].expand(42, -1, -1)),
                'spatial patch ordering differs')
        require(torch.equal(actual[:, :, 0], (times + origin)[:, None].expand(-1, 943)),
                'temporal position ordering differs')
    frame_intervals = []; cursor = 0
    for n in SPANS:
        frame_intervals.append([cursor, cursor + n - 1]); cursor += n
    queries = [{'bin': t, 'row': r, 'col': c, 'local_index': t * 943 + r * 41 + c,
                'packed_index': ta + t * 943 + r * 41 + c,
                'source_frames_inclusive': frame_intervals[t]}
               for t in range(42) for r in ROWS for c in COLS]
    return {'heads': list(HEADS), 'queries': queries, 'frame_intervals': frame_intervals,
            'reference_segment': [ra, rb], 'target_segment': [ta, tb],
            'position_scope': 'nominal position bins, not exact VAE receptive fields or calibrated lag'}


def read_distribution(q, k, v, full_lse, attention, *, bins=42, frame_rows=943, query_bins=None,
                      lse_atol=0.005, mass_excess_atol=0.005, sum_atol=2e-5):
    """Only independent bounded input copies enter this function. No clipping."""
    require(q.ndim == k.ndim == v.ndim == 4 and k.shape == v.shape, 'QKV rank/shape')
    require(q.shape[:2] == k.shape[:2] and q.shape[-1] == k.shape[-1], 'head dimensions')
    require(k.shape[2] == bins * frame_rows and tuple(full_lse.shape) == tuple(q.shape[:-1]),
            'bin/full-LSE shape')
    require(query_bins is not None, 'fixed query-bin mapping required')
    query_bins = torch.as_tensor(query_bins, device=q.device, dtype=torch.long)
    require(tuple(query_bins.shape) == (q.shape[2],) and bool(((query_bins >= 0) & (query_bins < bins)).all()),
            'query bin outside reference support')
    before = [x.clone() for x in (q, full_lse)]
    # K/V equality is checked against their original selected slices by caller;
    # avoid another pair of four-head full-reference GPU copies.
    rows = []
    same_output = torch.empty_like(q)
    for i in range(bins):
        bin_output, lse = attention(q, k[:, :, i * frame_rows:(i + 1) * frame_rows],
                           v[:, :, i * frame_rows:(i + 1) * frame_rows])
        # Retain only the queries assigned to this bin, not 42 output banks.
        selected = query_bins == i
        same_output[:, :, selected] = bin_output[:, :, selected]
        rows.append(lse)
        del bin_output
    bin_lse = torch.stack(rows, -1)
    reference_output, reference_lse = attention(q, k, v)
    reduced = torch.logsumexp(bin_lse, -1)
    p = (bin_lse - reduced[..., None]).exp()
    mass = (reduced - full_lse).exp()
    delta = mass[..., None] * (same_output.float() - reference_output.float())
    delta_l2 = torch.linalg.vector_norm(delta, dim=-1)
    delta_rms = delta.square().mean(-1).sqrt()
    errors = {'group_lse_max_abs': float((reduced - reference_lse).abs().max()),
              'subset_lse_max_excess': float((reduced - full_lse).max()),
              'probability_sum_max_abs': float((p.sum(-1) - 1).abs().max())}
    nonfinite_errors = [k for k, v in errors.items() if not math.isfinite(v)]
    errors = {k: v if math.isfinite(v) else None for k, v in errors.items()}
    finite = all(bool(torch.isfinite(x).all()) for x in (bin_lse, reference_lse, full_lse, p, mass, reference_output, same_output, delta_l2, delta_rms))
    gates = {'finite': finite, 'group_lse': errors['group_lse_max_abs'] is not None and errors['group_lse_max_abs'] <= lse_atol,
             'subset_lse': errors['subset_lse_max_excess'] is not None and errors['subset_lse_max_excess'] <= mass_excess_atol,
             'probability_sum': errors['probability_sum_max_abs'] is not None and errors['probability_sum_max_abs'] <= sum_atol,
             'query_lse_unchanged': torch.equal(q, before[0]) and torch.equal(full_lse, before[1])}
    return {'bin_lse': bin_lse, 'reference_lse': reference_lse, 'reduced_reference_lse': reduced,
            'full_lse': full_lse, 'probabilities': p, 'reference_mass': mass,
            'reference_output': reference_output, 'same_bin_output': same_output,
            'mass_weighted_readout_difference_l2': delta_l2,
            'mass_weighted_readout_difference_rms': delta_rms,
            'quality': {'status': 'PASS' if all(gates.values()) else 'UNKNOWN_NUMERICAL',
                        'gates': gates, 'errors': errors, 'nonfinite_error_fields': nonfinite_errors, 'clamped': False,
                        'additional_attention_calls': bins + 1}}


def describe(distribution, map_record):
    p = distribution['probabilities'].float()
    mass = distribution['reference_mass'].float()
    intervals = map_record['frame_intervals']
    centers = p.new_tensor([(a + b) / 2 for a, b in intervals])
    query_bins = torch.tensor([r['bin'] for r in map_record['queries']], device=p.device)
    center = centers[query_bins]
    same = p.gather(-1, query_bins[None, None, :, None].expand(*p.shape[:-1], 1)).squeeze(-1)
    adjacent = sum(p.gather(-1, (query_bins + d).clamp(0, len(intervals)-1)[None, None, :, None]
                          .expand(*p.shape[:-1], 1)).squeeze(-1) *
                   ((query_bins + d >= 0) & (query_bins + d < len(intervals))) for d in (-1, 0, 1))
    entropy = -(p * p.clamp_min(torch.finfo(p.dtype).tiny).log()).sum(-1)
    peaks, indices = p.topk(2, dim=-1)
    offset = (p * centers).sum(-1) - center
    lo = p.new_tensor([x[0] for x in intervals]); hi = p.new_tensor([x[1] for x in intervals])
    distance = (lo[None, :] - hi[query_bins, None]).clamp_min(0) + (lo[query_bins, None] - hi[None, :]).clamp_min(0)
    return {'same_bin_mass': same, 'same_or_adjacent_bin_mass': adjacent, 'entropy_nats': entropy,
            'top2_probability': peaks, 'top2_bins': indices, 'expected_reference_center_minus_query_center_frames': offset,
            'expected_interval_distance_frames': (p * distance).sum(-1),
            'unweighted_mean_offset_frames': float(offset.mean()),
            'reference_mass_weighted_mean_offset_frames': float((offset * mass).sum() / mass.sum()) if float(mass.sum()) > 0 else None,
            'interpretation': 'reference-time descriptors, not motion-delay estimates; all fixed rows retained'}
