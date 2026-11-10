"""Synthetic-only v2 boundary tests. Never consumes market outcomes."""
import engine as core
from pathlib import Path
D=core.D;pd=core.pd;dt=pd.Timestamp('2024-09-03');prev=pd.Timestamp('2024-09-02');resume=pd.Timestamp('2024-09-04');nextday=pd.Timestamp('2024-09-05')
source=(core.V1/'synthetic_m.py').read_text().replace('import engine as m','m=core.v1');ns={'core':core};exec(compile(source,'frozen_M_synthetics','exec'),ns)
Stub=ns['Stub'];seed=ns['seed'];attempt=ns['attempt']
def retained(s='a'):
 t=core.v1.rules.ticket_from_seed(seed(s),D(1005),dict(cash_reserve=D(100)));t['last_verified_day']='2024-09-02';return t
def setup():
 d=Stub();d.cal=pd.DatetimeIndex(['2024-08-30','2024-09-02','2024-09-03','2024-09-04','2024-09-05']);d.stock=d.stock.reindex(d.cal,fill_value=1)
 for sec in d.sector_ids:d.sectors[sec]=d.sectors[sec].reindex(d.cal).ffill()
 for s in d.ids:d.cap[s]=d.cap[s].reindex(d.cal,fill_value=100000)
 old=d.z;d.z=lambda s,when:{} if s=='a' and when==dt else old(s,when);e=core.Engine(d);e.tickets['a']=retained();return e

def run():
 inherited=ns['run']();checks=[]
 e=setup();identity=core.v1.rules.immutable_identity(e.tickets['a']);r=seed('a');r['ticket_id']=e.tickets['a']['ticket_id'];p=[r];e.economic_preflight(dt,p);assert not p and e.tickets['a']['status']=='PAUSED_NO_QUOTE' and e.tickets['a']['last_verified_day']=='2024-09-02' and e.tickets['a']['current_factor']==D(1);assert identity==core.v1.rules.immutable_identity(e.tickets['a']);e.alloc_open(dt,p);assert not e.orders and e.cash==core.v1.INITIAL;checks.append('Q0_existing_retained_pause_no_trade_cash_identity_or_factor_change')
 e.refresh_tickets(dt);assert e.tickets['a']['status']=='PAUSED_NO_QUOTE';checks.append('UNKNOWN_or_true_while_no_quote_remains_nonexecutable')
 stale=[r];e.economic_preflight(resume,stale);e.alloc_open(resume,stale);assert not stale and not e.orders and e.tickets['a']['status']=='RETAINED';pp=e.refresh_tickets(resume);assert len(pp)==1;e.economic_preflight(nextday,pp);e.alloc_open(nextday,pp);assert len(e.orders)==1 and e.orders[0]['day']=='2024-09-05' and e.tickets['a']['status']=='CONSUMED';checks.append('resume_reverify_then_CLOSE_then_next_OPEN_only')
 e=setup();e.economic_preflight(dt,[]);e.d.stock.at[dt,'a']=0;e.refresh_tickets(dt);assert e.tickets['a']['status']=='CANCELLED';checks.append('known_FALSE_original_D_cancel_while_paused')
 # Current CLOSE/HIGH/LOW/volume cannot determine current OPEN availability.
 e1=setup();e2=setup();old1=e1.d.z;old2=e2.d.z;e1.d.z=lambda s,d:dict(old1(s,d),raw_close=999,raw_high=999,raw_low=1,raw_volume=999) if s=='a' and d==dt else old1(s,d);e2.d.z=lambda s,d:dict(old2(s,d),raw_close=float('nan'),raw_high=float('nan'),raw_low=float('nan'),raw_volume=float('nan')) if s=='a' and d==dt else old2(s,d);e1.economic_preflight(dt,[]);e2.economic_preflight(dt,[]);assert e1.availability==e2.availability and e1.tickets==e2.tickets;checks.append('OPEN_pause_does_not_read_future_HLCV')
 # New SEED is not an existing retained ticket and gets no exception.
 e=setup();e.tickets={}
 try:e.economic_preflight(dt,[seed('a')]);assert False
 except core.Blocked as ex:assert 'OPEN_MISSING' in str(ex)
 checks.append('new_seed_missing_OPEN_still_hard_stop')
 # Actual holding always preserves original missing-price hard stop.
 e=setup();a=attempt('a');e.active['a']=a;e.archive[a['id']]=a
 try:e.economic_preflight(dt,[]);assert False
 except core.Blocked as ex:assert 'OPEN_MISSING' in str(ex)
 checks.append('actual_held_quote_gap_never_paused')
 e=setup();e.d.action=lambda s,d:[{'effective_date':'2024-09-03'}] if s=='a' and d==dt else [];e.economic_preflight(dt,[]);assert e.quote_gaps['a']['action_inventory']
 try:e.economic_preflight(resume,[]);assert False
 except core.Blocked as ex:assert 'GAP_UNADMITTED_EQUITY_EVENT' in str(ex)
 checks.append('gap_unreviewed_event_recorded_and_hard_checked_before_resume')
 e=setup();e.economic_preflight(dt,[]);e.d.factors['a']=D('1.1')
 try:e.economic_preflight(resume,[]);assert False
 except core.Blocked as ex:assert 'GAP_UNADMITTED_FACTOR_CHANGE' in str(ex)
 checks.append('unexplained_resumed_factor_does_not_bridge_itself')
 e=setup();e.economic_preflight(dt,[]);old=e.d.z;e.d.z=lambda s,d:dict(old(s,d),source_path='changed') if s=='a' and d==resume else old(s,d);e.economic_preflight(resume,[]);assert e.tickets['a']['status']=='CANCELLED' and not e.quote_gaps;checks.append('positive_source_change_cancels_no_source_splice')
 # All paused days' reviewed events must compose to the resumed observed factor.
 e=setup();e.d.action=lambda s,d:[{'effective_date':'2024-09-03'}] if s=='a' and d==dt else [];e.d.events={('a',dt):dict(factor_old='1',factor_new='1.1',economic_event_id_candidate='e')};e.economic_preflight(dt,[]);e.d.factors['a']=D('1.1');e.economic_preflight(resume,[]);assert e.tickets['a']['current_factor']==D('1.1') and not e.quote_gaps and not e.orders;checks.append('all_reviewed_gap_events_composed_no_entitlement_or_same_OPEN_fill')
 # Actual fill followed by missing CLOSE rolls whole day back; no held pause loophole.
 class BuyThenMissing(core.Engine):
  def close(self,d,p):
   if d==dt:
    self.ledger.append(dict(day=core.day(d),NAV=str(core.v1.INITIAL)));return [self.decorate(seed('a'),d)]
   return super().close(d,p)
 e=BuyThenMissing(Stub());e.d.days=pd.DatetimeIndex([dt,resume]);old=e.d.z;e.d.z=lambda s,d:dict(old(s,d),raw_close=float('nan')) if s=='a' and d==resume else old(s,d);e.run(False);assert not e.orders and not e.active and e.cash==core.v1.INITIAL and e.blockers and 'RAW_CLOSE_MISSING' in e.blockers[0];checks.append('OPEN_buy_then_missing_CLOSE_full_day_rollback')
 # A later failure restores pause/ticket/gap/log state before all-target diagnosis.
 class Fail(core.Engine):
  def close(self,d,p):raise core.Blocked('FORCED_AFTER_PAUSE')
 e=setup();e.__class__=Fail;e.run(False);assert e.tickets['a']['status']=='RETAINED' and not e.quote_gaps and not e.availability and e.blockers;assert e.all_blockers[0]['availability_boundary']=='EXISTING_Q0_TICKET_PAUSABLE_NO_QUOTE';checks.append('atomic_new_pause_state_rollback_then_restored_scan')
 return dict(result='PASS',inherited_count=inherited['check_count'],inherited_checks=inherited['checks'],new_count=len(checks),new_checks=checks,total=inherited['check_count']+len(checks),historical_not_run=True)
