"""Observed ACT ledger + opportunity joins only. No account simulation or policy change."""
from pathlib import Path
import sys,json,gzip,time,hashlib,collections,importlib.util
from decimal import Decimal as D
import numpy as np
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');O=ROOT/'research_rounds/fat-tail-opportunity-ledger-20261029';SRC=ROOT/'research_rounds/pvr-local-finite-capital-20261029/baseline';E1=ROOT/'research_rounds/s-entry-mechanism-audit-20261029';PV=ROOT/'research_rounds/pvr-act-comparison-20261027';BR=ROOT/'research_rounds/broad-stage-reentry-20261029'
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def export(p,rs):pd.DataFrame(rs).to_csv(p,index=False)
def maximum_gap(mask):
    run=best=0
    for x in mask:run=0 if x else run+1;best=max(best,run)
    return best

stage=sys.argv[1];started=time.monotonic();assert stage in ['sample','full'];dest=O/stage;dest.mkdir(exist_ok=False)
meta=pd.read_csv(ROOT/'research_rounds/tech-compound-design-20261026/proposed-pool.csv').fillna('').set_index('symbol');assert len(meta)==407
cache=pd.read_parquet(E1/'market-cache.parquet');opps=pd.read_parquet(E1/'opportunities.parquet');assert len(cache)==277167 and len(opps)==5349
obj=read(SRC/'accounts-v2/I__S0_base.json');daily=[r for r in rows(SRC/'accounts-v2/daily.jsonl.gz') if r['account']=='I__S0_base'];dec=[r for r in rows(SRC/'accounts-v2/decisions.jsonl.gz') if r['account']=='I__S0_base'];assert len(daily)==len(dec)==681
ds={r['at'][:10]:r for r in daily};de={r['at'][:10]:r for r in dec};cp={r['at'][:10]:r for r in obj['audit_log'] if r['kind']=='risk_checkpoint'};dates=list(ds);datepos={d:i for i,d in enumerate(dates)}
intents={r['order_id']:r for r in obj['audit_log'] if r['kind']=='entry_contract'};reserves={r['order_id']:r for r in obj['audit_log'] if r['kind']=='reserve'};assert len(intents)==len(reserves)==69
fills=[r for r in obj['audit_log'] if r['kind']=='fill'];assert len(fills)==138 and len({r['receipt']['receipt_id'] for r in fills})==138
cs=pd.read_csv(SRC/'analysis/campaigns.csv',dtype=str);cs=cs[cs.scenario.eq('base')].to_dict('records');assert len(cs)==69 and all(c['closed']=='True' for c in cs)
legacy=pd.read_csv(BR/'analysis/winner-windows.csv');legacy=legacy[legacy.account.eq('P0')].set_index('symbol');winners=set(legacy.index[legacy.is_price_3x]);assert len(winners)==207
traded={r['receipt']['security_id'] for r in fills};actions=sorted({r.get('sid',r.get('receivable',{}).get('security_id')) for r in obj['audit_log'] if r['kind'] in ['split','split_fraction_floor_proxy','dividend_accrual']});no_event=sorted(set(meta.index)-set(opps.symbol))
sample=sorted(set(sorted(traded)[:2]+sorted(set(meta.index)-traded)[:2]+actions[:2]+no_event[:2]));ids=sample if stage=='sample' else sorted(meta.index);save(dest/'SAMPLE_SELECTION.json',dict(ids=sample,rule='ID first2 traded + first2 untraded + first2 corporate-action + first2 no E0, deduplicated; no profit ranking'))
snap=Path(read(PV/'input.json')['snapshot']['path']);features={};windows={};label_mismatch=[];legacy_window_mismatch=[]
for sid in ids:
    f=pd.read_parquet(snap/'facts'/f'{sid}.parquet').loc['2024-01-02':'2026-10-27'];f=f[f.close.gt(0)]
    if len(f):
        flag=bool(f.close.max()>=3*f.close.iloc[0]);peak=f.close.idxmax();trough=f.loc[:peak].close.idxmin();windows[sid]=(str(trough.date()),str(peak.date()));features[sid]=dict(price_3x=flag,first_close=float(f.close.iloc[0]),peak_multiple=float(f.close.max()/f.close.iloc[0]))
        if flag!=(sid in winners):label_mismatch.append(sid)
        if sid in legacy.index and (windows[sid][0]!=legacy.loc[sid,'trough'] or windows[sid][1]!=legacy.loc[sid,'peak']):legacy_window_mismatch.append(sid)
    else:features[sid]=dict(price_3x=None,first_close=None,peak_multiple=None);windows[sid]=(None,None)
assert not label_mismatch and not legacy_window_mismatch,(label_mismatch,legacy_window_mismatch)

# Original signal structure IDs are used only for retrospective joining, not a new trading rule.
event_lookup={};event_days={};eg={sid:g for sid,g in opps.groupby('symbol')};gcache={};unlinked_signal=0;overlaps=0
for sid,g0 in cache[cache.symbol.isin(ids)].groupby('symbol',sort=True):
    g=g0.sort_values('date').copy();g['day']=g.date.dt.strftime('%Y-%m-%d');g['event_id']=None
    for e in eg.get(sid,pd.DataFrame()).to_dict('records'):
        mask=g.day.ge(e['start']) & (g.day.lt(e['end_signal']) if e['end_signal'] is not None else True)
        mask &= g.e0_target.eq(1)&g.e0_ready.eq(1)&g.segment_id.eq(e['source_segment'])
        overlaps+=int(g.loc[mask,'event_id'].notna().sum());g.loc[mask,'event_id']=e['event_id'];event_days[e['event_id']]=list(g.loc[mask,'day'])
    unlinked_signal+=int((g.Q & g.event_id.isna()).sum())
    for r in g.itertuples(index=False):event_lookup[(r.day,sid)]=r.event_id
    gcache[sid]=g.set_index('day',drop=False)
assert overlaps==0 and unlinked_signal==0,(overlaps,unlinked_signal)
orderlinks=[];filllinks=[];order_event={};missing_orders=[]
for oid,x in intents.items():
    sid=x['sid']
    if sid not in ids:continue
    key=event_lookup.get((x['decision_at'][:10],sid));order_event[oid]=key
    if key is None:missing_orders.append(oid)
    ff=[r['receipt'] for r in fills if r['order_id']==oid and r['receipt']['side']=='buy']
    orderlinks.append(dict(order_id=oid,symbol=sid,decision_at=x['decision_at'],event_id=key,budget=x['budget'],buy_fill_count=len(ff),first_fill=ff[0]['at'] if ff else None,gross=sum((D(f['gross_cny']) for f in ff),D(0)),fees=sum((D(f['fees_cny']) for f in ff),D(0))))
for r in fills:
    f=r['receipt'];sid=f['security_id']
    if sid not in ids:continue
    if f['side']=='buy':key=order_event.get(r['order_id']);owner='buy_decision_order'
    else:
        cyc=[c for c in cs if c['symbol']==sid and c['exit_at']==f['at']];assert len(cyc)==1,(sid,f['at'],'ambiguous sell cycle')
        bb=[r0 for r0 in fills if r0['receipt']['side']=='buy' and r0['receipt']['security_id']==sid and r0['receipt']['at']==cyc[0]['first_buy_at']];assert len(bb)==1
        key=order_event.get(bb[0]['order_id']);owner='unique_actual_cycle_first_buy'
    filllinks.append(dict(receipt_id=f['receipt_id'],order_id=r['order_id'],symbol=sid,side=f['side'],at=f['at'],event_id=key,ownership=owner,shares=f['shares'],gross=f['gross_cny'],fees=f['fees_cny']))
assert not missing_orders and all(r['event_id'] for r in filllinks)
export(dest/'order-event-links.csv',orderlinks);export(dest/'fill-event-links.csv',filllinks)

stockrows=[];feecomponents=[];actionrows=[];financial_residual=[];assert D(daily[-1]['inventory'])==0 and D(daily[-1]['order_reserved'])==0 and D(daily[-1]['sale_receivable'])==0
outstanding=obj['outstanding_dividends'];outstanding=list(outstanding.values()) if isinstance(outstanding,dict) else outstanding
for sid in ids:
    sf=[r for r in fills if r['receipt']['security_id']==sid];buy=sum((D(r['receipt']['gross_cny']) for r in sf if r['receipt']['side']=='buy'),D(0));sell=sum((D(r['receipt']['gross_cny']) for r in sf if r['receipt']['side']=='sell'),D(0));bf=sum((D(r['receipt']['fees_cny']) for r in sf if r['receipt']['side']=='buy'),D(0));sfv=sum((D(r['receipt']['fees_cny']) for r in sf if r['receipt']['side']=='sell'),D(0));div=sum((D(r['receivable']['net_local']) for r in obj['audit_log'] if r['kind']=='dividend_accrual' and r['receivable']['security_id']==sid),D(0));claim=sum((D(r['net_local']) for r in outstanding if r['security_id']==sid),D(0));paid=div-claim;trade=sell-buy-bf-sfv;net=trade+paid+claim
    old=sum((D(c['net_pnl']) for c in cs if c['symbol']==sid),D(0));assert net==old,(sid,'stock finance',net,old);financial_residual.append(net-old)
    aa=[r for r in obj['audit_log'] if r['kind'] in ['split','split_fraction_floor_proxy'] and r.get('sid')==sid]
    for a in aa:actionrows.append(dict(symbol=sid,**a))
    for r in sf:
        for component,v in r['fee_components'].items():feecomponents.append(dict(symbol=sid,receipt_id=r['receipt']['receipt_id'],side=r['receipt']['side'],component=component,amount=v))
    stockrows.append(dict(symbol=sid,name=meta.loc[sid,'name'],industry=meta.loc[sid,'industry'],is_price_3x=sid in winners,has_E0=sid in eg,buy_gross=buy,sell_gross=sell,buy_fees=bf,sell_fees=sfv,realized_trade_pnl=trade,unrealized_trade_pnl=D(0),dividend_cash_paid=paid,dividend_receivable=claim,corporate_action_records=len(aa),net_equity_profit=net,cycles=sum(c['symbol']==sid for c in cs)))
export(dest/'stock-actual-finance.csv',stockrows);export(dest/'fee-components.csv',feecomponents);export(dest/'corporate-actions.csv',actionrows)

capacity={'total_slots_full','sector_issuer_slots_full','sector_slots_full','issuer_already_occupied'};dayrows=[];eventrows=[];windowrows=[];exitrows=[]
for sid in ids:
    g=gcache[sid];sr=[]
    for day,z in g.iterrows():
        d=ds[day];dc=de[day];on=cp[day]['on'];held=int(d['positions'].get(sid,0));reasons=sorted({reason for s,reason in dc['rejected'] if s==sid});accepted=sid in dc['accepted'];pending=sid in d['pending_buys'];raw=bool(z.i_buy);q=bool(z.Q);cap=any(x in capacity for x in reasons);budget=any('budget' in x or 'quantity' in x for x in reasons)
        assert (sid in dc['eligible'])==(q and on),(sid,day,'Q cache vs original actual eligibility')
        if held:br='held'
        elif not raw:br='no_new_I_signal'
        elif not q:br='I_signal_not_full_Q'
        elif not on:br='ACT_paused'
        elif pending:br='pending_buy'
        elif accepted:br='accepted_no_current_close_position'
        elif cap:br='explicit_capacity_rejection'
        elif budget:br='explicit_budget_or_quantity_rejection'
        elif reasons:br='other_logged_rejection'
        else:br='eligible_unordered_unknown'
        a=dict(date=day,symbol=sid,event_id=z.event_id,is_price_3x=sid in winners,e0_known=pd.notna(z.e0_target),e0_active=bool(z.e0_target==1 and z.e0_ready==1),i_known=pd.notna(z.i_target),i_active=bool(z.i_target==1),raw_I_signal=raw,Q=q,ACT_on=on,held=held>0,shares=held,accepted=accepted,pending_buy=pending,capacity_logged=cap,budget_or_quantity_logged=budget,logged_reasons='|'.join(reasons),observable_day_gate=br)
        sr.append(a);dayrows.append(a)
    sdf=pd.DataFrame(sr).set_index('date',drop=False)
    for e in eg.get(sid,pd.DataFrame()).to_dict('records'):
        ss=sdf[sdf.event_id.eq(e['event_id'])];ol=[x for x in orderlinks if x['event_id']==e['event_id']];fl=[x for x in filllinks if x['event_id']==e['event_id'] and x['side']=='buy'];I=ss[ss.raw_I_signal];Q=ss[ss.Q]
        if fl:gate='actual_entry'
        elif I.empty:gate='no_I_signal_in_structure'
        elif Q.empty:gate='I_signal_but_no_full_Q'
        else:gate=str(Q.iloc[0].observable_day_gate)
        firstfill=min((x['at'][:10] for x in fl),default=None);firstq=Q.index[0] if len(Q) else None
        eventrows.append(dict(**e,is_price_3x=sid in winners,structure_observed_closes=len(ss),I_snapshots=len(I),Q_snapshots=len(Q),first_I=I.index[0] if len(I) else None,first_Q=firstq,orders=len(ol),buy_fills=len(fl),first_fill=firstfill,entry_intervals_from_first_Q=datepos[firstfill]-datepos[firstq] if firstfill and firstq else None,held_closes=int(ss.held.sum()),ACT_paused_Q_snapshots=int((ss.Q&~ss.ACT_on).sum()),capacity_Q_snapshots=int((ss.Q&ss.capacity_logged).sum()),budget_Q_snapshots=int((ss.Q&ss.budget_or_quantity_logged).sum()),has_no_new_I_while_I_active=bool((~ss.raw_I_signal&ss.i_active).any()),has_actual_exit=any(c['symbol']==sid and any(x['at']==c['first_buy_at'] for x in fl) for c in cs),has_reentry_same_structure=len(ol)>1,first_observable_breakpoint=gate))
    start,end=windows[sid];ww=sdf.loc[start:end] if start else sdf.iloc[:0];absent=ww[~ww.held]
    windowrows.append(dict(symbol=sid,name=meta.loc[sid,'name'],is_price_3x=sid in winners,trough=start,peak=end,observations=len(ww),held_days=int(ww.held.sum()),holding_coverage=float(ww.held.mean()) if len(ww) else None,max_absent_closes=maximum_gap(ww.held),new_I_days=int(ww.raw_I_signal.sum()),Q_days=int(ww.Q.sum()),absent_closes=len(absent),absent_no_new_I=int((~absent.raw_I_signal).sum()),absent_I_active_no_new_signal=int((absent.i_active&~absent.raw_I_signal).sum()),absent_Q_ACT_paused=int((absent.Q&~absent.ACT_on).sum()),absent_Q_capacity_logged=int((absent.Q&absent.capacity_logged).sum()),absent_Q_budget_logged=int((absent.Q&absent.budget_or_quantity_logged).sum()),absent_unknown=int(absent.observable_day_gate.eq('eligible_unordered_unknown').sum()),no_new_I_and_ACT_paused=int((~absent.raw_I_signal&~absent.ACT_on).sum())))
    for c in [x for x in cs if x['symbol']==sid]:
        buy=[r for r in fills if r['receipt']['security_id']==sid and r['receipt']['side']=='buy' and r['receipt']['at']==c['first_buy_at']][0];eid=order_event[buy['order_id']];sell=[r for r in fills if r['receipt']['security_id']==sid and r['receipt']['side']=='sell' and r['receipt']['at']==c['exit_at']][0];req=[r for r in obj['audit_log'] if r['kind']=='exit_request' and r['event_id']==sell['order_id']];assert len(req)==1;decisionday=req[0]['at'][:10];sale_day=c['exit_at'][:10];z=g.loc[decisionday]
        cause='ACT_pause' if not cp[decisionday]['on'] else 'original_I_target_off' if z.i_target==0 else 'unknown_exit_request_cause';after=g[g.day.ge(sale_day)];forward=after.iloc[:21];same=after[after.event_id.eq(eid)];futureI=same[same.i_buy.astype(bool)];futureQ=same[same.Q];futurefills=[r for r in filllinks if r['symbol']==sid and r['event_id']==eid and r['side']=='buy' and r['at']>c['exit_at']];base=D(sell['price'])*D(str(g.loc[sale_day,'factor']))
        exitrows.append(dict(symbol=sid,entry_at=c['first_buy_at'],event_id=eid,exit_request_at=req[0]['at'],sold_at=c['exit_at'],request_cause=cause,e0_active_at_request=bool(z.e0_target==1),I_target_at_request=float(z.i_target) if pd.notna(z.i_target) else None,cycle_net_pnl=c['net_pnl'],cycle_net_return=c['net_return'],post_exit21_complete=len(forward)==21,post_exit21_price_change=float(D(str(forward.iloc[-1].close))/base-1) if len(forward)==21 else None,same_structure_future_I_signals=len(futureI),same_structure_future_Q=len(futureQ),same_structure_future_Q_ACT_paused=sum(not cp[d]['on'] for d in futureQ.index),same_structure_actual_reentry_fills=len(futurefills),first_same_structure_reentry=futurefills[0]['at'] if futurefills else None))
pd.DataFrame(dayrows).to_parquet(dest/'daily-observed-funnel.parquet',index=False);export(dest/'structure-opportunities.csv',eventrows);export(dest/'all-stock-windows.csv',windowrows);export(dest/'actual-exit-reparticipation.csv',exitrows)

if stage=='full':
    # Audit the completed original ledger; this function never creates a cash account.
    sys.path.insert(0,str(ROOT/'research_rounds/tech-finite-compound-20261026/code'));spec=importlib.util.spec_from_file_location('original_independent_audit',ROOT/'research_rounds/tech-finite-compound-20261026/code/analyze_v2.py');A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A);A.CORE=PV/'input';prices=A.IndependentPrices();oldmeta=read(ROOT/'research_rounds/rs-h1-execution-20261025/inputs-v2/metadata.json');rules=read(PV/'execution-rules-v2.json');calendar=sorted(set([pd.Timestamp(x) for x in rules['calendars']['A']]+[pd.Timestamp(f'2026-10-{d}T09:30:00+08:00') for d in ['27','28','29','30']]));contrib=[];audited,check=A.old.audit_account('I__S0_base',obj,daily,prices,oldmeta,calendar,contrib);assert check['passed'] and len(audited)==69
    net=sum((r['net_equity_profit'] for r in stockrows),D(0));assert net==D(daily[-1]['nav'])-D(1000000);assert sum((r['buy_fees']+r['sell_fees'] for r in stockrows),D(0))==D(daily[-1]['fees_cny']);assert sum((r['dividend_receivable'] for r in stockrows),D(0))==D(daily[-1]['dividend_receivable']);assert D(1000000)+sum((r['realized_trade_pnl']+r['dividend_cash_paid'] for r in stockrows),D(0))==D(daily[-1]['available'])
    # Native daily contribution rows, stock totals, and our separate money table must agree.
    pp=collections.defaultdict(lambda:D(0))
    for x in contrib:pp[x['symbol']]+=x['net_contribution']
    assert all(pp[x['symbol']]==x['net_equity_profit'] for x in stockrows)
    sample_money=pd.read_csv(O/'sample/stock-actual-finance.csv',dtype=str);full_money=pd.read_csv(dest/'stock-actual-finance.csv',dtype=str).set_index('symbol');assert all(all(str(full_money.loc[x['symbol'],k])==str(x[k]) for k in sample_money.columns if k!='symbol') for x in sample_money.to_dict('records'))
    eventf=pd.DataFrame(eventrows);win=pd.DataFrame(windowrows);sf=pd.DataFrame(stockrows);ex=pd.DataFrame(exitrows);df=pd.DataFrame(dayrows)
    stats=dict(new_economic_paths=0,stocks=len(ids),structures=len(eventrows),I_snapshots=int(df.raw_I_signal.sum()),Q_snapshots=int(df.Q.sum()),events_any_I=int(eventf.I_snapshots.gt(0).sum()),events_any_Q=int(eventf.Q_snapshots.gt(0).sum()),events_filled=int(eventf.buy_fills.gt(0).sum()),stock_traded=len(traded),price3x_count=len(winners),actual_profit=net,realized_trade_pnl=sum((x['realized_trade_pnl'] for x in stockrows),D(0)),dividend_receivable=daily[-1]['dividend_receivable'],fees=daily[-1]['fees_cny'],financial_audit=check,first_breakpoints=eventf.first_observable_breakpoint.value_counts().to_dict(),exit_causes=ex.request_cause.value_counts().to_dict(),exit_same_structure_new_Q=int(ex.same_structure_future_Q.gt(0).sum()),exit_same_structure_reentry=int(ex.same_structure_actual_reentry_fills.gt(0).sum()),post_exit21_positive=int(ex.post_exit21_price_change.gt(0).sum()),post_exit21_complete=int(ex.post_exit21_complete.sum()),crossing_E0_exit_exposure_note='Actual buys attach uniquely to source E0; exposure can occur outside that source interval. Post-exit paths are descriptive and not foregone tradable profits.')
    stats['groups']={}
    for tag in [True,False]:
        ss=sf[sf.is_price_3x.eq(tag)];ww=win[win.is_price_3x.eq(tag)];ee=eventf[eventf.is_price_3x.eq(tag)];dd=df[df.is_price_3x.eq(tag)];missing=dd[~dd.held]
        stats['groups']['price3x' if tag else 'other200']=dict(stocks=len(ss),actual_profit=sum(ss.net_equity_profit,D(0)),traded=int(ss.cycles.gt(0).sum()),structure_events=len(ee),events_any_I=int(ee.I_snapshots.gt(0).sum()),events_any_Q=int(ee.Q_snapshots.gt(0).sum()),events_filled=int(ee.buy_fills.gt(0).sum()),window_mean_coverage=float(ww.holding_coverage.mean()),window_median_coverage=float(ww.holding_coverage.median()),window_never_held=int(ww.held_days.eq(0).sum()),window_absent_days=int(ww.absent_closes.sum()),window_absent_no_new_I=int(ww.absent_no_new_I.sum()),window_absent_I_active_no_new_signal=int(ww.absent_I_active_no_new_signal.sum()),window_absent_Q_ACT_paused=int(ww.absent_Q_ACT_paused.sum()),window_absent_Q_capacity_logged=int(ww.absent_Q_capacity_logged.sum()),window_absent_Q_budget_logged=int(ww.absent_Q_budget_logged.sum()),first_breakpoints=ee.first_observable_breakpoint.value_counts().to_dict(),flat_full_period_observed_day_gates=missing.observable_day_gate.value_counts().to_dict())
    ranked=sorted(stockrows,key=lambda x:x['net_equity_profit'],reverse=True);stats['actual_concentration']=dict(top1=ranked[:1],top5=ranked[:5],top1_profit=ranked[0]['net_equity_profit'],top5_profit=sum((x['net_equity_profit'] for x in ranked[:5]),D(0)),positive_stock_profit=sum((x['net_equity_profit'] for x in stockrows if x['net_equity_profit']>0),D(0)),negative_stock_loss=-sum((x['net_equity_profit'] for x in stockrows if x['net_equity_profit']<0),D(0)))
    # Unknown subcauses are reported explicitly, never assigned to capital by inference.
    stats['unknowns']=dict(full_Q_false_raw_I_rows=int((df.raw_I_signal&~df.Q).sum()),unresolved_non_Q_subcause='Composite Q failure does not identify industry, market, metadata, timestamp or other gate without original eligibility detail; no extra reconstruction performed.',eligible_unordered_unknown_rows=int(df.observable_day_gate.eq('eligible_unordered_unknown').sum()),unknown_exit_requests=int(ex.request_cause.eq('unknown_exit_request_cause').sum()),missing_e0_target_rows=int((~df.e0_known).sum()),missing_i_target_rows=int((~df.i_known).sum()),unmapped_order_ids=len(missing_orders),unmapped_fills=sum(not x['event_id'] for x in filllinks),signal_Q_without_event=unlinked_signal,ambiguous_day_event_assignments=overlaps,label_mismatches=len(label_mismatch),legacy_window_mismatches=len(legacy_window_mismatch))
    changed=[]
    for p,expected in read(O/'INPUT_IDENTITY.json')['sha256'].items():
        if sha(p)!=expected:changed.append(p)
    assert not changed,changed
    save(dest/'RESULTS.json',stats);print(json.dumps({k:stats[k] for k in ['stocks','structures','I_snapshots','Q_snapshots','events_any_I','events_any_Q','events_filled','stock_traded','actual_profit','first_breakpoints','exit_causes','groups','unknowns']},ensure_ascii=False,default=str),flush=True)
else:print(json.dumps(dict(stage='sample_passed',stocks=sample,linked_orders=len(orderlinks),linked_fills=len(filllinks),all_per_stock_money_exact=True,legacy_3x_labels_windows_exact=True,active_day_Q_exact=True),ensure_ascii=False),flush=True)
save(dest/'VERIFICATION.json',dict(passed=True,stage=stage,stocks=len(ids),linked_order_ids=len(orderlinks),linked_fills=len(filllinks),unlinked_orders=len(missing_orders),unlinked_fills=0,event_overlap=overlaps,per_stock_finance_exact=True,legacy_labels_and_windows_exact=True,active_day_Q_exact=True,seconds=time.monotonic()-started,new_economic_paths=0))
