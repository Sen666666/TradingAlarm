import wire as w
from types import SimpleNamespace
from datetime import timedelta
O=w.O;D=w.D;T=w.load('budget_full_real_ledger_tests',w.RR/'rs-h1-execution-20261025/code/test_sector_account.py');A=w.K.A;L=w.K.L
root=O/'synthetic-v3';root.mkdir(exist_ok=False);(root/'execution-rules-v2.json').write_bytes((w.RR/'pvr-act-comparison-20261027/execution-rules-v2.json').read_bytes());R,E,_,_,_=w.setup('TECH',root,False);C=w.account_class(E.Account,lambda *_:dict(structure_id='A|epoch=fixed',source_segment=0));base=T.T;res=[]
def mk(on=True,delay=0):
 a=C(initial_cash=100000,delay_events=delay);a.loss_b=D('.1') if on else None;a.mode='I';a.current_nav=D(100000);a.facts=SimpleNamespace(floor=lambda *_:D(1),factor=lambda *_:D(1));state=dict(price=D(10),known=True)
 class Market:
  rules={'security_metadata':{}}
  raw={'A':w.pd.DataFrame({'observed_bar':[True]*12,'valid_price':[True]*12},index=w.pd.date_range(base.date(),periods=12))}
  def latest_mark(self,s,at):return T.marks(at if state['known'] else at-timedelta(days=1),price=state['price'])[s]
  def fees(self,*_):return T.MINIMUM
  def quote(self,s,at):return T.quote(price=state['price'],fees=T.MINIMUM)
 a.market=Market();return a,state

def cl(t):return A.Clock(t,t+timedelta(days=1),t.date())
def stocks(t,fresh=True,up=True):
 f=lambda v:A.Fact(v,t,t,observed_at=t);s=A.Security('A',f('A'),f('G'),f(True),f(fresh),f(20e9),f(up),A.Rank(80,t,t));g=A.Sector('G',f(True),A.Rank(70,t,t));return (s,),(g,)
def admission(a,t,previous=(),fresh=True,completed=(),up=True):
 ss,gg=stocks(t,fresh,up);ss2=w.process(a,ss,cl(t),A.Fact);assert ss2 is ss
 factory=lambda **kw:A.decide(clock=cl(t),variant='S0',securities=ss2,sectors=gg,**kw)
 marks={s:T.marks(t,price=state_for[id(a)]['price'],sid=s)[s] for s in a.positions};ack=L.commit_cutoff(a,decision_factory=factory,clock=cl(t),quotes={'A':T.quote(price=state_for[id(a)]['price'],fees=T.MINIMUM)},marks=marks,previous=previous,bootstrap=not previous,completed_exits=completed);a.daily_delay_credit.clear();return ack
state_for={}
def started(on=True,delay=0):
 a,s=mk(on,delay);state_for[id(a)]=s;ok,oid=a.reserve_budget(quote=T.quote(fees=T.MINIMUM),clock=cl(base),gross_budget_cny=D(10000));assert ok;op=cl(base).earliest_execution_at;f=a.fill_buy('A',T.window(at=op,fees=T.MINIMUM,eid='initial',cash_due_at=op));
 if not f:
  a.expire_day_buys(op+timedelta(hours=6));ok,_=a.reserve_budget(quote=T.quote(fees=T.MINIMUM),clock=cl(op+timedelta(hours=6)),gross_budget_cny=D(10000));op=cl(op+timedelta(hours=6)).earliest_execution_at;f=a.fill_buy('A',T.window(at=op,fees=T.MINIMUM,eid='initial-delayed',cash_due_at=op))
 assert f;a.settle_due(op);return a,s,op

def run(name,f):f();res.append(dict(name=name,passed=True));print(name,'PASS',flush=True)
def cost_reset():
 a,s,op=started();c=a.loss_states['A'];assert c['K']==sum((f.gross_cny+f.fees_cny for f in a.fills),D(0));s['price']=D(8);ss,_=stocks(op+timedelta(hours=6));w.process(a,ss,cl(op+timedelta(hours=6)),A.Fact);assert 'A' in a.exits and len([x for x in a.audit_log if x['kind']=='loss_budget_request'])==1;s['price']=D(12);w.process(a,ss,cl(op+timedelta(hours=7)),A.Fact);assert 'A' in a.exits
run('actual_cost_only_and_budget_exit_stays_locked_after_profit_rebound',cost_reset)
def reentry():
 a,s,op=started();t=op+timedelta(hours=6);ack=admission(a,t);s['price']=D(8);t+=timedelta(days=1);ack=admission(a,t,ack.memories);ex=cl(t).earliest_execution_at;f=a.fill_exit('A',T.window(at=ex,price=8,fees=T.MINIMUM,cash_due_at=ex,eid='budget-exit'));assert f and 'A' not in a.loss_states;a.settle_due(ex);done=tuple(a.completed);t=ex+timedelta(hours=6);ack=admission(a,t,ack.memories,fresh=False,completed=done);assert not a.buys;t+=timedelta(days=1);ack=admission(a,t,ack.memories,fresh=True);assert 'A' in a.buys and a.buys['A'].purpose=='initial';op2=cl(t).earliest_execution_at;f=a.fill_buy('A',T.window(at=op2,price=9,fees=T.MINIMUM,cash_due_at=op2,eid='reentry'));assert f and a.loss_states['A']['K']==f.gross_cny+f.fees_cny and a.loss_groups['A|epoch=fixed']['attempts']==2
run('full_flat_completion_fresh_I_original_admission_new_initial_no_priority',reentry)
def same_day():
 a,s,op=started();t=op+timedelta(hours=6);s['price']=D(8);ack=admission(a,t);ex=cl(t).earliest_execution_at;a.fill_exit('A',T.window(at=ex,price=8,fees=T.MINIMUM,cash_due_at=ex,eid='same-day-exit'));a.settle_due(ex);ack=admission(a,ex+timedelta(hours=6),ack.memories,completed=tuple(a.completed),fresh=True);assert 'A' in a.buys and a.buys['A'].earliest_at>ex
run('open_flat_close_fresh_next_legal_initial_no_forced_extra_day',same_day)
def priority():
 a,s,op=started();s['price']=D(7);t=op+timedelta(hours=6);ack=admission(a,t,up=False);assert a.loss_states['A']['controller'].reason=='original';assert not any(x['kind']=='loss_budget_request' for x in a.audit_log)
run('original_structure_ACT_exit_priority_no_duplicate',priority)
def unknown():
 a,s,op=started();s['known']=False;s['price']=D(7);ss,_=stocks(op+timedelta(hours=6));w.process(a,ss,cl(op+timedelta(hours=6)),A.Fact);assert not a.exits and not a.loss_states['A']['controller'].locked
run('unknown_mark_does_not_create_budget_signal',unknown)
def off():
 a,s,op=started(False);assert not a.loss_states;ss,_=stocks(op+timedelta(hours=6));s['price']=D(1);before=list(a.audit_log);assert w.process(a,ss,cl(op+timedelta(hours=6)),A.Fact) is ss and a.audit_log==before
run('off_no_state_or_events_or_signal_mutation',off)
def partial():
 a,state=mk();state_for[id(a)]=state;ok,oid=a.reserve_budget(quote=T.quote(fees=T.MINIMUM),clock=cl(base),gross_budget_cny=D(10000));op=cl(base).earliest_execution_at;f=a.fill_buy('A',T.window(at=op,fees=T.MINIMUM,capacity=100,eid='partial1',cash_due_at=op));K=a.loss_states['A']['K'];cid=a.loss_states['A']['cycle'];f2=a.fill_buy('A',T.window(at=op+timedelta(hours=1),fees=T.MINIMUM,capacity=100,eid='partial2',cash_due_at=op+timedelta(hours=1)));assert a.loss_states['A']['cycle']==cid and a.loss_states['A']['K']==K+f2.gross_cny+f2.fees_cny
run('partial_actual_fill_adds_cost_same_cycle_no_phantom_reset',partial)
def actions():
 a,s,op=started();K=a.loss_states['A']['K'];q=a.quantity('A');t=op+timedelta(hours=6);a.accrue_dividend(event_id='div',sid='A',currency='CNY',net_local=D(q),ex_at=t,paid_at=None,source_id='declared',entitlement_basis='actual');s['price']=D(9);ss,_=stocks(t);w.process(a,ss,cl(t),A.Fact);assert not a.exits;a.split(event_id='split',sid='A',ratio=D(2),at=t,new_shares_sellable_at=t);s['price']=D('4.5');ss,_=stocks(t+timedelta(hours=1));w.process(a,ss,cl(t+timedelta(hours=1)),A.Fact);assert not a.exits and a.loss_states['A']['K']==K and a.quantity('A')==2*q
run('raw_price_shares_and_declared_dividend_no_double_adjustment',actions)
def delay_initial():
 from dataclasses import replace
 a,s,op=started();t=op+timedelta(hours=6);s['price']=D(8);ack=admission(a,t);ex=cl(t).earliest_execution_at;a.fill_exit('A',T.window(at=ex,price=8,fees=T.MINIMUM,cash_due_at=ex,eid='flat-before-delay'));a.settle_due(ex);a.delay_events=1;t=ex+timedelta(hours=6);ack=admission(a,t,ack.memories,completed=tuple(a.completed));bt=cl(t).earliest_execution_at;assert a.fill_buy('A',T.window(at=bt,price=8,fees=T.MINIMUM,eid='real-wait',cash_due_at=bt)) is None;ct=bt+timedelta(hours=6);expired=a.expire_day_buys(ct);memory=tuple(replace(m,waiting=True,created_at=ct,origin='expired_unfilled_recompetition') if m.security_id in expired else m for m in ack.memories);ack=admission(a,ct,memory,fresh=True);assert a.buys['A'].delay_remaining==0 and a.buys['A'].purpose=='initial';f=a.fill_buy('A',T.window(at=cl(ct).earliest_execution_at,price=8,fees=T.MINIMUM,eid='initial-after-new-fresh',cash_due_at=cl(ct).earliest_execution_at));assert f and a.loss_groups['A|epoch=fixed']['attempts']==2
run('flat_original_initial_delay_credit_with_new_fresh_not_partial_patch',delay_initial)
w.K.save(O/'SYNTHETIC.json',dict(passed=True,tests=res,real_original_account_and_ledger_and_admission=True,partial_role_patch_used=False));print('PASS',len(res))
