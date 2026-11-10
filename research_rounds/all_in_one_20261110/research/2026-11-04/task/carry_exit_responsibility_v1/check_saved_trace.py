"""Saved carry/exit timing only. No new signal, stop, or wealth engine."""
from pathlib import Path
from decimal import Decimal as D, localcontext
from collections import defaultdict,Counter
import json,gzip,hashlib,time
import pandas as pd
O=Path(__file__).resolve().parent;T=O.parent
P=T/'ma63_down_replenishment_v1'
BOOK=T/'capacity_cost_guard_v1/runs/long-v1/arms/B/pair/B.json.gz'
DAILY=T/'capacity_cost_guard_v1/runs/long-v1/arms/B/pair/daily.jsonl.gz'
MAN=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
SELECTED=['DOWN_04','DOWN_05','DOWN_06']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
def stats(rr):
    return dict(layer_spell_rows=len(rr),stocks=len({x['sid']for x in rr}),
        wealth=sum((D(x['period_wealth'])for x in rr),D(0)),
        positive_rows=sum(D(x['period_wealth'])>0 for x in rr),negative_rows=sum(D(x['period_wealth'])<0 for x in rr),zero_rows=sum(D(x['period_wealth'])==0 for x in rr),
        positive_wealth=sum((D(x['period_wealth'])for x in rr if D(x['period_wealth'])>0),D(0)),
        negative_wealth=sum((D(x['period_wealth'])for x in rr if D(x['period_wealth'])<0),D(0)))
def main():
    assert not(O/'RESULTS.json').exists(),'no repeat'
    started=time.monotonic()
    paths=[Path(__file__),P/'ALL_LAYER_PERIOD_WEALTH.json',P/'ALL_SPELL_RESULTS.json',BOOK,DAILY,MAN,
        T/'ma63_down_replenishment_review_v1/SAVED_PERIOD_WEALTH_AUDIT.json']
    sources={str(p):sha(p)for p in paths}
    save('INPUT_FREEZE.json',dict(scope='all carry in DOWN04/05/06; first requests and actual sells; no new period money split',sources=sources))
    with gzip.open(BOOK,'rt')as f:b=json.load(f)
    with gzip.open(DAILY,'rt')as f:snaps=[json.loads(x)for x in f]
    dates=[x['at'][:10]for x in snaps];assert len(dates)==726 and len(set(dates))==726
    byday={x['at'][:10]:x for x in snaps};dateindex={d:i for i,d in enumerate(dates)}
    def next_open(at):
        k=dateindex[at[:10]]+1
        return None if k==len(dates)else dates[k]+' 09:30:00+08:00'
    periods={s['spell_id']:s for s in read(P/'ALL_SPELL_RESULTS.json')if s['spell_id']in SELECTED}
    carry=[r for r in read(P/'ALL_LAYER_PERIOD_WEALTH.json')if r['spell_id']in SELECTED and r['group']=='carry_at_previous_CLOSE']
    reqs=defaultdict(list);sells=defaultdict(list)
    for a in b['audit']:
        if a['kind']=='pilot_layer_exit':
            for k in a['layers']:reqs[k].append(a)
    for tr in b['trades']:
        if tr['side']=='sell':
            for part in tr['parts']:sells[part['layer']].append(dict(at=tr['at'],raw_open=tr['raw_open'],execution_price=tr['price'],part=part,receipt_id=tr['receipt_id']))
    records=[]
    for r in carry:
        p=periods[r['spell_id']];lo,hi=p['start'],p['end'];start=p['previous_close']+' 15:10:00+08:00';end=hi+' 15:10:00+08:00';k=r['layer'];sid=r['sid']
        q0=next(x for x in byday[p['previous_close']]['layers']if x['id']==k);assert q0['qty']==r['qty_at_boundary']>0
        known_requests=[x for x in reqs[k]if x['at']<=end]
        first=known_requests[0]if known_requests else None
        category='NO_LAYER_EXIT_REQUEST_BY_END'if first is None else'ALREADY_REQUESTED_BEFORE_START'if first['at']<=start else'FIRST_REQUEST_DURING_SPELL_MIXED_MONEY_UNKNOWN'
        partlist=[x for x in sells[k]if lo<=x['at'][:10]<=hi]
        after=[x for x in sells[k]if first and x['at']>first['at']]
        nxt=next_open(first['at'])if first else None
        firstsell=after[0]if after else None
        snapshot_states=[]
        for day in p['days']:
            s=byday[day];lot=next((x for x in s['layers']if x['id']==k),None)
            if lot:
                snapshot_states.append(dict(day=day,qty=lot['qty'],stock_pending_exit=sid in s['pending_sells'],
                    layer_request_known=bool(first and first['at']<=s['at']),
                    effective_line_signal=lot['last_core_line']if lot['role']=='core'else lot['floor']))
        records.append(dict(**r,spell_start=lo,spell_end=hi,previous_CLOSE=p['previous_close'],
            timing_category=category,first_layer_request=first,request_NEXT_OPEN=nxt,
            first_actual_sell_after_request=firstsell,first_actual_sell_at_request_NEXT_OPEN=bool(firstsell and firstsell['at']==nxt),
            request_to_first_sell_sessions=None if not firstsell else dateindex[firstsell['at'][:10]]-dateindex[first['at'][:10]],
            sell_parts_in_spell=partlist,request_reason_change_observations=known_requests,
            actual_live_CLOSE_states=snapshot_states,stock_pending_at_period_boundary=sid in byday[p['previous_close']]['pending_sells'],
            broker_ack_timestamp='UNKNOWN_NOT_RECORDED_IN_SAVED_TRACE',
            pre_request_wealth=r['period_wealth']if first is None else None,
            post_request_wealth=r['period_wealth']if first and first['at']<=start else None,
            mixed_request_pre_post_money='UNKNOWN_NO_NEW_INTRASPELL_FINANCIAL_BOUNDARY'if category.startswith('FIRST_REQUEST_DURING')else'whole_spell_on_one_side_of_first_request'))
    with localcontext()as ctx:
        ctx.prec=90
        summaries=[]
        for name,p in periods.items():
            rr=[x for x in records if x['spell_id']==name];g=stats(rr)
            for key in ['wealth','positive_wealth','negative_wealth']:assert g[key]==D(p['old'][key])
            summaries.append(dict(spell_id=name,start=p['start'],end=p['end'],carry=g,
                by_timing={cat:stats([x for x in rr if x['timing_category']==cat])for cat in sorted({x['timing_category']for x in rr})},
                requests_before_or_inside=sum(x['first_layer_request']is not None for x in rr),
                next_OPEN_actual_fills=sum(x['first_actual_sell_at_request_NEXT_OPEN']for x in rr),
                delayed_actual_first_fill=sum(x['request_to_first_sell_sessions']is not None and x['request_to_first_sell_sessions']>1 for x in rr),
                unknown_pre_post_amount_rows=sum(x['timing_category'].startswith('FIRST_REQUEST_DURING')for x in rr)))
        save('ALL_CARRY_TRACE_ROWS.json',records);save('ALL_THREE_SPELL_SUMMARIES.json',summaries)
        # Prespecified explanatory selection only: largest original period-loss
        # stocks in the two negative spells, and largest profit stocks in DOWN04.
        bystock=defaultdict(list)
        for x in records:bystock[('positive_reference'if x['spell_id']=='DOWN_04'else'negative_focus',x['sid'])].append(x)
        stockrows=[dict(group=g,sid=sid,**stats(v),members=v)for(g,sid),v in bystock.items()]
        negative=sorted([x for x in stockrows if x['group']=='negative_focus'],key=lambda x:x['wealth'])[:3]
        positive=sorted([x for x in stockrows if x['group']=='positive_reference'],key=lambda x:-x['wealth'])[:2]
    manifest={x['symbol']:x for x in read(MAN)};examples=negative+positive
    facts_sources={}
    for x in examples:
        sid=x['sid'];fp=Path(manifest[sid]['refs']['facts']);facts_sources[str(fp)]=sha(fp)
    save('EXAMPLE_FACTS_FREEZE.json',dict(selection='fixed top3 period-loss stock and top2 period-profit stock; diagnostic only',sources=facts_sources))
    for x in examples:
        f=pd.read_parquet(manifest[x['sid']]['refs']['facts'],columns=['raw_close'])
        for m in x['members']:
            req=m['first_layer_request'];fill=m['first_actual_sell_after_request']
            if req:
                day=pd.Timestamp(req['at'][:10]);m['request_CLOSE_original_raw_mark']=str(f.loc[day,'raw_close'])if day in f.index else None
                m['raw_open_gap_to_request_CLOSE']=None if not(fill and m['request_CLOSE_original_raw_mark'])else str(D(fill['raw_open'])/D(m['request_CLOSE_original_raw_mark'])-1)
                m['gap_scope']='original request-close vs first actual fill rawOPEN; no claim of continuous stops or isolated PnL'
    save('MAX_THREE_LOSS_AND_TWO_PROFIT_STOCK_EXAMPLES.json',examples)
    for p,h in {**sources,**facts_sources}.items():assert sha(p)==h,p
    save('RESULTS.json',dict(status='PASS_SAVED_CARRY_REQUEST_AND_FILL_TIMING_ONLY',seconds=time.monotonic()-started,
        carry_rows=len(records),spells=3,examples=len(examples),summary=summaries,
        ACK_known=False,new_account=0,new_signal_or_stop=0,new_price_loader=0,new_pre_post_wealth_engine=0))
    print(json.dumps(dict(rows=len(records),spells=summaries),ensure_ascii=False,default=str))
if __name__=='__main__':main()
