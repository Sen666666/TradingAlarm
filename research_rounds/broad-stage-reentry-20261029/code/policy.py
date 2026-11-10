"""BSR-1 strategy state; original F/CP1 market indicators are read, not changed."""
from decimal import Decimal as D
import math
import pandas as pd

def support_cache(facts, fine, cp):
    current = None
    first = None
    vf = vc = None
    rows = []
    ff = fine.reindex(facts.index)
    cc = cp.reindex(facts.index)
    for r, f, c in zip(facts.itertuples(), ff.itertuples(), cc.itertuples()):
        day = r.Index
        key = int(r.segment_id) if bool(r.i_target) else None
        if key is None or current != key:
            vf = vc = None
            first = day if key is not None else None
        current = key
        if key is not None:
            close = float(r.close)
            if vf is not None and close <= vf: vf = None
            if vc is not None and close <= vc: vc = None
            if f.event == 1 and pd.Timestamp(f.pivot_date) >= first:
                vf = max(vf or -math.inf, float(f.pivot))
            if c.receipt is True or (pd.notna(c.receipt) and bool(c.receipt)):
                vc = max(vc or -math.inf, float(c.candidate))
        rows.append((vf, vc))
    return pd.DataFrame(rows, index=facts.index, columns=['f_valid', 'cp_valid'], dtype=float)

def new_candidates(layer, day, fine, cp):
    candidates = []
    opened = pd.Timestamp(layer['opened']).date()
    if fine is not None and fine.event == 1 and pd.Timestamp(fine.pivot_date).date() >= opened:
        candidates.append(('F', D(str(fine.pivot))))
    if cp is not None and bool(cp.receipt):
        candidates.append(('CP1', D(str(cp.candidate))))
    return candidates

def advance(layer, day, close, e_floor, fine, cp):
    """Old line is checked before changes. Returns a policy event, never fills."""
    old = layer['floor']
    if close <= old:
        return 'exit'
    if layer['kind'] == 'core':
        layer['floor'] = max(old, e_floor)
        layer['phase'] = 'CORE_TREND' if e_floor >= layer['bridge_floor'] else 'CORE_BRIDGE'
        return 'raise' if layer['floor'] > old else None
    candidates = new_candidates(layer, day, fine, cp)
    layer['floor'] = max([old, e_floor] + [p for _, p in candidates])
    if layer['kind'] == 'trial' and any(p > layer['entry_cost'] for _, p in candidates):
        layer.update(kind='core', bridge_floor=layer['floor'], promoted_at=day,
                     phase='CORE_TREND' if e_floor >= layer['floor'] else 'CORE_BRIDGE',
                     promotion_sources=[name for name, p in candidates if p > layer['entry_cost']])
        return 'promote'
    return 'raise' if layer['floor'] > old else None
