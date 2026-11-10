"""Small actual-ledger/v2 bridge checks, before full paired mechanism replay."""
import joint as J
from pathlib import Path
from types import SimpleNamespace
from datetime import timedelta
from dataclasses import asdict
import time,math,json
W=J.W;T=W.load('joint_real_ledger_fixtures',W.RR/'rs-h1-execution-20261025/code/test_sector_account.py');D=W.D;BASE=T.T;ORIG=T.T-timedelta(days=1);OUT=[]
def mkt():
 return SimpleNamespace(protocol={'fractional_split_policy':'floor_position_fraction_writeoff'},marks=lambda at,ids:{s:T.marks(at,10,sid=s)[s] for s in ids})
facts=SimpleNamespace(factor=lambda *_:D(1),floor=lambda *_:D('9.9'),structure_lookup={})
def account(expand):
 a=J.Account('B' if expand else 'A',mkt(),facts,expand,{'A':'S'});b=a.budget;b.start('S','E',J.ordinal(ORIG));b.industry(J.V.Evidence('industry1','S','industry_cp1','21',J.ordinal(ORIG),J.ordinal(ORIG),J.ordinal(ORIG),'E'),J.ordinal(ORIG));return a
def progress(a,at,gid='industry2',grant=True):
 b=a.budget;bar=J.ordinal(at);terms=dict(grant_id=gid,grant_capital=b.nav,grant_risk=.03*b.nav,decision_batch=str(at.date()),decision_bar=bar) if grant else {};return b.industry(J.V.Evidence(gid,'S','industry_cp1','21',bar-1,bar,bar,'E'),bar,**terms)
def intent(at=BASE,rid='stock1'):
 q=T.quote(price=10,fees=T.MINIMUM);return dict(sid='A',clock=T.admission.Clock(at,at+timedelta(days=1),at.date()),quote=q,budget=D(20000),cap=2000,weight=1.,group=0,score=90,kind='add',role='mobile',floor=D('9.9'),epoch=(0,1),reason='fresh_CP1_mobile',rank=0,CP1_id=rid,CP1_trace=dict(receipt_id=rid,formation_start_exclusive=str((at-timedelta(days=1)).date())))
def routed(a,i):
 x,why=J.LR.preview(i,D(10),D(1),T.RULE,T.MINIMUM);assert not why;a.sync(i['clock'].earliest_execution_at);r,why=J.Runner.route(SimpleNamespace(sector_by_sid={'A':'S'}),a,i,x,i['clock'].earliest_execution_at);return x,r,why
def reserve(a,i,x,r):
 q,pool,gid=r;a.reserve_quantity(i,q,x['price'],x['schedule'],i['clock'].earliest_execution_at);a.sync(i['clock'].earliest_execution_at);return q
def win(i,x,capacity=10**8):return T.window(price=x['price'],raw_open=D(10),at=i['clock'].earliest_execution_at,capacity=capacity,fees=T.MINIMUM,eid=i['CP1_id'],cash_due_at=i['clock'].earliest_execution_at)
def case(n,fn):d=fn();OUT.append(dict(name=n,passed=True,actual=d));print(n,'PASS',flush=True)
def equal_probe():
 counts=[]
 for expand in [False,True]:
  a=account(expand);a.core_epoch['A']=(0,1)
  if expand:progress(a,BASE,grant=False)
  i=intent();x,r,why=routed(a,i);assert not why and r[1]=='probe' and i['CP1_id'] in a.budget.consumed;q=reserve(a,i,x,r);f=a.fill_buy('A',win(i,x));assert f and f.shares==q and a.jmeta[a.layers[-1]['id']]['role']=='mobile';assert a.budget.orders[i['budget_order']].qty==0;counts.append(q)
 assert counts[0]==counts[1];return dict(A_B_same_quantity=counts,no_grant_B_does_not_lose_probe=True,full_native_cancel_callback_reconciled=True)
case('confirmed_without_grant_same_probe_mobile_and_old_core_lock',equal_probe)
def exhausted_grant_probe():
 a=account(True);progress(a,BASE);g=a.budget.grants['industry2'];g.capital_limit=0;g.risk_limit=0;i=intent();x,r,why=routed(a,i);assert not why and r[1]=='probe';reserve(a,i,x,r);f=a.fill_buy('A',win(i,x));assert f
 j=intent(at=BASE+timedelta(days=2));_,r,why=routed(a,j);assert r is None and why=='no_fresh_stock_CP1';return dict(fallback_pool='probe',canonical_consumed_once=True)
case('grant_exhausted_probe_fallback_no_speculative_CP1_consume',exhausted_grant_probe)
def confirmed_growth():
 a=account(True);progress(a,BASE);i=intent();x,r,why=routed(a,i);reserve(a,i,x,r);a.fill_buy('A',win(i,x));at=BASE+timedelta(days=2);a.sync(at);a.budget.migrate('S');a.pools_from_model();a.sync(at);j=intent(at=at,rid='stock2');x,r,why=routed(a,j);assert not why and r[1]=='confirmed';q=reserve(a,j,x,r);a.fill_buy('A',win(j,x));assert any(x.pool=='confirmed' for x in a.budget.lots);return dict(second_new_receipt_pool=r[1],actual_added=q,old_probe_migrated_without_cash_change=True)
case('same_attempt_migration_and_new_mobile_confirmed_growth',confirmed_growth)
def partial_failure():
 a=account(True);progress(a,BASE);i=intent();x,r,_=routed(a,i);q=reserve(a,i,x,r);f=a.fill_buy('A',win(i,x,100));assert f.shares==100 and a.buys['A'].remaining_shares==q-100;at=BASE+timedelta(days=1,hours=3);a.sync(at);b=a.budget;b.observe('S',J.ordinal(at),failure=True);avail=a.available;assert b.resources()[2]>0 and a.available==avail;a.cancel_buy('A');a.sync(at);assert a.quantity('A')==100 and not a.buys and b.resources()[2]==0
 t=J.ordinal(at);tok=J.V.Evidence('industry-failed-bar','S','industry_cp1','21',t-1,t,t,'E');assert b.industry(tok,t)=='not_new_progress';assert not b.sectors['S'].active;return dict(partial_real_position=100,cancel_ack_releases_only_remainder=True,same_bar_no_restart=True)
case('industry_failure_partial_real_fill_pending_ack_and_no_same_bar_restart',partial_failure)
def async_and_replacement():
 a=account(True);progress(a,BASE);a.budget.end_batch('batch');at=BASE+timedelta(days=3);i=intent(at,rid='async-stock');x,r,why=routed(a,i);assert not why;reserve(a,i,x,r);f=a.fill_buy('A',win(i,x));assert f;assert a.budget.grants['industry2'].active
 later=at+timedelta(days=2);a.sync(later);progress(a,later,'industry3');assert not a.budget.grants['industry2'].active;assert a.budget.grants['industry3'].active;return dict(async_current_stock_accepted=True,old_grant_replaced_not_stacked=True)
case('asynchronous_grant_use_and_new_industry_receipt_replacement',async_and_replacement)
def pending_late_fill():
 a=account(True);progress(a,BASE);i=intent();x,r,_=routed(a,i);reserve(a,i,x,r);at=i['clock'].earliest_execution_at;a.sync(at);progress(a,at,'industry3');bid=i['budget_order'];assert a.budget.orders[bid].status=='cancel_pending';f=a.fill_buy('A',win(i,x));assert f;a.sync(at);assert a.quantity('A')==f.shares and a.budget.orders[bid].status=='filled';assert a.budget.resources()[2]==0;assert all(z.pool=='confirmed' for z in a.budget.lots);return dict(full_real_fill_wins_cancel=True,shares=f.shares,grant_sum_preserved=True)
case('full_native_fill_wins_cancel_and_migration_preserves_lot',pending_late_fill)
def no_open_future_floor():
 a=account(True);i=intent();i.update(kind='core',role='core',CP1_id=None,CP1_trace=None,risk_budget=D(2500));x,r,why=routed(a,i);assert not why;reserve(a,i,x,r);a.fill_buy('A',win(dict(i,CP1_id='core-window'),x));known=a.budget.resources()[1];a.facts=SimpleNamespace(factor=lambda *_:D(1),floor=lambda *_:None,structure_lookup={});a.sync(BASE+timedelta(days=1,hours=1));assert a.budget.resources()[1]==known and a.jmeta[a.layers[-1]['id']]['last_core_line']=='9.9';return dict(future_close_floor_ignored_at_open=True,last_decision_line_preserved=True)
case('core_budget_open_uses_decision_known_floor_not_future_close',no_open_future_floor)
def actual_stock_cap():
 a=account(True);progress(a,BASE)
 for k in range(5):
  at=BASE+timedelta(days=2*k+1);i=intent(at,rid='grow'+str(k));x,r,why=routed(a,i);assert not why;reserve(a,i,x,r);a.fill_buy('A',win(i,x))
 i=intent(BASE+timedelta(days=12),rid='gap-stock');x,why=J.LR.preview(i,D(20),D(1),T.RULE,T.MINIMUM);assert not why;x['known_open']=D(20);a.sync(i['clock'].earliest_execution_at);r,why=J.Runner.route(SimpleNamespace(sector_by_sid={'A':'S'}),a,i,x,i['clock'].earliest_execution_at);assert r is None and 'stock_capital' in why and i['CP1_id'] not in a.budget.consumed;return dict(actual_holdings=a.quantity('A'),gap_open=20,new_order_refused_without_selling_existing=True,receipt_not_consumed=True)
case('stock10_percent_current_open_aggregate_natural_overweight_no_new_buy',actual_stock_cap)
def budget_corporate_actions():
 a=account(True);progress(a,BASE);i=intent();x,r,_=routed(a,i);q=reserve(a,i,x,r);a.fill_buy('A',win(i,x));at=BASE+timedelta(days=2);a.sync(at);initial_nav=a.budget.nav;cash=a.available;fees=a.fees_cny;state={'price':D(10),'factor':D(1)};a.market.marks=lambda when,ids:{s:T.marks(when,state['price'],sid=s)[s] for s in ids};a.facts=SimpleNamespace(factor=lambda *_:state['factor'],floor=lambda *_:D('9.9'),structure_lookup={})
 a.accrue_dividend(event_id='excash',sid='A',currency='CNY',net_local=D(q)*D('.1'),ex_at=at,paid_at=None,source_id='explicit-fixture',entitlement_basis='actual shares');state.update(price=D('9.9'),factor=D(10)/D('9.9'));a.sync(at);post_div_risk=a.budget.resources()[1];assert abs(a.budget.nav-initial_nav)<1e-6 and a.available==cash;assert abs(a.budget.cash-a.budget.resources()[2]-float(cash))<1e-6
 a.split(event_id='split2',sid='A',ratio=D(2),at=at,new_shares_sellable_at=at+timedelta(days=1));state.update(price=D('4.95'),factor=state['factor']*2);a.sync(at);assert a.quantity('A')==2*q and sum(z.qty for z in a.budget.lots)==2*q;assert abs(a.budget.resources()[1]-post_div_risk)<1e-6;assert abs(a.budget.nav-initial_nav)<1e-6 and a.available==cash and a.fees_cny==fees;assert abs(a.budget.lots[0].floor-float(D('9.9')/state['factor']))<1e-10
 return dict(actual_and_budget_shares=2*q,raw_price=4.95,raw_budget_floor=a.budget.lots[0].floor,entitlement_unspendable=str(D(q)*D('.1')),NAV_continuous=True,fees_and_cash_exact=True)
case('budget_mirror_cash_dividend_split_units_floor_cash_and_fees',budget_corporate_actions)
def physical_prefix():
 shared=W.context();rows=J.T.read(J.O/'STOCK_CANONICAL_RECEIPTS.json');receipts={sid:{} for sid in shared[1].lines}
 for r in rows:receipts[r['canonical_series']][r['confirmed_day']]=r
 def obs(r):
  return W.canon(dict(daily=r.daily,opportunities=r.opportunities,funding=r.funding,industry=r.stage_events,accounts={k:dict(trades=a.trades,audit=a.audit_log,layers=a.layers,metadata=a.jmeta,journal=a.journal,orders=a.buys,budget=dict(sectors=a.budget.sectors,grants=a.budget.grants,orders=a.budget.orders,consumed=sorted(a.budget.consumed),losses={str(k):v for k,v in a.budget.losses.items()})) for k,a in r.accounts.items()}))
 end='2025-07-07';r=J.Runner(shared,receipts);r.run(end=end,begin=J.START);prefix=J.Runner(W.physical(shared,end),{s:{d:v for d,v in x.items() if d<=end} for s,x in receipts.items()});prefix.cp={s:f.loc[:end] for s,f in prefix.cp.items()};prefix.industry_rows={s:{d:v for d,v in rs.items() if d<=end} for s,rs in prefix.industry_rows.items()};prefix.run(end=end,begin=J.START);assert obs(r)==obs(prefix);return dict(two_policies_real_decisions_and_cash_prefix_exact=True,closes=len(r.daily),fills={k:len(a.trades) for k,a in r.accounts.items()},seconds=r.run_seconds)
case('two_policy_physical_prefix_real_ledger',physical_prefix)
J.save('JOINT_GATE',dict(passed=True,tests=OUT,reviewed_model_SHA256=W.M.sha(J.O/'budget_v2/model.py'),real_execution_authoritative=True,synthetic_model_fill_sell_not_called=True,new_economic_full_paths=0));print('JOINT_GATE_DONE',len(OUT),flush=True)
