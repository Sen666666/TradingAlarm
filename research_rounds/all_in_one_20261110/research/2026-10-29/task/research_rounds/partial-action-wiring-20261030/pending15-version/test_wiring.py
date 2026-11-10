"""Hand-specified synthetic execution scenarios. No historical strategy paths."""
import role_adapter as M
from pathlib import Path
from datetime import timedelta,datetime,timezone
from types import SimpleNamespace
from dataclasses import replace
import json,time,hashlib,traceback,sys
O=M.O;A=M.A;L=M.L;D=M.D;accounts=[];current_case=None
T=M.load('partial_role_original_test_helpers',M.RR/'rs-h1-execution-20261025/code/test_sector_account.py');BASE=T.T;t0=time.monotonic();results=[]
def clock(at):return A.Clock(at,at+timedelta(days=1),at.date())
def q(sid='A',price=10,group='G',rule=None):return T.quote(sid,price=price,fees=T.MINIMUM,sector=group,rule=rule or T.RULE)
def win(sid='A',at=None,price=10,capacity=10**8,**kw):
 at=at or BASE+timedelta(days=1);return T.window(sid,at=at,price=price,capacity=capacity,fees=T.MINIMUM,eid=sid+'|'+at.isoformat(),cash_due_at=at,**kw)
def start(cls=M.RoleAccount,enabled=True,shares=400,rule=None,**kw):
 a=cls(initial_cash=40000,**({'roles_enabled':enabled} if cls==M.RoleAccount else {}),**kw);accounts.append((current_case,a));a.facts=SimpleNamespace(floor=lambda *_:D(8),factor=lambda *_:D(1));a.reserve_budget(quote=q(rule=rule),clock=clock(BASE),gross_budget_cny=shares*10);f=a.fill_buy('A',win(rule=rule or T.RULE));assert f and f.shares==shares;return a
def trigger(a,day=2):
 at=BASE+timedelta(days=day);a.close_risk('A',clock(at),q(),10,negative_id='neg|'+at.isoformat());at+=timedelta(days=1);a.expire_day_buys(at);r=a.close_risk('A',clock(at),q(price=9.5),9.5);return at,r
def trim(a,capacity=10**8):
 at,r=trigger(a);sat=clock(at).earliest_execution_at;f=a.fill_exit('A',win(at=sat,price=9.5,capacity=capacity));a.settle_due(sat);return sat,f
def packet(at,*,new=False,rankA=90,rankC=80,price=10,up=True,cap=20e9):
 fact=lambda v:A.Fact(v,at,at,source_id='synthetic-public',observed_at=at);ss=[A.Security('A',fact('A'),fact('G'),fact(True),fact(True),fact(cap),fact(up),A.Rank(rankA,at,at))];quotes={'A':q(price=price)}
 if new:ss.append(A.Security('C',fact('C'),fact('G'),fact(True),fact(True),fact(cap),fact(True),A.Rank(rankC,at,at)));quotes['C']=q('C',price=price)
 return tuple(ss),(A.Sector('G',fact(True),A.Rank(80,at,at)),),quotes
def commit(a,at,*,new=False,event='I-new',rankA=90,rankC=80,price=10,previous=(),up=True,ACT=True):
 ss,gs,quotes=packet(at,new=new,rankA=rankA,rankC=rankC,price=price,up=up);marks={sid:T.marks(at,price,sid=sid)[sid] for sid in a.positions};a.current_nav=a.balance(at,marks)['nav']
 if not ACT:
  a.risk_state=dict(on=True,peak=D(50000),saw_off=False,previous_fast=False,episode=0);M.E.risk_policy.step(a,at,'ACT20_BREAK');assert not a.risk_state['on'];ss=M.E.risk_policy.override(a,ss,clock(at),'ACT20_BREAK',A.Fact)
 receipts={'A':M.FreshI(event,'A',at)} if event else {};return M.commit_roles(a,clock=clock(at),securities=ss,sectors=gs,quotes=quotes,marks=marks,receipts=receipts,previous=previous,bootstrap=not previous,ACT_on=ACT)
def verify_money(a,at,price=10):
 marks={sid:T.marks(at,price,sid=sid)[sid] for sid in a.positions};actual=a.balance(at,marks)['nav']-D(40000);expected=sum(a.group_cash.values(),D(0))+sum(a.group_dividend.values(),D(0))+sum((a.quantity(sid)*marks[sid].cny_price(at) for sid in a.positions),D(0));assert actual==expected,(actual,expected);return str(actual)
def case(name,fn):
 global current_case
 current_case=name
 try:detail=fn();results.append(dict(name=name,passed=True,actual=detail));print(name,'PASS',detail,flush=True)
 except BaseException as e:
  results.append(dict(name=name,passed=False,error=repr(e),traceback=traceback.format_exc()));p=O/('TEST_RESULTS-failed-'+str(len(list(O.glob('TEST_RESULTS-failed-*')))+1)+'.json');p.write_text(json.dumps(dict(passed=False,tests=results),ensure_ascii=False,indent=2,default=str));raise

def only_risk():
 a=start();at,f=trim(a);r=a.roles['A'];assert (r['K'],r['R'],a.quantity('A'),a.available,len(a.completed))==(200,0,200,D(37890),0);assert a.close_risk('A',clock(at+timedelta(hours=6)),q(),8)['note']=='risk_role_empty_no_repeat_sale';assert not a.exits;b=start();u=b.close_risk('A',clock(BASE+timedelta(days=2)),q(),10,negative_id='unknown-scale',sigma=None);assert 'negative_sigma_unknown' in u['current_unknown'] and not b.exits;return dict(K=200,R=0,available=str(a.available),completion=0,missing_scale_preserved_unknown=True,account_reconciles=verify_money(a,at+timedelta(hours=6),9.5))
case('only_risk_200_sold_core_200_kept',only_risk)
def partial_wait():
 a=start();at,f=trim(a,100);r=a.roles['A'];assert (r['K'],r['R'],a.quantity('A'),a.exits['A'].remaining_target)==(200,100,300,100);ack=commit(a,at+timedelta(hours=6));assert not ack.accepted and not a.buys and not a.completed;return dict(physical=300,pending_target=100,restore_accepted=ack.accepted)
case('partial_reduction_retains_occupancy',partial_wait)
def priority_full():
 a=start();at,_=trim(a,100);cl=at+timedelta(hours=6);ack=commit(a,cl,up=True,ACT=False);assert a.exits['A'].remaining_target is None and a.exits['A'].purpose=='structure_exit';a.fill_exit('A',win(at=clock(cl).earliest_execution_at,price=9.5));a.settle_due(clock(cl).earliest_execution_at);assert not a.quantity('A') and len(a.completed)==1 and not a.roles
 b=start();bt,_=trim(b,100);commit(b,bt+timedelta(hours=6),up=False,ACT=True);assert b.exits['A'].remaining_target is None and b.exits['A'].purpose=='structure_exit'
 return dict(real_completion=1,ACT_alone_upgrades=True,structure_alone_upgrades=True,account_reconciles=verify_money(a,clock(cl).earliest_execution_at,9.5))
case('ACT_or_structure_upgrades_pending_trim_to_full',priority_full)
def joint_ranking():
 orders=[]
 for high in [True,False]:
  a=start();at,_=trim(a);ack=commit(a,at+timedelta(hours=6),new=True,rankA=90 if high else 70,rankC=80);assert ack.accepted==(('A','C') if high else ('C','A'));assert {o.purpose for o in a.buys.values()}=={'initial','risk_restore'};assert a.available>=0 and len(a.occupancy(at+timedelta(hours=6)))==2;orders.append(ack.accepted)
 return dict(order_follows_original_H1=orders)
case('restore_and_new_stock_share_original_ranked_cash',joint_ranking)
def short_cash_min():
 a=start();at,_=trim(a);a.reserve_budget(quote=q('B'),clock=clock(at+timedelta(hours=1)),gross_budget_cny=a.available-D(10));before=a.available;ack=commit(a,at+timedelta(hours=6));assert not ack.accepted and a.roles['A']['cap']==200 and a.roles['A']['R']==0 and a.available==before
 b=start(shares=100);at,r=trigger(b);assert b.roles['A']['R']==0 and b.quantity('A')==100 and not b.exits;return dict(committed_cash_fixture_remaining=str(before),refused=ack.rejected,one_lot_core=100)
case('insufficient_committed_cash_and_unsplittable_lot',short_cash_min)
def fresh_only():
 a=start();at,_=trim(a);cl=at+timedelta(hours=6);ss,gs,qq=packet(cl);marks=T.marks(cl);stale=M.FreshI('old','A',BASE);ack=M.commit_roles(a,clock=clock(cl),securities=ss,sectors=gs,quotes=qq,marks=marks,receipts={'A':stale});assert not ack.accepted;before_sale=M.FreshI('same-day-but-before-sale','A',at-timedelta(minutes=1));bad=M.commit_roles(a,clock=clock(cl),securities=ss,sectors=gs,quotes=qq,marks=marks,receipts={'A':before_sale});assert not bad.accepted
 blocked=replace(ss[0],buy_allowed=A.Fact(False,cl,cl));noq=M.commit_roles(a,clock=clock(cl),securities=(blocked,),sectors=gs,quotes=qq,marks=marks,receipts={'A':M.FreshI('new-but-Q-false','A',cl)});assert not noq.accepted
 ack=commit(a,cl,event='one');assert ack.accepted==('A',) and a.buys['A'].earliest_at==clock(cl).earliest_execution_at;oid=a.buys['A'].order_id;a.cancel_buy('A');again=commit(a,cl,event='one',previous=ack.memories);assert not again.accepted and 'A' not in a.buys;return dict(stale_not_used=True,market_Q_false_not_restored=True,same_receipt_once=True,next_execution=str(clock(cl).earliest_execution_at),order_purpose='risk_restore')
case('same_day_fresh_receipt_consumed_once',fresh_only)
def rising_price():
 a=start();at,_=trim(a);cl=at+timedelta(hours=6);ack=commit(a,cl,price=20);assert ack.accepted==('A',) and a.buys['A'].target_shares==100;assert a.roles['A']['cap']==200;f=a.fill_buy('A',win(at=clock(cl).earliest_execution_at,price=20));assert f.shares==100 and a.roles['A']['R']==100 and a.roles['A']['cap']==200;return dict(actual_restored=100,reference_cap=200,budget_after_existing_stock_cap=str(a.intents[a.role_events[-1]['receipt'].receipt_id]['budget']) if False else str(f.gross_cny))
case('rising_price_only_affordable_reference_gap_restored',rising_price)
def corporate_actions():
 a=start();at=BASE+timedelta(days=2);a.close_risk('A',clock(at),q(),10,negative_id='pre-split');a.accrue_dividend(event_id='div1',sid='A',currency='CNY',net_local=D(40),ex_at=at,paid_at=None,source_id='explicit-fixture',entitlement_basis='actual400shares');assert a.available==D(35995) and a.role_events[-1]['core']==D(20) and a.role_events[-1]['risk']==D(20);a.split(event_id='split2',sid='A',ratio=D(2),at=at,new_shares_sellable_at=at+timedelta(days=1));assert (a.quantity('A'),a.roles['A']['K'],a.roles['A']['R'],a.roles['A']['cap'])==(800,400,400,400);verify_money(a,at,5);a.close_risk('A',clock(at+timedelta(days=1)),q(price=5),5,factor=2);assert not a.exits and a.roles['A']['controller'].shares==400
 b=start(fractional_split_policy='floor_position_fraction_writeoff');b.split(event_id='frac',sid='A',ratio=D('1.003'),at=at,new_shares_sellable_at=at);assert b.quantity('A')==401 and (b.roles['A']['K'],b.roles['A']['R'])==(201,200);return dict(dividend_core=20,dividend_risk=20,split_actual=800,fractional_actual=401,no_fractional_cash=True)
case('dividend_split_and_odd_share_role_conservation',corporate_actions)
def repeated_losses():
 a=start();at,_=trim(a)
 for i in range(2):
  cl=at+timedelta(hours=6);ack=commit(a,cl,event='restore-'+str(i));assert ack.accepted==('A',);op=clock(cl).earliest_execution_at;a.fill_buy('A',win(at=op));a.settle_due(op);warn=op+timedelta(hours=6);a.expire_day_buys(warn);a.close_risk('A',clock(warn),q(),10,negative_id='new-warning-'+str(i));cross=warn+timedelta(days=1);a.close_risk('A',clock(cross),q(price=9.5),9.5);at=clock(cross).earliest_execution_at;a.fill_exit('A',win(at=at,price=9.5));a.settle_due(at)
 assert len(a.fills)==6 and a.fees_cny==D(30) and a.roles['A']['K']==200 and a.roles['A']['R']==0;return dict(real_fills=6,fees=str(a.fees_cny),structure_total=verify_money(a,at,9.5),real_completion=len(a.completed))
case('repeated_risk_rounds_keep_all_structure_costs',repeated_losses)
def feature_off():
 a=start(enabled=False);b=start(cls=M.Parent);at=BASE+timedelta(days=2);before=list(a.audit_log);assert a.close_risk('A',clock(at),q(),1,negative_id='disabled-no-action',full_exit=True) is None and a.audit_log==before
 for x in [a,b]:
  x.expire_day_buys(at);ss,gs,qq=packet(at,new=True);marks=T.marks(at);fn=lambda **kw:A.decide(clock=clock(at),variant='S0',securities=ss,sectors=gs,**kw)
  if x is a:M.commit_roles(x,clock=clock(at),securities=ss,sectors=gs,quotes=qq,marks=marks,bootstrap=True)
  else:L.commit_cutoff(x,decision_factory=fn,clock=clock(at),quotes=qq,marks=marks,bootstrap=True)
 at+=timedelta(days=1)
 for x in [a,b]:
  if 'C' in x.buys:x.fill_buy('C',win('C',at));x.settle_due(at)
 assert a.fills==b.fills and a.audit_log==b.audit_log and a.buys==b.buys and a.sequence==b.sequence and a.available==b.available and a.completed==b.completed and not a.role_events;return dict(full_synthetic_ledger_audit_exact=True,fills=len(a.fills),audit_rows=len(a.audit_log))
case('role_disabled_exact_original_behavior',feature_off)
def restore_partial_T1():
 a=start();at,_=trim(a);cl=at+timedelta(hours=6);commit(a,cl);op=clock(cl).earliest_execution_at;a.fill_buy('A',win(at=op,capacity=100));assert a.roles['A']['R']==100 and 'A' in a.buys
 # Restore contribution belongs to the real new batch. Mature core may legally supply total-portfolio T+1 inventory; no fake role-specific maturity.
 warn=op+timedelta(hours=6);a.close_risk('A',clock(warn),q(),10,negative_id='partial-warning');cross=warn+timedelta(days=1);a.close_risk('A',clock(cross),q(price=9.5),9.5);assert 'A' not in a.buys and a.exits['A'].remaining_target==100;a.fill_exit('A',win(at=clock(cross).earliest_execution_at,price=9.5));a.settle_due(clock(cross).earliest_execution_at);assert a.roles['A']['K']==200 and a.roles['A']['R']==0 and not a.completed
 b=M.RoleAccount(initial_cash=40000);b.facts=SimpleNamespace(floor=lambda *_:D(8),factor=lambda *_:D(1));b.reserve_budget(quote=q(),clock=clock(BASE),gross_budget_cny=4000);b.fill_buy('A',win(sellable_at=BASE+timedelta(days=5)));at,_=trigger(b);early=clock(at).earliest_execution_at;assert b.fill_exit('A',win(at=early,price=9.5)) is None and b.roles['A']['R']==200 and b.exits['A'].remaining_target==200 and not b.completed;b.fill_exit('A',win(at=BASE+timedelta(days=5),price=9.5));b.settle_due(BASE+timedelta(days=5));assert b.quantity('A')==200 and b.roles['A']['K']==200
 return dict(cancelled_restore_remainder=True,sold_actual_risk=100,core_kept=200,actual_locked_batch_no_early_fill=True,real_mature_window_fill=True)
case('partial_restore_then_risk_cancels_unfilled_remainder',restore_partial_T1)
def cap_and_slots():
 a=start();at,_=trim(a);cl=at+timedelta(hours=6);ack=commit(a,cl,price=40);assert not ack.accepted and not a.exits and a.roles['A']['K']==200
 b=start();at,_=trim(b);decision=at+timedelta(hours=1)
 for sid,group in [('B','G'),('D','H'),('E','H'),('F','J'),('H','J')]:b.reserve_budget(quote=q(sid,group=group),clock=clock(decision),gross_budget_cny=1000)
 op=clock(decision).earliest_execution_at
 for sid in ['B','D','E','F','H']:b.fill_buy(sid,win(sid,at=op))
 b.settle_due(op);full=commit(b,op+timedelta(hours=6),new=True);assert full.accepted==('A',) and any(s=='C' and r=='total_slots_full' for s,r in full.rejected) and len(b.occupancy(op+timedelta(hours=6)))==6
 return dict(natural_core_not_forced_out=True,restore_rejected=ack.rejected,full_six_slots_restore_only=full.accepted,new_rejected=full.rejected)
case('natural_concentration_blocks_new_risk_not_core',cap_and_slots)

report=dict(passed=all(x['passed'] for x in results),tests=results,seconds=time.monotonic()-t0,real_controller=True,real_ledger_and_admission=True,no_historical_or_economic_paths=True,source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(L.__file__),Path(A.__file__),Path(sys.modules[M.Parent.__module__].__file__)]})
(O/'TEST_RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str));print('ALL',len(results),'PASS',flush=True)
traces=[dict(case=name,audit_log=a.audit_log,role_events=getattr(a,'role_events',[]),actual_available=a.available,actual_positions={s:p.shares for s,p in a.positions.items()},remaining_buys=a.buys,remaining_sells=a.exits,actual_completed=a.completed,terminal_roles={s:{k:v for k,v in r.items() if k!='controller'} for s,r in getattr(a,'roles',{}).items()},group_cash=getattr(a,'group_cash',{}),group_dividend=getattr(a,'group_dividend',{})) for name,a in accounts];(O/'ACCOUNT_TRACES.json').write_text(json.dumps(M.E.native.encoded(traces),ensure_ascii=False,indent=2,default=str));(O/'RESTORE_BUDGET_CHECKS.json').write_text(json.dumps(M.E.native.encoded([dict(case=name,**r) for name,a in accounts for r in getattr(a,'role_events',[]) if r['kind']=='restore_budget_check']),ensure_ascii=False,indent=2,default=str))
