"""Call-level M3 adversarial contracts; never reads historical outcomes."""
import engine as e
import copy,inspect,ast,json
from types import SimpleNamespace
D=e.D;Z=e.ZERO;pd=e.pd;day=pd.Timestamp('2024-09-03');nxt=pd.Timestamp('2024-09-04')
source=(e.v1.O/'synthetic_m.py').read_text().replace('import engine as m','m=e.v1');ns={'e':e};exec(compile(source,'frozen_fixture','exec'),ns);Base=ns['Stub'];attempt=ns['attempt'];seed=ns['seed'];plan=ns['plan'];cp=ns['cp']
class Stub(Base):
 @property
 def main(self):return {sec:pd.DataFrame(dict(M=[self.M[s]]*len(self.cal),E=[self.Es[s]]*len(self.cal)),index=self.cal) for s,sec in self.sid_sector.items()}
def add(e0,s,q=100,kind='SEED',confirmed=False):
 a=attempt(s,q,kind);a['confirmed_history']=confirmed;e0.active[s]=a;e0.archive[a['id']]=a
 e0.orders.append(dict(side='BUY_SEED',round_id=a['id'],lot_id=s+'|seed_original',qty=100,order_seq=len(e0.orders)+1))
 return a
def prepare(e0,requests):
 e0.plan_transfers(day,requests);return requests

def run():
 # Run the actual frozen M2 suite in a private namespace, not against changed M3 outcomes.
 source=(e.V2/'synthetic_pause.py').read_text().replace('import engine as core','core=e.m2');scope={'e':e};exec(compile(source,'frozen39','exec'),scope);prior=scope['run']();assert prior['total']==39
 checks=[]
 targets,lam,status=e.water({'A':D(70),'B':D(0)},{'A':D(1),'B':D(1)},D(100));assert targets['A']==70 and abs(targets['B']-30)<D('1e-20');checks.append('water_lower_included_once')
 assert e.water({'A':D(101)},{'A':D(1)},D(100))[2].startswith('INFEASIBLE');checks.append('infeasible_lower_no_new_reference')
 x=e.Engine(Stub());a=add(x,'a');a['confirmed_history']=True;a['add_count']=1;a['lots'].append(dict(id='bigadd',q=2000,kind='ADD',bought='2024-09-02',floor=D(5)));x.orders.append(dict(side='BUY_ADD',round_id=a['id'],lot_id='bigadd',qty=2000,order_seq=2));r=x.classify_reference(day);rows=r['rows'];assert sum(v['core_qty'] for v in rows)==200 and next(v for v in rows if v['lot_id']=='bigadd')['mobile_qty']==1900;checks.append('large_first_ADD_core_capped_at_original_SEED_shares')
 a['confirmed_history']=False;a['information_pending']={'cp':'provisional'};r=x.classify_reference(day);assert sum(v['core_qty'] for v in r['rows'])==0 and r['rows'][0]['mobile_qty']==0;checks.append('provisional_or_unconfirmed_seed_not_winner_core')
 x=e.Engine(Stub());a=add(x,'a',1000,'ADD',True);x.d.M['a']=-1;r=x.classify_reference(day);assert r['rows'][0]['mobile_qty']==0 and 'M_OR_E_UNKNOWN' in r['rows'][0]['unknown'];checks.append('UNKNOWN_full_freeze_no_false_zero')
 x.d.M['a']=1;a['lots'][0]['bought']='2024-09-04';r=x.classify_reference(day);assert r['rows'][0]['mobile_qty']==0;checks.append('T1_quantity_excluded_from_mobile_cash')
 x=e.Engine(Stub());add(x,'old');x.d.M['old']=0;x.cash=D(100);x.receivable=D(500);r=x.classify_reference(day);assert r['budget']==r['NAV']-r['reserve']-D(500)-r['outside_fixed']-r['stress'];assert x.cash==100;checks.append('receivable_and_sale_stress_only_once_not_cash')
 x=e.Engine(Stub());a=add(x,'a',1000,'ADD',True);a['exit']='I_INVALID';r=x.classify_reference(day);assert r['rows'][0]['mobile_qty']==0 and r['rows'][0]['core_qty']==0;checks.append('locked_exit_is_frozen_not_renamed_core_or_donor')
 # Reference rejects original legal seed without rewriting its dated required quantity.
 x=e.Engine(Stub());x.d.Es['a']=0;r=seed('a',E=0);prepare(x,[r]);assert r['planned_q']==100 and r['_ref_q']==0;x.alloc_open(nxt,[r]);assert not [o for o in x.orders if o.get('side','').startswith('BUY')] and x.tickets['a']['status']=='RETAINED';assert x.candidates[-1]['decision']=='MIN_LOT_CAPITAL_REJECT:reference_cap';checks.append('zero_E_reference_only_seed_retained_with_original_legal_q')
 x=e.Engine(Stub());x.d.M['a']=-1;r=seed('a',M=-1);prepare(x,[r]);x.alloc_open(nxt,[r]);assert x.tickets['a']['status']=='PAUSED' and not x.orders;checks.append('M_UNKNOWN_no_probe_fallback_preserves_ticket')
 x=e.Engine(Stub());x.d.M['a']=0;r=seed('a',M=0);prepare(x,[r]);x.alloc_open(nxt,[r]);assert x.orders[-1]['qty']==100 and not x.transfer_plan;checks.append('known_nonM_small_seed_residual_cash_preserved')
 rr=seed('a');assert e.rules.ticket_from_seed(rr,D(1005),dict(reference_cap=D(0),stock_cap=D(500),cash_reserve=D(10))) is None;assert e.rules.ticket_from_seed(rr,D(1005),dict(reference_cap=D(0),attempt_budget=D(500))) is None;checks.append('reference_plus_stock_or_attempt_never_retained')
 # Call-level multi-cap accounting at OPEN, not helper-only.
 x=e.Engine(Stub());x.d.Es['a']=0;r=seed('a',E=0);r['budget']=D(500);prepare(x,[r]);x.alloc_open(nxt,[r]);assert 'a' not in x.live_tickets() and set(x.candidates[-1]['violated_caps'])=={'attempt_budget','reference_cap'};checks.append('OPEN_multiple_caps_listed_and_not_retained')
 # Seed allocation can be denied by reference even with abundant real cash.
 x=e.Engine(Stub());x.d.Es['a']=.00001;r=seed('a');prepare(x,[r]);assert r['_ref_q']==0;x.alloc_open(nxt,[r]);assert x.tickets['a']['first_reject_caps']==['reference_cap'];checks.append('positive_tiny_T_insufficient_hand_retains')
 # Explicit legal close quantities stay zero even if others fail or reference expands at OPEN.
 x=e.Engine(Stub());r1=seed('a');r2=seed('b');prepare(x,[r1,r2]);r2['_ref_q']=0;x.reference['T']['B']=D(1000000);x.reference['envelope']['B']=D(1000000);x.d.prices['a']=D(4);x.alloc_open(nxt,[r1,r2]);assert not x.orders;checks.append('OPEN_no_promote_close_zero_when_other_request_fails')
 # M reference queue uses gaps, updates reservations and cannot overspend sector envelope.
 x=e.Engine(Stub());x.d.sid_sector['b']='A';x.d.sector_ids=['A','OLD','X'];x.d.Es['a']=1;x.d.Es['b']=1;r1=seed('a');r2=seed('b');r3=seed('x');prepare(x,[r1,r2,r3]);ordered=x.request_key_groups([r1,r2,r3]);assert ordered[0]['sid']=='a' and ordered[1]['sid']=='x';x.alloc_open(nxt,[r1,r2,r3]);assert all(v>=0 for v in x._ref_spent.values());checks.append('each_reservation_updates_gap_not_whole_sector_first')
 # Large uncapped ADD still has real CP and positive net, while core protection is separate.
 x=e.Engine(Stub());a=add(x,'a');a['cp']=cp();a['plan']=plan('a',2000);x.info_close(a,day,a['cp'],D(95));prepare(x,[]);before=len(x.orders);x.alloc_open(nxt,[]);new=x.orders[before:];assert new and new[0]['qty']>100 and new[0]['qty']<=2000 and a['cp'] is None;assert x.floor_risk[-1]['not_profit_covered'];checks.append('uncapped_ADD_actual_size_and_principal_risk_CP_once')
 # A one-request funding gap does not trigger sales when that receiver fails at OPEN.
 x=e.Engine(Stub());a=add(x,'old',10000,'ADD',True);x.d.Es['old']=.001;x.cash=D(100);r=seed('a');prepare(x,[r]);assert x.transfer_plan;x.d.prices['a']=D(4);before=len(x.orders);x.alloc_open(nxt,[r]);assert len(x.orders)==before and x.transfers[-2]['event']=='TRANSFER_CASH' and D(x.transfers[-2]['M_desired_cost'])==0;checks.append('gap_failure_cancels_voluntary_donor_no_floor_replenish_only')
 # Sell net proceeds, below-floor cash deficit and donor floor remain exact.
 x=e.Engine(Stub());a=add(x,'old',10000,'ADD',True);x.d.Es['old']=.001;x.cash=D(100);r=seed('a');prepare(x,[r]);pl=copy.deepcopy(x.transfer_plan);before=len(x.orders);x.alloc_open(nxt,[r]);sells=[o for o in x.orders[before:] if o['side'].startswith('SELL')];assert sells and all(o['qty']<=next(p['max_q'] for p in pl if p['lot_id'] in o['lots']) for o in sells);tf=next(t for t in reversed(x.transfers) if t['event']=='TRANSFER_CASH');assert D(tf['net_cash_released'])==sum((D(o['cash_delta']) for o in sells),Z);assert D(tf['initial_gap'])>D(tf['M_desired_cost']);assert x.quantity(a)>=100;checks.append('cash_shortfall_net_fees_frozen_max_and_seed_equivalent_core')
 # No actual legal request: no voluntary selling regardless of tiny cash or attractive T.
 x=e.Engine(Stub());add(x,'old',10000,'ADD',True);x.d.Es['old']=.001;x.cash=D(1);prepare(x,[]);assert not x.transfer_plan;checks.append('no_real_request_no_donor_sale')
 x=e.Engine(Stub());a=add(x,'old',10000,'ADD',True);b=add(x,'x',2000,'ADD',True);a['lots'][0]['bought']='2024-09-02';b['lots'][0]['bought']='2024-08-30';x.d.M['old']=x.d.M['x']=0;x.d.W['old']=x.d.W['x']=True;x.cash=D(1);prepare(x,[seed('a')]);assert x.transfer_plan[0]['sid']=='x';checks.append('original_W_donors_oldest_first_not_surplus_sorted')
 # Atomic rollback includes all new accounting state/logs and uses restored targets.
 class Fail(e.Engine):
  def economic_preflight(self,*a):pass
  def accrue(self,*a):pass
  def exit_open(self,*a):pass
  def alloc_open(self,*a):self.reference={'corrupt':1};self._ref_spent={'x':D(99)};self.capital_lots.append({'bad':1});self.reference_log.append({'bad':1});self.reference_requests.append({'bad':1});self.cash-=D(99)
  def close(self,*a):raise e.Blocked('FORCED_REFERENCE_ROLLBACK')
  def scan_restored_targets(self,*a):return []
 x=Fail(Stub()).run(False);assert x.cash==e.INITIAL and not x.reference and not x._ref_spent and not x.capital_lots and not x.reference_requests and not x.reference_log;checks.append('all_reference_state_and_logs_atomic_rollback')
 # Dated sell_step 1 continues to use minimum net cover.
 x=e.Engine(Stub());x.d.getmeta=lambda *a:(e.b.QuantityRule('star',200,1,1,True,1),None,None);assert x.sell_quantity('a',nxt,D(10),D(2006),500,600)==202;checks.append('dated_sell_step_one_no_100_share_oversale')
 return dict(result='PASS',inherited=prior,new_count=len(checks),new_checks=checks,total=39+len(checks),historical_outcomes_not_used=True)
if __name__=='__main__':
 out=run();e.save(e.O/'SYNTHETIC_QA.json',out);print(json.dumps(out,default=str))
