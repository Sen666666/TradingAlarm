"""R2 adversarial repairs and native scheduling. No historical account paths."""
import sys,unittest,json,pickle,subprocess
from datetime import timedelta
from decimal import Decimal as D
from dataclasses import asdict
from test_native import Cases,fixtures,proof,intents,clock,op,cl,win,allow,activate
from native_capital import SyntheticRunner,CanonicalReceipt,encode,digest
from test_native import seed,observation
from imports_native import IO,O,T,COMPOSITE,sha

def packet(a,sids,n,*,price=None,valid=True,q=True,core=True,fresh=True,i_floor=None,cp_floor=None):
 at=cl(n);out={}
 for rank,s in enumerate(sids):
  out[s]=dict(known_at=at,close=a.market.prices[s] if price is None else D(str(price)),i_valid=valid,q=q,core_event=core,
   i_floor=a.facts.floors[s] if i_floor is None else D(str(i_floor)),cp_floor=a.facts.floors[s] if cp_floor is None else D(str(cp_floor)),
   receipt=CanonicalReceipt('source-CP1|'+s+'|'+str(n),s,cl(n)-timedelta(days=1),cl(n),cl(n),(0,1)) if fresh else None,priority=(rank,),structure=(0,1))
 return out
def generated_source():
 r=SyntheticRunner();a=r.account;ss=fixtures(a,10,lambda i:'S'+str(i//2));seed(r,'G')
 first=packet(a,ss,0);first[ss[-1]]['q']=False
 second=packet(a,ss,1,price=101,core=False,fresh=False);second[ss[0]]['i_valid']=False;second[ss[0]]['q']=False;second[ss[-1]]=packet(a,[ss[-1]],1,core=False)[ss[-1]]
 return r,ss,[dict(at=cl(0),observations={'G':observation('G',cl(0),101)},stocks=first),dict(at=op(1),is_open=True),dict(at=cl(1),observations={'G':observation('G',cl(1),105)},stocks=second),dict(at=op(2),is_open=True),dict(at=cl(2),observations={'G':observation('G',cl(2),110)},stocks=packet(a,ss,2,price=102,core=False,fresh=False))]

class Revision(Cases):
 def test_22_ACT_completes_partial_and_same_layer_reason_union(self):
  r=SyntheticRunner();a=r.account;ss=fixtures(a,8);proof(r,'G',0);r.opening(intents(a,ss),op(1));a.snapshot(cl(1));z=a.layers[0]
  a.trim(z['id'],200,clock(1),'existing_allocation');eid=a.exits[z['sid']].event_id;a.trim(z['id'],100,clock(1),'protection_overlap')
  self.assertEqual(sum(e.remaining for e in a.policy.locks.values() if e.lot==z['id']),200)
  for s in ss:a.mark(s,70,cl(1),a.market.sectors[s])
  proof(r,'G',1,105);self.assertFalse(a.policy.act['on']);self.assertEqual(a.exits[z['sid']].event_id,eid)
  self.assertEqual(a.exits[z['sid']].remaining_target,z['qty']);self.assertEqual(sum(e.remaining for e in a.policy.locks.values() if e.lot==z['id']),z['qty'])
  self.assertEqual(len([e for e in a.policy.locks.values() if e.lot==z['id']]),2)
  self.assertTrue(all('ACT_pause' in a.exit_duties[e.eid]['reasons'] for e in a.policy.locks.values() if e.lot==z['id']))
  self.keep('22_ACT_partial_union',dict(state=a.exported(cl(1)),old_request=200,full_union=z['qty'],old_native_order_id_preserved=eid))
 def test_23_fraction_zero_unknown_is_atomic_rejection(self):
  r=SyntheticRunner();a=r.account;ss=fixtures(a,1,lambda i:'S',50,48);proof(r,'G',0);a.submit(intents(a,ss)[0],op(1));a.fill_buy(ss[0],win(a,ss[0],op(1),400,'400','buy'));a.ack_buy_cancel(ss[0]);a.snapshot(cl(1));a.trim(a.layers[0]['id'],1,clock(1),'one_share_exit')
  before=digest(a.exported(cl(1)))
  with self.assertRaisesRegex(ValueError,'atomic pre-action rejection'):a.split(event_id='fraction-half',sid=ss[0],ratio=D('.5'),at=op(2),new_shares_sellable_at=op(3))
  self.assertEqual(before,digest(a.exported(cl(1))));self.assertEqual(a.quantity(ss[0]),400);self.assertEqual(a.exits[ss[0]].remaining_target,1)
  self.assertNotIn('fraction-half',a.action_events)
  # Even corrupted/imported UNKNOWN with zero remainder cannot disappear.
  e=next(iter(a.policy.locks.values()));e.e0=None;e.remaining=0
  with self.assertRaisesRegex(Exception,'unconfirmed zero'):a.resources()
  self.keep('23_atomic_fraction_rejected',dict(financial_and_policy_unchanged=True,split_not_recorded=True,unknown_zero_cannot_be_aggregated_as_zero=True,before_digest=before))
 def test_24_selected_mobile_cannot_borrow_sellable_core(self):
  r=SyntheticRunner();a=r.account;ss=fixtures(a,1,lambda i:'S',20,19);proof(r,'G',0);i=a.intent(ss[0],clock(0),core=True);r.opening([i],op(1));core=a.layers[0]
  j=a.intent(ss[0],clock(1),receipt='mobile-next-day',core=False,cp_floor=D('19.5'));r.opening([j],op(2));mobile=a.layers[1];a.snapshot(op(2));a.trim(mobile['id'],200,T.admission.Clock(op(2),op(2)+timedelta(minutes=1),op(2).date()),'mobile_only')
  before=digest(a.exported(op(2)));blocked=a.fill_exit(ss[0],win(a,ss[0],op(2)+timedelta(minutes=2),200,'too-early-mobile'));self.assertIsNone(blocked);self.assertEqual(core['qty'],999)
  self.assertEqual(a.exits[ss[0]].remaining_target,200)
  sold=a.fill_exit(ss[0],win(a,ss[0],op(3),200,'mobile-now-legal'));self.assertEqual(sold.shares,200);self.assertEqual(core['qty'],999);self.assertEqual(a.trades[-1]['parts'][0]['layer'],mobile['id'])
  a.assert_lot_bridge();self.keep('24_selected_lot_sellability',dict(blocked_early=True,core_unchanged=core['qty'],actual_parts=a.trades[-1]['parts'],state=a.exported(op(3))))
 def test_25_full_close_ACT_F1_and_old_line_before_new_line(self):
  r=SyntheticRunner();a=r.account;ss=fixtures(a,9);seed(r,'G');r.event(cl(0),observations={'G':observation('G',cl(0),101)},stocks=packet(a,ss,0));r.event(op(1),is_open=True)
  self.assertEqual(len(a.positions),9);self.assertGreater(a.nav(op(1)),D(990000));self.assertEqual(len(a.policy.consumed),9)
  rows=packet(a,ss,1,price=70,valid=False,q=False,i_floor=96,cp_floor=97);r.event(cl(1),observations={'G':observation('G',cl(1),105)},stocks=rows)
  self.assertFalse(a.policy.act['on']);self.assertFalse(a.policy.incident['phase_started_once']);self.assertFalse(a.policy.allowed('G','G'))
  self.assertEqual(sum(e.remaining for e in a.policy.locks.values()),sum(z['qty'] for z in a.layers));self.assertEqual(len(a.exits),9)
  self.assertTrue(all(e.h['floor']==95 for e in a.policy.locks.values()))
  trace=r.lifecycle[-1]['trace'];self.assertLess(trace.index('ACT_incident_cutoff'),trace.index('F1_failure_create_advance'))
  self.keep('25_full_close_ACT_F1',r.observable(cl(1)))
 def test_26_old_mobile_trigger_precedes_fresh_higher_protection(self):
  r=SyntheticRunner();a=r.account;ss=fixtures(a,1);seed(r,'G');r.event(cl(0),observations={'G':observation('G',cl(0),101)},stocks=packet(a,ss,0));r.event(op(1),is_open=True)
  rows=packet(a,ss,1,price=94,i_floor=96,cp_floor=97);r.event(cl(1),observations={'G':observation('G',cl(1),105)},stocks=rows)
  self.assertEqual(a.layers[0]['floor'],D(95));e=next(iter(a.policy.locks.values()));self.assertEqual(e.h['floor'],D(95));self.assertEqual(e.reason,'CP1_old_line_exit');self.assertGreater(e.e0,0)
  self.keep('26_old_line_before_ratchet',r.observable(cl(1)))
 def test_27_whole_batch_before_window_no_refill_from_late_cancel(self):
  r=SyntheticRunner();a=r.account;ss=fixtures(a,10,lambda i:'S'+str(i//2));seed(r,'G');r.event(cl(0),observations={'G':observation('G',cl(0),101)},stocks=packet(a,ss,0));consults=[]
  def windows(sid,at):
   batch=[x for x in a.native_callbacks if x['kind']=='entire_batch_reserved_before_windows'][-1]
   self.assertEqual(len(batch['orders']),9);self.assertNotIn(ss[-1],a.buys);consults.append(dict(sid=sid,reservations_before=len([x for x in a.audit_log if x['kind']=='reserve'])))
   if sid==ss[0]:a.request_buy_cancel(sid);a.ack_buy_cancel(sid);return None
   return win(a,sid,at,eid='batch|'+sid,side='buy')
  r.event(op(1),is_open=True,buy_windows=windows)
  self.assertEqual(len(a.policy.consumed),9);self.assertFalse(a.quantity(ss[0]));self.assertFalse(a.quantity(ss[-1]));self.assertNotIn(ss[-1],a.buys);self.assertEqual(len(consults),9)
  self.assertGreater(a.available,D(190000));self.keep('27_reserve_batch_before_windows',dict(consults=consults,state=r.observable(op(1)),unfunded_last_stock_not_revisited=True))
 def test_28_close_sources_drive_S80_without_manual_permission(self):
  r=SyntheticRunner();a=r.account;ss=fixtures(a,8,lambda i:'B',160,152);seed(r,'B')
  r.event(cl(0),observations={'B':observation('B',cl(0),101)},stocks=packet(a,ss,0,core=False));r.event(op(1),is_open=True);self.assertFalse(a.positions);self.assertFalse(a.policy.consumed)
  r.event(cl(1),observations={'B':observation('B',cl(1),105)},stocks=packet(a,ss,1,core=False));self.assertEqual(list(a.policy.k),['B']);r.event(op(2),is_open=True);b=a.bridge(op(2));self.assertGreater(b['inventory']/b['nav'],D('.795'))
  self.keep('28_source_driven_S80',dict(state=r.observable(op(2)),actual_exposure=b['inventory']/b['nav'],permission_and_K_not_manually_assigned=True))
 def test_29_physical_prefix_future_mutation_and_cross_process_continue(self):
  full,ss,source=generated_source();short=pickle.loads(pickle.dumps(full));mutated=pickle.loads(pickle.dumps(full));changed=pickle.loads(pickle.dumps(source));changed[-1]['stocks'][ss[1]]['close']=D(999999)
  for event in source[:3]:full.event(**pickle.loads(pickle.dumps(event)))
  for event in pickle.loads(pickle.dumps(source[:3])):short.event(**event)
  for event in changed[:3]:mutated.event(**event)
  expected=digest(full.observable(cl(1)));self.assertEqual(expected,digest(short.observable(cl(1))));self.assertEqual(expected,digest(mutated.observable(cl(1))))
  cp=self.root/'checkpoints'/'full-close.pkl';full.checkpoint(cp);out=self.root/'checkpoints'/'full-continued.json';subprocess.run([sys.executable,'-B',str(O/'restore_revision.py'),str(cp),str(out),op(2).isoformat()],capture_output=True,text=True,check=True)
  restored=SyntheticRunner.restore(cp);full.event(**source[3]);restored.event(**source[3]);self.assertEqual(digest(full.observable(op(2))),digest(restored.observable(op(2))))
  child=json.loads(out.read_text());self.assertEqual(child['digest'],digest(full.observable(op(2))))
  self.assertGreater(len(restored.account.trades),len(short.account.trades));self.assertEqual(len(short.account.exits),1)
  with self.assertRaisesRegex(ValueError,'already completed'):restored.event(**source[3])
  self.keep('29_prefix_restore',dict(prefix_digest=expected,physical_equal=True,changed_future_equal=True,cross_process=child,checkpoint_sha256=sha(cp),post_restart=restored.observable(op(2))))
 def test_30_multilayer_exit_union_single_native_commission(self):
  r=SyntheticRunner();a=r.account;ss=fixtures(a,1,lambda i:'S',20,19);proof(r,'G',0);r.opening([a.intent(ss[0],clock(0),core=True)],op(1));r.opening([a.intent(ss[0],clock(1),receipt='mobile',core=False,cp_floor=D('19.5'))],op(2));a.snapshot(cl(2));core,mobile=a.layers
  a.trim(mobile['id'],200,clock(2),'mobile_rule');oid=a.exits[ss[0]].event_id;a.trim(mobile['id'],100,clock(2),'allocation_overlap');a.trim(core['id'],100,clock(2),'core_allocation')
  self.assertEqual(a.exits[ss[0]].remaining_target,300);self.assertEqual(a.exits[ss[0]].event_id,oid)
  f=a.fill_exit(ss[0],win(a,ss[0],op(3),300,'both_layers'));self.assertEqual(f.shares,300);self.assertEqual(len(a.trades[-1]['parts']),2);self.assertEqual(sum(p['fee_cny'] for p in a.trades[-1]['parts']),f.fees_cny);self.assertEqual(core['qty'],899)
  self.assertEqual(len([x for x in a.fills if x.side=='sell']),1);self.keep('30_multilayer_one_native_fill',r.observable(op(3)))
 def test_31_cancel_pending_support_deadline_and_future_rejection(self):
  r=SyntheticRunner();a=r.account;ss=fixtures(a,1);seed(r,'G');r.event(cl(0),observations={'G':observation('G',cl(0),101)},stocks=packet(a,ss,0));r.event(op(1),is_open=True,buy_windows=lambda s,t:None);oid=a.buys[ss[0]].order_id;deadline=a.supports[oid]['deadline'];cash=a.available
  # P lapse is a real frozen F1 output; old order waits for explicit ACK.
  r.event(cl(1),observations={'G':observation('G',cl(1),101,.4)},stocks=packet(a,ss,1,core=False));self.assertIn(ss[0],a.cancel_requests);self.assertEqual(a.available,cash);self.assertEqual(a.supports[oid]['deadline'],deadline)
  r.event(op(2),is_open=True);self.assertEqual(a.available,cash);self.assertFalse(a.positions)
  a.ack_buy_cancel(ss[0]);self.assertGreater(a.available,cash);self.assertEqual(len(a.policy.consumed),1)
  before=digest(r.observable(op(2)));future=packet(a,ss,2);future[ss[0]]['known_at']=cl(3)
  with self.assertRaisesRegex(ValueError,'future stock'):r.planning(cl(2),{},future)
  self.assertEqual(before,digest(r.observable(op(2))));self.keep('31_cancel_and_future_clock',dict(deadline=deadline,new_receipt_did_not_extend=True,state=r.observable(op(2))))

def main():
 root=O/'runs'/(sys.argv[1] if len(sys.argv)>1 else 'attempt-001');root.mkdir(parents=True,exist_ok=False);Revision.root=root
 IO.prepare_targets(dict(final=root/'RESULTS.json',checkpoint=root/'checkpoints'/'probe.pkl',failure=root/'failure'/'ERROR.json'))
 for p in O.glob('*.py'):IO.write_bytes(root/'source'/p.name,p.read_bytes())
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Revision))
 out=dict(contract=COMPOSITE,adapter_sha256=sha(O/'native_capital.py'),tests=result.testsRun,passed=result.wasSuccessful(),failures=[dict(test=str(t),trace=v) for t,v in result.failures+result.errors],historical_paths=0)
 IO.write_json(root/'RESULTS.json',out);print(json.dumps(out,ensure_ascii=False,indent=2));return not result.wasSuccessful()
if __name__=='__main__':raise SystemExit(main())
