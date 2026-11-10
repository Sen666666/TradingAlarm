from types import SimpleNamespace
import copy,json
import engine as m
D=m.D;pd=m.pd;ZERO=m.ZERO;INIT=m.INITIAL;dt=pd.Timestamp('2024-09-03');prev=pd.Timestamp('2024-09-02');origin=('s','p','0')
class Stub:
 def __init__(self):
  self.ids=['a','b','old','x'];self.names={s:s for s in self.ids};self.sid_sector={'a':'A','b':'B','old':'OLD','x':'X'};self.sector_ids=['A','B','OLD','X'];self.events={};self.hashes={};self.excluded=[];self.admission=[];self.cal=pd.DatetimeIndex(['2024-08-30','2024-09-02','2024-09-03','2024-09-04']);self.days=self.cal[2:3];self.prices={s:D(10) for s in self.ids};self.states={s:1 for s in self.ids};self.M={s:1 for s in self.ids};self.Es={s:1.0 for s in self.ids};self.W={s:False for s in self.ids};self.factors={s:D(1) for s in self.ids};self.cap={s:pd.Series(100000,index=self.cal) for s in self.ids};self.stock=pd.DataFrame(1,index=self.cal,columns=self.ids);self.sectors={sec:pd.DataFrame(dict(state=1,N=3,K=3,n=3,U=0,paired_K=3,entered3=0,left3=0,diff=0,strength=False),index=self.cal) for sec in self.sector_ids}
 def z(self,s,d):
  p=float(self.prices[s]);return dict(raw_open=p,raw_close=p,adjustment_factor=float(self.factors[s]),source_kind='s',source_path='p',segment_id=0,observed_bar=True,price_eligible=True,volume_eligible=True,source_invalid=False,synthetic_event_bar=False)
 def f(self,s,d):return dict(i_target=True,i_floor=5)
 def c(self,s,d):return dict(receipt=False,candidate=None)
 def m(self,s,d):return SimpleNamespace(M=self.M[s],E=self.Es[s],M_streak=2,W=self.W[s])
 def fee(self,s,d,q,p,side):return D(5) if q else ZERO
 def getmeta(self,*args):return (m.b.QuantityRule('x',100,100,100,True,1),None,None)
 def size(self,s,d,p,budget,cap):return max(0,min(int(cap)//100,int((budget-D(5))/p)//100))*100
 def action(self,s,d):return []
def attempt(s,q=100,kind='SEED'):
 return dict(id=s+'|1',sid=s,signal_day='2024-09-02',birth_type='A',lots=[dict(id=s+'|lot',q=q,kind=kind,bought='2024-09-02',floor=D(5))],ifloor=D(5),factor=D(1),origin=origin,exit=None,plan=None,cp=None,cashflow=D(-900),dividend=ZERO,fees=D(5),nav0=INIT,add_count=0,seed_day='2024-09-02',confirmed_history=False)
def cp():return dict(id='CP1',date='2024-09-02',floor=D(5),origin=origin,consumed=False,invalid=False)
def seed(s,M=1,E=1):return dict(kind='SEED',sid=s,birth_type='A',signal_day='2024-09-02',plan_day='2024-09-02',budget=D(24000),planned_q=100,capacity=100,ifloor=D(5),factor=D(1),origin=origin,nav0=INIT,M=M,E=D(E),M_streak=2)
def plan(s,q=100):return dict(kind='ADD',sid=s,signal_day='2024-09-02',plan_day='2024-09-02',cp_date='2024-09-02',cp_id='CP1',budget=D(24000),planned_q=q,capacity=100000,close_net='95',origin=origin,factor=D(1),M=1,E=D(1),M_streak=2)
def setup(s='b',q=100):
 e=m.Engine(Stub());a=attempt(s,q);a['cp']=cp();e.active[s]=a;e.archive[a['id']]=a;return e,a
def proof(e,a):e.info_close(a,prev,a['cp'],D(95))
def run():
 checks=[]
 assert m.tri_or(1,-1)==1 and m.tri_and(0,-1)==0 and m.tri_or(0,-1)==-1;checks.append('three_valued_logic')
 # Baseline primitive and complete baseline joint synthetic suite remain valid.
 m.b.synthetic();source=(m.BASE/'synthetic_joint.py').read_text().replace('from engine import','from frozen_v9 import');ns={};exec(compile(source,'baseline_synthetic_joint','exec'),ns);checks+=['baseline_'+x for x in ns['run']()]
 e,a=setup();a['plan']=plan('b',2000);proof(e,a);e.alloc_open(dt,[]);assert e.orders[0]['qty']==100 and a['confirmed_history'] and a['add_count']==1 and a['cp'] is None;checks.append('OPEN_ADD_quantity_not_above_actual_holding_consumes_CP_once')
 # A gap can only shrink original quantity, and a fee-short legal size never consumes CP.
 e,a=setup(q=200);e.d.prices['b']=D(100);a['cashflow']=D(-900);r=plan('b',200);r['budget']=D(15000);a['plan']=r;proof(e,a);e.alloc_open(dt,[]);assert e.orders and e.orders[0]['qty']==100;checks.append('OPEN_gap_shrinks_CLOSE_plan')
 e,a=setup();e.cash=D(100);a['plan']=plan('b');proof(e,a);e.alloc_open(dt,[]);assert not e.orders and a['confirmed_history'] and not a['cp']['consumed'];checks.append('information_mature_without_funding_CP_unconsumed')
 e,a=setup();a['plan']=plan('b');proof(e,a);a['exit']='TRIAL_SECTOR_FALSE';e.exit_open(dt);e.alloc_open(dt,[]);assert not e.active and not a['confirmed_history'] and e.confirmations[-1]['decision']=='PROVISIONAL_WITHDRAWN';checks.append('mandatory_exit_before_confirmation_no_resurrection')
 # Two M sectors ranked E, same industry ADD before seed, non-M seeds last.
 e,a=setup();rr=[seed('a',1,5),plan('b'),seed('x',0,100)];assert [r['sid'] for r in e.request_key_groups(rr)]==['a','b','x'];checks.append('M_strength_order_nonM_last')
 # Cash-only rejection retains original identity, multicaps do not.
 e=m.Engine(Stub());old=attempt('old',107800);e.active['old']=old;e.archive[old['id']]=old;e.cash=D(120000);e.alloc_open(dt,[seed('a')]);t=e.live_tickets()['a'];ident=m.rules.immutable_identity(t);assert t['nav0']==INIT and t['signal_day']=='2024-09-02'
 e.economic_preflight(pd.Timestamp('2024-09-04'),[]);e.d.stock.at[pd.Timestamp('2024-09-04'),'a']=-1;e.refresh_tickets(pd.Timestamp('2024-09-04'));assert t['status']=='PAUSED' and ident==m.rules.immutable_identity(t);e.d.stock.at[pd.Timestamp('2024-09-04'),'a']=0;e.refresh_tickets(pd.Timestamp('2024-09-04'));assert t['status']=='CANCELLED';checks.append('retained_identity_UNKNOWN_pause_FALSE_cancel')
 rr=seed('a');rr['budget']=D(500);assert m.rules.ticket_from_seed(rr,D(1005),dict(cash_reserve=D(100),attempt_budget=D(500))) is None;checks.append('multicap_rejection_not_retained')
 # Missing bridge for paused retained ticket is an account blocker.
 t=m.rules.ticket_from_seed(seed('a'),D(1005),dict(cash_reserve=D(100)));t['status']='PAUSED';e=m.Engine(Stub());e.tickets['a']=t;e.d.factors['a']=D('1.1')
 try:e.economic_preflight(dt,[]);assert False
 except m.Blocked:pass
 checks.append('paused_retained_same_source_factor_change_blocks')
 # Deficit includes existing cash-floor shortfall; net, not gross, sale proceeds fund buys.
 e=m.Engine(Stub());a=attempt('old',1000,kind='ADD');a['lots'].append(dict(id='core',q=100,kind='SEED',bought='2024-09-02',floor=D(5)));a['add_count']=1;a['confirmed_history']=True;e.active['old']=a;e.archive[a['id']]=a;e.cash=D(1190);e.d.M['old']=0;e.d.W['old']=True;e.transfer_plan=[dict(signal_day='2024-09-02',sid='old',round_id=a['id'],lot_id='old|lot',max_q=100,reason='WEAK_SECTOR_ADD_LAYER',rank=1)]
 nav=D(12000);sv={'old':D(11000)};r=seed('a');e.execute_transfers(dt,[r],nav,sv);tr=e.transfers[-1];assert D(tr['initial_gap'])==D('1015.5000') and D(tr['net_cash_released'])==D('994.5000');assert e.quantity(a)==1000 and a['lots'][-1]['q']==100;checks.append('cash_below_floor_deficit_and_net_fee_cash_and_core_preserved')
 # Receiver fails at OPEN: frozen donors are not sold; quantity never exceeds frozen limit.
 e,a=setup('old');e.d.prices['a']=D(4);e.transfer_plan=[dict(signal_day='2024-09-02',sid='old',round_id=a['id'],lot_id='old|lot',max_q=100,reason='UNCONFIRMED_NON_MAINLINE_SEED',rank=1)];e.cash=D(1);e.execute_transfers(dt,[seed('a')],D(1000),{'old':D(1000)});assert not e.orders and e.transfers[-1]['initial_gap']=='0';checks.append('receiver_gap_failure_zero_donor_sale_no_cash_floor_only_sale')
 # UNKNOWN cannot become donor even while cash is insufficient.
 e,a=setup('old');a['cp']=None;e.d.M['old']=-1;e.d.stock.at[prev,'old']=0;e.cash=D(1);e.plan_transfers(prev,[seed('a')]);assert not e.transfer_plan;checks.append('UNKNOWN_never_donor')
 # Close ADD quantity gate and information proof exist independently, no minimum upsize.
 class CloseTest(m.Engine):
  def attribute(self,*args):pass
  def plan_transfers(self,*args):self.transfer_plan=[]
 e=CloseTest(Stub());a=attempt('b',100);a['cp']=cp();e.active['b']=a;e.archive[a['id']]=a;e.close(dt,prev);assert a['plan']['planned_q']==100 and a['information_pending'];checks.append('CLOSE_ADD_actual_share_bound_and_information_separate')
 # Uncertifiable day rolls back actual partial cash/orders, tickets, proofs and donor state.
 class Fail(m.Engine):
  def economic_preflight(self,d,p):pass
  def accrue(self,d):pass
  def exit_open(self,d):pass
  def alloc_open(self,d,p):self.cash-=D(123);self.orders.append(dict(day=m.day(d),side='BUY_SEED'));self.tickets['bad']={'x':1};self.confirmations.append({'bad':True});self.transfer_plan=[{'bad':True}]
  def close(self,d,p):raise m.Blocked('forced test')
  def scan_targets(self,*args):return []
 e=Fail(Stub()).run(False);assert e.cash==INIT and not e.orders and not e.tickets and not e.confirmations and not e.transfer_plan and e.uncertified_day['partial_orders'];checks.append('atomic_all_new_state_rollback')
 # Dated sell step 1 must not over-sell by hardcoded board lot.
 e=m.Engine(Stub());e.d.getmeta=lambda *a:(m.b.QuantityRule('star',200,1,1,True,1),None,None)
 assert e.sell_quantity('a',dt,D(10),D(2006),500,600)==202
 checks.append('sell_step_one_minimum_fee_cover_quantity')
 # Paused tickets must still have an executable OPEN source row.
 e=m.Engine(Stub());t=m.rules.ticket_from_seed(seed('a'),D(1005),dict(cash_reserve=D(100)));t['status']='PAUSED';e.tickets['a']=t;original=e.d.z
 e.d.z=lambda s,d:dict(original(s,d),raw_open=float('nan'))
 try:e.economic_preflight(dt,[]);assert False
 except m.Blocked as ex:assert 'OPEN_MISSING' in str(ex)
 checks.append('paused_ticket_missing_OPEN_blocks')
 # A dividend payable at this CLOSE is real cash before the transfer plan.
 class PayTest(m.Engine):
  def attribute(self,*args):pass
  def refresh_tickets(self,d):return [self.decorate(seed('a'),d)]
 e=PayTest(Stub());a=attempt('old',12000);a['cp']=None;e.active['old']=a;e.archive[a['id']]=a;e.cash=D(100);e.receivable=D(15000);e.d.M['old']=0;e.d.stock.at[dt,'old']=0
 e.d.events={('old',prev):dict(record_date='2024-08-30',pay_date='2024-09-03')};e.claims={('old',prev):dict(amount=D(15000),round=a['id'],paid=False)}
 e.close(dt,prev);r=e.transfers[-1];assert e.cash==D(15100) and D(r['M_desired_cost'])>0 and r['initial_gap']=='0' and not e.transfer_plan
 checks.append('PAY_CLOSE_before_transfer_plan_avoids_unnecessary_donor')
 return dict(result='PASS',checks=checks,check_count=len(checks),historical_account_not_run=True)
