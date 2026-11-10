import unittest,json,copy,subprocess
from datetime import datetime
from dataclasses import asdict
from projector import *
import projector as P
AT='2025-07-03 15:10:00+08:00';END='2025-07-04 15:10:00+08:00'
MAIN=asdict(N.quantity(datetime.fromisoformat(AT),False));STAR=asdict(N.quantity(datetime.fromisoformat(AT),True));FEES=asdict(N.fees(datetime.fromisoformat(AT),False))
def lot(sid='OLD',q=5000,mark='100',floor='88.4',purpose='G',pool='confirmed',role='mobile',sector='OLDSEC',risk=None,locked=False):
 m=D(mark);r=D(q)*max(Z,m-D(floor)) if risk is None else D(risk)
 return dict(id=sid,sid=sid,sector=sector,qty=q,mark=m,floor=D(floor),capital=D(q)*m,risk=r,pool=pool,role=role,purpose=purpose,
   locked_capital=D(q)*m if locked else Z,donor_eligible=not locked,holding_S=True,sellable_qty=q,quantity=copy.deepcopy(MAIN),fees=copy.deepcopy(FEES))
def state(lots=(),cash='500000',assets=(),nd=None):
 nav=D(cash)+sum((num(z,'capital') for z in lots),Z)+sum((num(a,'amount') for a in assets if a['kind']=='sale_receivable'),Z)
 return dict(at=AT,deadline=END,decision_nav=nav if nd is None else D(nd),nav=nav,available=D(cash),pending_fees=Z,rows=copy.deepcopy(list(lots)),lots=copy.deepcopy(list(lots)),assets=copy.deepcopy(list(assets)),targets={z['sector']:nav*D('.8') for z in lots})
def demand(sid='NEW',q=500,mark='100',floor='90',quantity=MAIN,sector=None):
 return dict(sid=sid,sector=sector or sid,priority=(0,sid),max_q=q,mark=D(mark),floor=D(floor),role='mobile',pool='confirmed',use='S',eligible=True,receipt_valid=True,
   receipt_id='receipt-'+sid,known_at=AT,deadline=END,industry_target=D('800000'),quantity=copy.deepcopy(quantity),fees=copy.deepcopy(FEES))
def simple_exit_state():
 z=lot(q=800,mark='1',floor='1.1',risk='5',locked=True)
 asset=dict(id='EXIT|old',kind='pending_exit',amount=D(100)*(ONE-SLIP)-fee(100,ONE-SLIP,FEES,'sell'),due_at='2025-07-04 09:30:00+08:00',parts=[dict(layer='OLD',q=100,risk_release=D(5))],cancel_pending=False)
 return state([z],cash='200',assets=[asset]),[demand('A',100,'.9','.89'),demand('B',100,'.9','.89')]

# Explicit fixture provider for inherited JF1 cases; production never fills missing fields.
TRUSTED={}
def bound(s,ds):
 s=copy.deepcopy(s);ds=copy.deepcopy(ds)
 s.update(account_id='explicit-synthetic-fixture',target_id='same-industry-source-context',receipt_registry={},analysis_only=False)
 s.setdefault('other_saved_goal_need',0)
 for d in ds:
  d.setdefault('price_known_at',AT)
  d.setdefault('receipt_binding',dict(event_id=d['receipt_id'],sid=d['sid'],source='explicit-fixture-not-native',source_binding=digest('fixture-source'),payload_sha256=digest(d['receipt_id']),start='2025-07-01 15:10:00+08:00',end=AT,confirmed=AT,deadline=d['deadline'],structure=['fixture',1],scale='21',market_context=d['sector']+'|fixture-context'))
  s['receipt_registry'][d['receipt_id']]=digest(d['receipt_binding'])
 return s,ds
def solve(s,ds):
 ss,dd=bound(s,ds);c=P.solve(ss,dd);TRUSTED[c['snapshot_sha256']]=(ss,dd);return c
def preview(s,ds,Q):
 ss,dd=bound(s,ds);return P.preview(ss,dd,Q)
def accept_fixture(b,c):
 ss,dd=TRUSTED[c['snapshot_sha256']];b.accept(c,c['target_id'],snapshot=ss,demands=dd,actual_commitments=b.commitments())
def load_fixture(b):return CertificateBook.loads(b.dumps(),trusted_inputs=TRUSTED,actual_commitments=b.commitments())
def rehash_book(r):r['book_id']=digest({k:v for k,v in r.items() if k!='book_id'});return json.dumps(r)

class Tests(unittest.TestCase):
 def test_zero_no_liquidation(self):
  s=state([lot()]);d=demand();d['eligible']=False;r=solve(s,[d]);self.assertEqual(r['Q'],{'NEW':0});self.assertFalse(r['donors']['rows'])
 def test_partial_feasible_not_full_target(self):
  s=state([lot()]);d=demand();r=solve(s,[d]);self.assertEqual(r['Q']['NEW'],100);self.assertFalse(r['donors']['rows']);self.assertFalse(preview(s,[d],{'NEW':500})['validation']['ok'])
 def test_all_feasible(self):
  s=state([],cash='1000000');ds=[demand('A',100,'10','9'),demand('B',200,'10','9')];r=solve(s,ds);self.assertEqual(r['Q'],{'A':100,'B':200});self.assertFalse(r['donors']['rows'])
 def test_all_feasible_with_required_original_donor(self):
  s=state([lot(q=1100,mark='8',floor='7.99')],cash='1200');d=demand(q=200,mark='1',floor='.98');r=solve(s,[d])
  self.assertEqual(r['Q']['NEW'],200);self.assertEqual(r['donors']['rows'][0]['q'],100)
  self.assertEqual(r['validation']['actual_cash_released'],0)
 def test_failed_later_candidate_cannot_erase_earlier_legal_donor(self):
  s=state([lot(q=1100,mark='8',floor='7.45')],cash='1200');a=demand('A',200,'1','.98');b=demand('B',100,'1','.98',sector='OLDSEC')
  before=digest(s);r=solve(s,[a,b]);self.assertEqual(r['Q'],{'A':200,'B':0});self.assertEqual(r['donors']['rows'][0]['q'],100);self.assertEqual(digest(s),before)
 def test_genuine_nonmonotone_quantity_min_fails_larger_passes(self):
  s=state([lot(q=1100,mark='8',floor='7.45')],cash='1200');d=demand(q=200,mark='1',floor='.98')
  low=preview(s,[d],{'NEW':100});high=preview(s,[d],{'NEW':200})
  self.assertFalse(low['validation']['ok']);self.assertTrue(high['validation']['ok']);self.assertFalse(low['donors']['rows']);self.assertTrue(high['donors']['rows'])
  self.assertEqual(solve(s,[d])['Q']['NEW'],200)
 def test_star_each_new_order_min200_even_with_holdings(self):
  for existing in (False,True):
   s=state([lot('NEW',q=50,mark='10',floor='9')] if existing else [],cash='1000000');d=demand(q=199,mark='10',floor='9',quantity=STAR)
   self.assertEqual(solve(s,[d])['Q']['NEW'],0)
  d=demand(q=205,mark='10',floor='9',quantity=STAR);self.assertEqual(list(qty_options(d)),[205,204,203,202,201,200,0])
 def test_min_fee_native_incremental_not_paid_twice(self):
  sched=schedule(FEES);p=D('10');paid=sched.incremental('sell',D(100)*p,{}, {},1,shares=100);accrued=sched.rate_accrual('sell',D(100)*p,1,shares=100)
  second=fee(100,p,FEES,'sell',paid,accrued);independent=fee(100,p,FEES,'sell');self.assertEqual(independent-second,D(5))
 def test_unfilled_exit_lock_not_current_cash_or_risk(self):
  s,ds=simple_exit_state();before=digest(s);r=solve(s,ds)
  self.assertTrue(r['validation']['conditional']);self.assertEqual(r['validation']['actual_risk_released'],0);self.assertEqual(r['validation']['actual_cash_released'],0)
  self.assertEqual(s['rows'][0]['risk'],5);self.assertEqual(s['available'],200);self.assertEqual(digest(s),before)
 def test_pending_cover_not_funded_twice(self):
  s,ds=simple_exit_state();r1=solve(s,ds);r2=solve(s,ds);self.assertEqual(r1['certificate_id'],r2['certificate_id']);self.assertFalse(r2['donors']['rows']);self.assertGreater(r2['donors']['covered'],0)
 def test_partial_sale_then_partial_cash_settlement_no_double_cover(self):
  s,ds=simple_exit_state();p=ONE-SLIP;sc=schedule(FEES);paid=sc.incremental('sell',D(50)*p,{}, {},1,shares=50);acc=sc.rate_accrual('sell',D(50)*p,1,shares=50)
  net1=D(50)*p-sum(paid.values(),Z);net2=D(50)*p-fee(50,p,FEES,'sell',paid,acc)
  s['rows'][0]['qty']-=50;s['rows'][0]['capital']-=50;s['rows'][0]['risk']-=D('2.5');s['lots']=copy.deepcopy(s['rows'])
  s['assets']=[dict(id='AR|partial',kind='sale_receivable',amount=net1,due_at='2025-07-04 09:30:00+08:00',parts=[]),dict(s['assets'][0],amount=net2,parts=[dict(layer='OLD',q=50,risk_release=D('2.5'))])]
  s['nav']+=net1-D(50)
  unsettled=solve(s,ds);self.assertFalse(unsettled['donors']['rows'])
  s['available']+=net1;s['assets']=s['assets'][1:]
  settled=solve(s,ds);self.assertEqual(unsettled['Q'],settled['Q']);self.assertEqual(unsettled['validation']['terminal'],settled['validation']['terminal']);self.assertFalse(settled['donors']['rows'])
 def test_cancel_pending_and_duplicate_asset_block_atomically(self):
  s,ds=simple_exit_state();s['assets'][0]['cancel_pending']=True;before=digest(s)
  with self.assertRaisesRegex(ValueError,'WAIT_CANCEL_ACK'):solve(s,ds)
  self.assertEqual(digest(s),before);s['assets'][0]['cancel_pending']=False;s['assets'].append(copy.deepcopy(s['assets'][0]))
  with self.assertRaisesRegex(ValueError,'duplicate'):solve(s,ds)
 def test_future_quote_and_gap_guard(self):
  s=state([],cash='1000000');d=demand(q=100);d['known_at']='2025-07-04 09:30:00+08:00';self.assertEqual(solve(s,[d])['Q']['NEW'],0)
  d=demand(q=100);d['floor']=d['mark'];self.assertEqual(solve(s,[d])['Q']['NEW'],0)
 def test_probe_core_pending_reserve_unchanged(self):
  s=state([],cash='1000000');d=demand(q=1000,mark='100',floor='90');d['pool']='probe';d['role']='core';d['use']='T'
  self.assertEqual(solve(s,[d])['Q']['NEW'],100)
  # Cancel-pending commitment remains charged, just as any other old order.
  s['rows'].append(dict(id='pending',sid='P',sector='P',pool='probe',role='core',qty=1000,mark=100,capital=D(100000),risk=D(5000)))
  self.assertEqual(solve(s,[d])['Q']['NEW'],0)
 def test_donor_not_yet_sellable_rejects_no_fictional_cash(self):
  s=state([lot(q=1100,mark='8',floor='7.45')],cash='1200');s['lots'][0]['sellable_qty']=0;d=demand(q=200,mark='1',floor='.98')
  r=solve(s,[d]);self.assertEqual(r['Q']['NEW'],0);self.assertFalse(r['donors']['rows'])
 def test_restart_fresh_never_revives_raw_target(self):
  s=state([lot()]);d=demand();c=solve(s,[d]);b=CertificateBook();accept_fixture(b,c)
  b.bind_reservation('same-industry-source-context','NEW','real-order-1',100,AT,receipt_id='receipt-NEW');b.actual_fill('real-order-1',50,fill_receipt_id='actual-fill-1');b.cancel_request('real-order-1')
  self.assertEqual(b.cap('same-industry-source-context','NEW',500,AT,receipt_id='receipt-NEW'),0)
  out=Path(__file__).with_name('restart');out.mkdir(exist_ok=True);(out/'BOOK.json').write_text(b.dumps());(out/'TRUSTED.json').write_text(json.dumps(dict(trusted_inputs=TRUSTED,actual_commitments=b.commitments()),default=str,sort_keys=True))
  subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('restart_worker.py')),str(out/'BOOK.json'),str(out/'TRUSTED.json'),hashlib.sha256((out/'TRUSTED.json').read_bytes()).hexdigest(),str(out/'RESTORED.json')],check=True)
  restored=json.loads((out/'RESTORED.json').read_text());self.assertEqual(restored['cap'],0);self.assertEqual(restored['orders'],b.orders);self.assertEqual(restored['filled'],b.filled)
  b=load_fixture(b);self.assertEqual(b.cap('same-industry-source-context','NEW',500,AT,receipt_id='receipt-NEW'),0)
  b.cancel_ack('real-order-1');self.assertEqual(b.cap('same-industry-source-context','NEW',500,AT,receipt_id='receipt-NEW'),50)
  self.assertEqual(b.cap('same-industry-source-context','NEW',500,'2025-07-05 09:30:00+08:00',receipt_id='receipt-NEW'),0)
 def test_wrong_certificate_source_rejected(self):
  b=CertificateBook();r=json.loads(b.dumps());r['contract']='wrong'
  with self.assertRaisesRegex(ValueError,'identity'):CertificateBook.loads(rehash_book(r),trusted_inputs={},actual_commitments=b.commitments())
 def test_native_dependency_binding_rejected(self):
  b=CertificateBook();r=json.loads(b.dumps());r['native_source_binding']['slippage']='future-other-value'
  with self.assertRaisesRegex(ValueError,'native source'):CertificateBook.loads(rehash_book(r),trusted_inputs={},actual_commitments=b.commitments())
 def test_excess_old_funding_not_silently_replaced_or_approved(self):
  s,ds=simple_exit_state();s['assets'][0]['pure_funding']=True
  # One small buy needs no donor; the old whole funding order is now excessive.
  r=solve(s,[ds[0]]);self.assertTrue(r['requires_native_existing_funding_reconciliation']);self.assertFalse(r['donors']['rows'])
  with self.assertRaisesRegex(ValueError,'acknowledgement'):accept_fixture(CertificateBook(),r)
 def test_actual_role_and_unknown_sale_fields_cannot_be_bypassed(self):
  s=state([],cash='1000000');d=demand(q=100);d['role']='core'
  self.assertEqual(solve(s,[d])['Q']['NEW'],0)
  s,ds=simple_exit_state();s['lots'][0]['sellable_qty']=None
  with self.assertRaisesRegex(ValueError,'UNKNOWN'):solve(s,ds)
 def test_changed_Q_unchanged_certificate_digest_rejected(self):
  c=solve(state([lot()]),[demand()]);c['Q']['NEW']=500
  with self.assertRaisesRegex(ValueError,'digest'):accept_fixture(CertificateBook(),c)
 def test_rehashed_Q_still_recomputed_from_actual_resources(self):
  c=solve(state([lot()]),[demand()]);c['Q']['NEW']=500;c['certificate_id']=digest({k:v for k,v in c.items() if k!='certificate_id'})
  with self.assertRaisesRegex(ValueError,'trusted snapshot'):accept_fixture(CertificateBook(),c)
 def test_receipt_identity_affects_certificate_and_cannot_cross_use(self):
  s=state([lot()]);d=demand();c=solve(s,[d]);b=CertificateBook();accept_fixture(b,c)
  with self.assertRaisesRegex(ValueError,'different receipt'):b.cap(c['target_id'],'NEW',500,AT,receipt_id='later-fresh')
  d2=demand();d2['receipt_id']='later-fresh';c2=solve(s,[d2]);self.assertNotEqual(c2['certificate_id'],c['certificate_id'])
  with self.assertRaisesRegex(ValueError,'fresh receipt'):accept_fixture(b,c2)
 def test_missing_fields_fail_closed_not_synthetic_filled(self):
  s,ds=bound(state([lot()]),[demand()]);del ds[0]['price_known_at']
  with self.assertRaisesRegex(ValueError,'missing demand'):P.solve(s,ds)
  s,ds=bound(state([lot()]),[demand()]);del ds[0]['receipt_binding']['start']
  with self.assertRaisesRegex(ValueError,'missing receipt'):P.solve(s,ds)
 def test_future_price_even_when_signal_clock_valid_is_rejected(self):
  s,ds=bound(state([],cash='1000000'),[demand(q=100)]);ds[0]['price_known_at']='2025-07-04 09:30:00+08:00'
  c=P.solve(s,ds);self.assertEqual(c['Q']['NEW'],0);self.assertTrue(any('future_price_known_at' in why for t in c['trace'] for why in t['violations']))
  ds[0]['price_known_at']='2025-07-03 15:10:00'
  with self.assertRaisesRegex(ValueError,'aware'):P.solve(s,ds)
 def test_valid_price_clock_metadata_is_still_bound_in_certificate(self):
  s,ds=bound(state([lot()]),[demand()]);c=P.solve(s,ds);changed=copy.deepcopy(ds);changed[0]['price_known_at']='2025-07-03 15:05:00+08:00';c2=P.solve(s,changed)
  self.assertEqual(c['Q'],c2['Q']);self.assertNotEqual(c['certificate_id'],c2['certificate_id'])
  with self.assertRaisesRegex(ValueError,'trusted snapshot'):P.verify_certificate(c,s,changed)
 def test_other_goal_one_AR_cannot_cover_old100_plus_new55(self):
  ar=dict(id='AR|one',kind='sale_receivable',amount=D(100),due_at='2025-07-04 09:30:00+08:00',parts=[])
  s=state([lot(q=89,mark='100',floor='99.99',purpose='T')],cash='1000',assets=[ar]);s['other_saved_goal_need']=100;d=demand(q=100,mark='.5',floor='.49')
  with self.assertRaisesRegex(ValueError,'RECONCILE_OTHER_COMMITTED_GOALS'):solve(s,[d])
  s['other_saved_goal_need']=0;c=solve(s,[d]);self.assertEqual(c['Q']['NEW'],100);self.assertEqual(c['donors']['covered'],D('55.028206602500'))
 def test_rehashed_book_state_quantity_and_actual_provider_checked(self):
  c=solve(state([lot()]),[demand()]);b=CertificateBook();accept_fixture(b,c)
  b.bind_reservation(c['target_id'],'NEW','real',100,AT,receipt_id='receipt-NEW');b.actual_fill('real',50,fill_receipt_id='fill-one');b.cancel_request('real')
  truth=b.commitments();r=json.loads(b.dumps());r['orders']['real']['remaining']=400
  with self.assertRaisesRegex(ValueError,'conservation'):CertificateBook.loads(rehash_book(r),trusted_inputs=TRUSTED,actual_commitments=truth)
  r=json.loads(b.dumps());r['orders']['real'].update(remaining=100,filled=0);r['filled']={};r['fill_receipts']={}
  with self.assertRaisesRegex(ValueError,'actual commitment'):CertificateBook.loads(rehash_book(r),trusted_inputs=TRUSTED,actual_commitments=truth)
 def test_load_missing_trusted_snapshot_and_forged_book_digest_reject(self):
  c=solve(state([lot()]),[demand()]);b=CertificateBook();accept_fixture(b,c)
  with self.assertRaisesRegex(ValueError,'trusted original snapshot'):CertificateBook.loads(b.dumps(),trusted_inputs={},actual_commitments=b.commitments())
  r=json.loads(b.dumps());r['certificates'][c['certificate_id']]['Q']['NEW']=500
  with self.assertRaisesRegex(ValueError,'book body digest'):CertificateBook.loads(json.dumps(r),trusted_inputs=TRUSTED,actual_commitments=b.commitments())
 def test_restore_fully_rehashed_forged_certificate_still_reproved(self):
  c=solve(state([lot()]),[demand()]);b=CertificateBook();accept_fixture(b,c);r=json.loads(b.dumps());old=c['certificate_id'];changed=r['certificates'].pop(old);changed['Q']['NEW']=500
  changed['certificate_id']=digest({k:v for k,v in changed.items() if k!='certificate_id'});new=changed['certificate_id'];r['certificates'][new]=changed;r['active'][c['target_id']]=new
  with self.assertRaisesRegex(ValueError,'trusted snapshot'):CertificateBook.loads(rehash_book(r),trusted_inputs=TRUSTED,actual_commitments=b.commitments())
  r=json.loads(b.dumps());del r['orders']
  with self.assertRaisesRegex(ValueError,'schema'):CertificateBook.loads(rehash_book(r),trusted_inputs=TRUSTED,actual_commitments=b.commitments())
 def test_wrong_actual_snapshot_or_target_and_analysis_view_cannot_commit(self):
  c=solve(state([lot()]),[demand()]);ss,dd=copy.deepcopy(TRUSTED[c['snapshot_sha256']]);ss['available']+=1
  with self.assertRaisesRegex(ValueError,'snapshot'):CertificateBook().accept(c,c['target_id'],snapshot=ss,demands=dd,actual_commitments=CertificateBook().commitments())
  ss,dd=copy.deepcopy(TRUSTED[c['snapshot_sha256']]);ss['analysis_only']=True;cc=P.solve(ss,dd)
  with self.assertRaisesRegex(ValueError,'analysis'):CertificateBook().accept(cc,cc['target_id'],snapshot=ss,demands=dd,actual_commitments=CertificateBook().commitments())
 def test_fill_receipt_dedup_and_missing_aggregate_quantity(self):
  c=solve(state([lot()]),[demand()]);b=CertificateBook();accept_fixture(b,c);b.bind_reservation(c['target_id'],'NEW','real',100,AT,receipt_id='receipt-NEW')
  b.actual_fill('real',50,fill_receipt_id='one');b.actual_fill('real',50,fill_receipt_id='one');self.assertEqual(b.orders['real']['filled'],50)
  with self.assertRaisesRegex(ValueError,'alias'):b.actual_fill('real',25,fill_receipt_id='one')
  b.filled={}
  with self.assertRaisesRegex(ValueError,'missing aggregate'):b.cap(c['target_id'],'NEW',500,AT,receipt_id='receipt-NEW')

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 Path(__file__).with_name('SYNTHETIC_RESULTS.json').write_text(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),passed=result.wasSuccessful(),financial_events=0),indent=2)+'\n')
 raise SystemExit(not result.wasSuccessful())
