"""Isolated native-pending E3.1 5/15 ranking, NOT the original 5517 daily20 trial.
No Account/Runner imports, execution, eligibility changes or economic outputs.
Only rank is changed; existing audit aliases deliberately remain historical.
"""
from copy import deepcopy
from math import isfinite

POLICY = 'E31_NATIVE_PENDING_5F15C_FULL_QUEUE_v1'

def rank_pending(intents, state_rows, day):
    """Return (copied_intents, stock_audit, summary); never mutate inputs.

    intents: native PVR-ranked list of dicts (sid, role, rank, PVR_score).
    state_rows: iterable of dicts with sid, day, state, first_break_day;
        accepts full dated history, reads ONLY exact day. No numeric state
        price/support/PVR is used. Caller supplies point-in-time state contract.
    Unknown PVR stocks remain pinned at their original unique-stock slots.
    Among movable stocks, select first 5 current-day FIRST_BREAK and first
    15 CONFIRMED in ORIGINAL rank order, interleave 1+3, append original-order
    fallback to complete 20 and then all remaining originals. Short reservation
    buckets are compressed, matching frozen research proposal semantics.
    """
    ordered = sorted(intents, key=lambda i:(i['rank'], i['role'] != 'core'))
    orig=[]; groups={}; ranks={}
    for i in ordered:
        s=i['sid']
        if s not in groups: orig.append(s);groups[s]=[];ranks[s]=i['rank']
        assert i['role'] in ('core','mobile'), ('unknown role',s)
        assert i['rank']==ranks[s], ('inconsistent same-stock rank',s)
        assert i['role'] not in [r['role'] for r in groups[s]], ('duplicate native role',s)
        groups[s].append(i)
    assert len(set(ranks.values()))==len(ranks), 'stock ranks must be unique'
    states={}
    for r in state_rows:
        if str(r['day'])[:10] != day: continue
        s=r['sid']
        if s not in groups: continue
        assert s not in states, ('duplicate same-day state',s,day)
        states[s]={'state':r.get('state'),'first_break_day':r.get('first_break_day')}
    def score(i):
        v=i.get('PVR_score')
        return float(v) if v is not None and isfinite(float(v)) else None
    ready={}
    for s in orig:
        vals=[score(i) for i in groups[s]]
        assert all(v==vals[0] for v in vals), ('inconsistent same-stock PVR',s)
        ready[s]=vals[0] is not None
    movable=[s for s in orig if ready[s]]
    fresh=[s for s in movable if states.get(s,{}).get('state')=='FIRST_BREAK' and str(states[s].get('first_break_day'))[:10]==day][:5]
    confirmed=[s for s in movable if states.get(s,{}).get('state')=='CONFIRMED'][:15]
    selected=[]; reason={}
    for k in range(5):
        if k<len(fresh):selected.append(fresh[k]);reason[fresh[k]]='FRESH_RESERVED'
        for s in confirmed[3*k:3*k+3]:selected.append(s);reason[s]='CONFIRMED_RESERVED'
    remaining=[s for s in movable if s not in reason]
    n=max(0,min(20,len(movable))-len(selected))
    for s in remaining[:n]:reason[s]='BASE_FALLBACK'
    for s in remaining[n:]:reason[s]='ORIGINAL_TAIL'
    stream=iter(selected+remaining)
    final=[next(stream) if ready[s] else s for s in orig]
    slots=[ranks[s] for s in orig]; keys={s:slots[k] for k,s in enumerate(final)}
    pos={s:k for k,s in enumerate(final)}
    out=deepcopy(intents)
    for i in out:i['rank']=keys[i['sid']]
    audit=[dict(sid=s,day=day,original_slot=k,final_slot=pos[s],original_rank=ranks[s],new_rank=keys[s],roles=[i['role'] for i in groups[s]],state_available=s in states,state=states.get(s,{}).get('state'),first_break_day=states.get(s,{}).get('first_break_day'),native_PVR_ready=ready[s],selection_role=reason.get(s,'MISSING_PVR_PINNED')) for k,s in enumerate(orig)]
    summary=dict(policy=POLICY,day=day,unique_stocks=len(orig),intents=len(intents),state_available=len(states),missing_state=len(orig)-len(states),missing_native_PVR=sum(not ready[s] for s in orig),fresh_reserved=len(fresh),confirmed_reserved=len(confirmed),fallback_prefix=n,moved_stocks=sum(keys[s]!=ranks[s] for s in orig),prefix_definition='20 movable stocks, pinned unknown-PVR slots have precedence',original_5517_daily20_hypothesis=False)
    assert sorted(keys.values())==sorted(ranks.values())
    assert all(pos[s]==k for k,s in enumerate(orig) if not ready[s])
    assert [{k:v for k,v in i.items() if k!='rank'} for i in out]==[{k:v for k,v in i.items() if k!='rank'} for i in intents]
    return out,audit,summary
