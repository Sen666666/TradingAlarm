"""Read-only checkpoints and P/G decomposition; no decision or reserve callbacks."""
from decimal import Decimal as D
import copy
import recycle_bridge as M
E = M.E

def pg(mark, floor, qty, total_cost):
    r = D(qty) * max(D(0), mark - floor)
    if total_cost is None or qty <= 0:
        return dict(R=r, P=None, G=None, status='COST_UNKNOWN')
    unit = total_cost / D(qty)
    p = D(qty) * max(D(0), min(mark, unit) - floor)
    # Residual is the authoritative nominal R minus P; exact Decimal identity.
    g = r - p
    assert p >= 0 and g >= 0 and p + g == r
    return dict(R=r, P=p, G=g, cost_per_share=unit, status='KNOWN')

def checkpoint(b, day, phase):
    snap = b.snapshot(day, phase)
    layers = []
    for x in snap.holdings:
        active = [a for a in b._active_layers(x.round_id) if a.kind ==
                  ('core' if x.qty == int(b.s.archives[x.round_id].get('core', 0))
                   and x.floor == D(str(b.s.facts[x.sid].get(
                       b.s.cal[b.s.cal < day][-1] if phase == 'OPEN' else day, {}).get('i_floor'))) /
                       b.s.archives[x.round_id]['fac'] else 'add')]
        # Select by original construction order instead of ambiguous equal quantities.
        st = b.s.archives[x.round_id]
        prior = b.s.cal[b.s.cal < day]
        fact_day = prior[-1] if phase == 'OPEN' else day
        core_floor = D(str(b.s.facts[x.sid].get(fact_day, {})['i_floor'])) / st['fac']
        core_matches = int(st.get('core', 0)) == x.qty and x.floor == core_floor
        already_core = any(a['round_id'] == x.round_id and a['kind'] == 'core' for a in layers)
        kind = 'core' if core_matches and not already_core else 'add'
        active = [a for a in b._active_layers(x.round_id) if a.kind == kind]
        cost = sum((a.cost for a in active), D(0)) if sum(a.qty for a in active) == x.qty else None
        layers.append(dict(round_id=x.round_id, sid=x.sid, sector=x.sector, pool=x.pool,
            kind=kind, qty=x.qty, mark=x.mark, floor=x.floor, capital=x.capital,
            **pg(x.mark, x.floor, x.qty, cost)))
    risks = {p: sum((x['R'] for x in layers if x['pool'] == p), D(0))
             for p in ('probe', 'confirmed')}
    return copy.deepcopy(dict(day=day, phase=phase, reconciliation=b.reconcile(day, phase),
        round_balances={rid:dict(sid=st['sid'], core=st.get('core', 0), add=st.get('add', 0),
            cash=st.get('cash', D(0)), receivable=st.get('receivable', D(0)),
            pool=b.pools.get(rid)) for rid, st in b.s.archives.items()},
        states=b.states, claims=list(b.s.claims.values()),
        orders=[{k:o[k] for k in ('order_id','round_id','sid','kind','q','fee','risk','pool','status')}
                for o in b.orders.values()],
        layers=layers, nominal_R_probe=risks['probe'], nominal_R_confirmed=risks['confirmed'],
        nominal_R_all=risks['probe'] + risks['confirmed'],
        risk_complete=snap.certified,
        unknown=snap.unknown,
        note='Report only. R_all has no new cap. P/G use fee-inclusive live-layer buy cost; no dividend cost rebasing.'))
