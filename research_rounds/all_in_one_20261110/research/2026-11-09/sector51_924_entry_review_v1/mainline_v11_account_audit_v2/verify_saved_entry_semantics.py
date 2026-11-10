"""Strict saved-output entry semantic audit. No strategy import, Data, model or network.
Checks real bool scalar and candidate against sealed CP parquet, then raw OPEN/CLOSE suffix.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import hashlib,json,argparse,sys
sys.dont_write_bytecode=True
import numpy as np
import pandas as pd
read=lambda p:json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def bool_exact(v):
    assert type(v) is bool or isinstance(v,np.bool_),('not_real_bool_scalar',repr(v),str(type(v)))
    return bool(v)
def pos(v):
    try:return D(str(v)).is_finite() and D(str(v))>0
    except Exception:return False

def verify(path):
    path=Path(path).resolve();sources=read(path/'SOURCE_HASHES.json');events=read(path/'ENTRY_CP_EVENTS.json');decisions=read(path/'ENTRY_GATE_DECISIONS.json');orders=read(path/'ORDERS.json');end=read(path/'DAY_LEDGER.json')[-1]['day']
    manifests=[p for p in sources if p.endswith('/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')];assert len(manifests)==1
    manifest={x['symbol']:x for x in read(manifests[0])};frames={};provenance={};identities={};checks=Counter();samples=[]
    for x in read(path/'ENTRY_ARCHIVE.json')+list(read(path/'ENTRY_SHADOWS.json').values()):
        t=x['identity']['ticket_id'];assert t not in identities or identities[t]==x['identity'];identities[t]=x['identity'];provenance[t]=x['provenance']
    def frame(p):
        p=str(p)
        if p not in frames:
            assert p in sources and sha(p)==sources[p],('unsealed_or_changed_parquet',p)
            frames[p]=pd.read_parquet(p);assert frames[p].index.is_unique
        return frames[p]
    def rawpath(sid):
        ps=[p for p in manifest[sid]['source_sha256'] if p.endswith('/signal.parquet')];assert len(ps)==1,('ambiguous_original_raw',sid,ps)
        return ps[0]
    def row(f,d,label):
        dt=pd.Timestamp(d);assert dt in f.index,('missing_required_bar',d,label);return f.loc[dt]
    def lineage(z):return tuple(str(z.get(k)) for k in ('source_kind','source_path','segment_id'))
    def quote_ok(z,origin):
        assert lineage(z)==tuple(origin),'raw_source_identity_change'
        for key in ('observed_bar','price_eligible','volume_eligible'):assert bool_exact(z.get(key)),('invalid_quote',key)
        for key in ('source_invalid','synthetic_event_bar'):assert not bool_exact(z.get(key)),('invalid_quote',key)
        assert pos(z.get('adjustment_factor'))
    created=[x for x in events if x['event']=='CREATED'];assert created,'NO_REAL_ENTRY_CP_CREATED'
    bycp={};byticket=defaultdict(list);planmap=defaultdict(list);consumed=defaultdict(list)
    for e in events:
        assert e['day']<=end,'future_entry_event'
        byticket[e['ticket_id']].append(e)
        if e['event']=='CONSUMED':consumed[e['ticket_id']].append(e)
    for x in created:
        ticket=x['ticket_id'];ident=identities[ticket];p=provenance[ticket]['cp_path'];assert p==manifest[x['sid']]['refs']['CP1']
        c=row(frame(p),x['day'],'cp');assert bool_exact(c.get('receipt')) is True,('created_without_true_receipt',ticket,x['day'])
        assert pos(c.get('candidate')) and D(str(c['candidate']))==D(x['candidate']),('created_candidate_mismatch',ticket,x['day'])
        assert x['phase']=='CLOSE' and x['original_signal_day']==ident['signal_day']<=x['day']
        raw=row(frame(rawpath(x['sid'])),x['day'],'raw');quote_ok(raw,ident['origin']);assert pos(raw['raw_close'])
        floor=D(x['candidate']);assert D(str(raw['raw_close']))*D(str(raw['adjustment_factor']))>floor
        expected='ENTRY_CP:'+hashlib.sha256(json.dumps(['ENTRY_CP',x['sid'],ident['origin'],x['day'],str(floor),provenance[ticket]['model_sha256']]).encode()).hexdigest()
        assert x['entry_evidence_id']==expected,('entry_id',ticket,x['day'])
        k=(ticket,x['entry_evidence_id']);assert k not in bycp;bycp[k]=x;checks['real_created_receipt_candidate_and_source']+=1
    for x in decisions:
        assert x['day']<=end
        if x['phase']=='CLOSE':planmap[(x['sid'],x.get('original_signal_day'),x['day'])].append(x)
        if x.get('G') is not None and x['phase']=='CLOSE' and x['allocation_phase']=='MATURE':
            assert x['F'] in (-1,0,1) and x['CP_state'] in (-1,0,1)
            expect=1 if 1 in (x['F'],x['CP_state']) else -1 if -1 in (x['F'],x['CP_state']) else 0
            assert x['G']==expect,('frozen_MATURE_OR',x)
            checks['MATURE_three_valued_OR']+=1
    calendar=[x['day'] for x in read(path/'DAY_LEDGER.json')]
    fills=[]
    for o in orders:
        if o['side']!='BUY_SEED':continue
        ds=[x for x in planmap[(o['sid'],o['signal_day'],o['plan_day'])] if x.get('G') is not None];assert len(ds)==1
        plan=ds[0];phase=o['allocation_phase'];assert phase==plan['allocation_phase']
        route='EVENT_RESIDUAL_BYPASS' if phase in ('EVENT','RESIDUAL') else 'F' if plan['F']==1 else 'CP'
        assert phase in ('EVENT','RESIDUAL','MATURE')
        if phase=='MATURE':assert plan['G']==1
        if route=='CP':
            assert plan['CP_state']==1;ticket=plan['ticket_id'];ev_id=o.get('entry_evidence_id');assert ev_id and plan['entry_evidence_id']==ev_id
            created_ev=bycp[(ticket,ev_id)];receipt=created_ev['day'];assert o['signal_day']<=receipt<=o['plan_day']<o['day']
            terms=[e for e in consumed[ticket] if e['day']==o['day']];assert len(terms)==1
            slot=terms[0]['final_slot'];assert slot and slot['id']==ev_id and not slot['invalid'] and not slot['unknown_gap'] and slot['last_verified_open']==o['day'] and slot['receipt_day']==receipt
            floor=D(slot['floor']);assert floor==D(created_ev['candidate']);ident=identities[ticket];raws=frame(rawpath(o['sid']));cps=frame(provenance[ticket]['cp_path'])
            # Check all intervening real prices and CP-stream booleans, not merely absence of an INVALIDATED log.
            for d in calendar:
                if not receipt<=d<=o['day']:continue
                z=row(raws,d,'price_suffix');quote_ok(z,ident['origin']);factor=D(str(z['adjustment_factor']))
                if d>receipt:
                    assert pos(z.get('raw_open')) and D(str(z['raw_open']))*factor>floor,('entry_CP_OPEN_breach',ticket,d)
                    checks['CP_funded_fill_verified_OPEN']+=1
                if d<o['day']:
                    assert pos(z.get('raw_close')) and D(str(z['raw_close']))*factor>floor,('entry_CP_CLOSE_breach',ticket,d)
                    c=row(cps,d,'receipt_update_suffix');rv=bool_exact(c.get('receipt'))
                    if rv:assert pos(c.get('candidate')),('invalid_true_receipt_candidate',ticket,d)
                    checks['CP_funded_fill_verified_CLOSE_and_stream']+=1
            checks['CP_route_actual_MATURE_seed']+=1
        else:checks['F_route_actual_MATURE_seed' if route=='F' else 'EVENT_RESIDUAL_bypass_seed']+=1
        fills.append(dict(order_seq=o['order_seq'],sid=o['sid'],original_signal_day=o['signal_day'],actual_day=o['day'],plan_day=o['plan_day'],phase=phase,route=route,F=plan['F'],CP_state=plan['CP_state'],entry_evidence_id=o.get('entry_evidence_id')))
    for h in read(path/'HOLDINGS.json'):assert not str(h.get('cp_id')).startswith('ENTRY_CP:'),'entry_cp_in_active_account'
    return dict(verdict='PASS_SAVED_ENTRY_SEMANTICS',end=end,checks=dict(checks),route_counts=dict(Counter(x['route'] for x in fills)),actual_seed_routes=fills,CP_created_count=len(created),real_parquet_files_read=len(frames),pandas_version=pd.__version__,numpy_version=np.__version__,strategy_imported=False,Data_instantiated=False,history_replayed=False,limitations='Read-only output and sealed-parquet semantics for admission evidence; not an independent replay of the entire trading strategy or a production/PIT certification.')
def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:r=verify(a.candidate)
    except Exception as e:
        r=dict(verdict='FAIL_SAVED_ENTRY_SEMANTICS',error_type=type(e).__name__,error=str(e),strategy_imported=False,history_replayed=False)
        a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps(r,ensure_ascii=False));raise
    a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='actual_seed_routes'},ensure_ascii=False,default=str))
if __name__=='__main__':main()
