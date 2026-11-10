"""Immutable market-only context reduction; no finance or account initialization."""
from dataclasses import dataclass, replace
from datetime import date
import hashlib
import json

VERSION = 'NATIVE1709-MARKET-PROOF-BOOTSTRAP-1'

@dataclass(frozen=True)
class MarketProof:
    scope: str
    source: str | None = None
    seq: int = 0
    context: str | None = None
    permit: bool = False
    support: bool = False
    mature: bool = False
    events: tuple[str, ...] = ()
    last_day: str | None = None
    proof_history: tuple[dict, ...] = ()

def cursor(day):
    return date.fromisoformat(day).toordinal()

def source_signature(source_dict):
    return hashlib.sha256(json.dumps(source_dict,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def reduce_market(old, *, source, day, seq, events, permit, support):
    if old.last_day is not None and day <= old.last_day:
        raise ValueError('nonincreasing original market clock')
    if not source or seq != old.seq+1:
        raise ValueError('source missing or scope observation sequence discontinuity')
    n=old if old.source==source else replace(old,source=source,context=None,permit=False,support=False,mature=False,events=())
    ev=tuple(events)
    if any(e.startswith('price_failure') or e=='source_changed_context_ended' for e in ev):
        n=replace(n,context=None,support=False,mature=False)
    history=old.proof_history
    for kind in ev:
        if kind in ('break_started','repair_restored'):
            n=replace(n,context=f'{old.scope}|{source}|{cursor(day)}|{seq}',mature=False)
        elif kind=='price_advance' and n.context:
            n=replace(n,mature=True)
        if kind in ('break_started','repair_restored','price_advance') and n.context:
            history=history+(dict(scope=old.scope,source=source,context=n.context,kind=kind,
                confirmed=cursor(day),seq=seq,known=cursor(day),
                event_id=f'{old.scope}|{source}|{cursor(day)}|{seq}|{kind}'),)
    return replace(n,seq=seq,permit=bool(permit),support=bool(support and n.context),
                   events=ev,last_day=day,proof_history=history)

def from_dict(v):
    v=dict(v);v['events']=tuple(v['events']);v['proof_history']=tuple(v['proof_history'])
    r=MarketProof(**v)
    if r.mature and not r.context:raise ValueError('mature without market context')
    if any(e['confirmed']>cursor(r.last_day) or e['known']>cursor(r.last_day) or e['seq']>r.seq for e in r.proof_history):
        raise ValueError('future proof in restored context')
    return r
