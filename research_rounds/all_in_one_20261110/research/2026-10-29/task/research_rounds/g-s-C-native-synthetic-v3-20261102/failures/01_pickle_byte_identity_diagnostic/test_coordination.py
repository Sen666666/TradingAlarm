"""Incremental adversarial native lifecycle tests; no historical source loading."""
from test_native import *
import argparse

class Coordination(unittest.TestCase):
 root=None;records={}
 def keep(self,name,r,at,**extra):
  x=dict(state=r.observable(at),extra=extra);self.records[name]=x;IO.write_json(self.root/(name+'.json'),x,encoder=encode)
 def test01_pending_buy_does_not_block_other_target(self):
  r=Runner('C_BATCH20');aids=fixtures(r,1,'A','OLD');close(r,0,packet(r,aids,0),{'G':obs(r,'G',0)})
  r.event(op(1),is_open=True,capacities={aids[0]:0});a=r.account;old=a.buys[aids[0]];oid=old.order_id;deadline=a.supports[oid]['deadline'];priority=a.supports[oid]['priority'];reserve=old.remaining_budget_cny+old.fee_reserved_cny
  bs=fixtures(r,1,'B','NEW');close(r,1,packet(r,aids+bs,1),{})
  self.assertIn(aids[0],a.cancel_requests);self.assertEqual(a.buys[aids[0]].order_id,oid);self.assertEqual(a.supports[oid]['deadline'],deadline)
  r.event(op(2),is_open=True);self.assertGreater(a.quantity(bs[0]),0);self.assertEqual(a.quantity(aids[0]),0)
  self.assertEqual(a.buys[aids[0]].remaining_budget_cny+a.buys[aids[0]].fee_reserved_cny,reserve);self.assertEqual(a.supports[oid]['priority'],priority)
  cash=a.available;a.ack_buy_cancel(aids[0]);self.assertEqual(a.available,cash+reserve);r.assert_observers()
  self.keep('01_pending_buy_other_funded',r,op(2),old_order=oid,new_filled=a.quantity(bs[0]))
 def test02_old_funding_local_wait_other_plan_continues(self):
  r,old=funded('C10');new=switch(r,old);a=r.account;legacy={s:o.event_id for s,o in a.exits.items()};legacy_q={s:o.remaining_target for s,o in a.exits.items()}
  other=fixtures(r,1,'X','OTHER');allids=old+new+other;rows=packet(r,allids,3,priorities={s:(i,) for i,s in enumerate(other+new+old)})
  h={s:(300 if s=='OTHER' else 200 if s=='NEW' else 10) for s in set(a.market.sectors.values())};close(r,3,rows,{},h)
  self.assertTrue(all(s in r.local_wait_sids for s in new));self.assertNotIn(other[0],r.local_wait_sids);self.assertGreater(r.active['Q'][other[0]],0)
  for sid,oid in legacy.items():self.assertEqual(a.exits[sid].event_id,oid);self.assertEqual(a.exits[sid].remaining_target,legacy_q[sid]);self.assertIn(sid,a.funding.cancel_requests)
  self.assertTrue(all(not z['available_to_new_targets'] for z in r.coverage.snapshots[-1]['assets']))
  orders=a.funding.order_goals;self.assertTrue(any(set(v['goals'])!=set(orders[next(iter(legacy.values()))]['goals']) for v in orders.values()))
  self.keep('02_local_wait_other_plan',r,cl(3),legacy_orders=legacy,new_other_quantity=r.active['Q'][other[0]])
 def test03_partial_receivable_cancel_ACK_and_fresh_resume(self):
  r,old=funded('C_BATCH20');new=switch(r,old);a=r.account;sid=next(iter(a.exits));oid=a.exits[sid].event_id;cash=a.available
  f=r.apply_window('sell',sid,win(r,sid,op(3),capacity=100,eid='partial-owned',due=op(4)));self.assertEqual(a.available,cash)
  asset=r.coverage.receivables[f.settlement_id];self.assertEqual(asset['origin_order'],oid)
  allids=old+new;rows=packet(r,allids,3);close(r,3,rows,{})
  self.assertTrue(all(s in r.local_wait_sids for s in new));before=r.budget.batch['carry'];old_targets=set(a.funding.order_goals)
  # Requests leave funds/risk/carry in place until original native ACK.
  self.assertGreater(D(before),0);self.assertTrue(a.funding.cancel_requests);self.assertEqual(a.available,cash)
  acks=[(s,True) for s in a.funding.cancel_requests];r.event(cl(3)+timedelta(minutes=1),funding_cancel_acks=acks)
  self.assertEqual(r.budget.batch['carry'],before);self.assertEqual(a.available,cash)
  self.assertTrue(r.coverage.receivables[f.settlement_id]['owners']);r.event(op(4));self.assertGreater(a.available,cash)
  self.assertIn(f.settlement_id,r.coverage.settled);a.settle_due(op(4));self.assertEqual(len(r.coverage.settled),1)
  close(r,4,packet(r,allids,4),{})
  self.assertFalse(any(s in r.local_wait_sids for s in new));self.assertTrue(any(r.active['Q'].get(s,0) for s in new))
  self.assertEqual(a.supports[next(iter(r.authority.orders))]['receipt'].confirmed,cl(0));r.assert_observers()
  self.keep('03_partial_settle_resume',r,cl(4),old_orders=sorted(old_targets),released_asset=f.settlement_id,next_carry=r.budget.batch['carry'])
 def test04_independent_stop_not_global_WAIT(self):
  r,old=funded('C_BATCH20');new=switch(r,old);a=r.account;sid=next(iter(a.exits));oid=a.exits[sid].event_id;rows=packet(r,old+new,3);rows[sid]['i_valid']=False
  close(r,3,rows,{})
  self.assertEqual(a.exits[sid].event_id,oid);layer=next(z for z in a.layers if z['sid']==sid);self.assertEqual(a.exits[sid].remaining_target,layer['qty'])
  self.assertTrue(any('I_structure_exit' in d['reasons'] for d in a.exit_duties.values() if d['sid']==sid));self.assertEqual(r.last_completed_event,cl(3));self.assertEqual(a.policy.cursor,cl(3).date().toordinal())
  self.assertTrue(r.local_wait_sids);self.assertEqual(r.results[-1]['at'],cl(3).isoformat());r.assert_observers()
  r.event(op(4),is_open=True);self.assertEqual(a.quantity(sid),0)
  self.keep('04_stop_continues',r,op(4),retained_native_exit=oid)
 def test05_owned_receivable_restart_and_tamper(self):
  r,old=funded('C_BATCH20');new=switch(r,old);a=r.account;sid=next(iter(a.exits));f=r.apply_window('sell',sid,win(r,sid,op(3),capacity=100,eid='restart-owned',due=op(4)))
  close(r,3,packet(r,old+new,3),{});cp=self.root/'checkpoints'/'owned.pkl';r.checkpoint(cp);out=self.root/'child.json'
  subprocess.run([sys.executable,'-B',str(HERE/'restore_check.py'),str(cp),str(out),cl(3).isoformat()],check=True,capture_output=True,text=True)
  self.assertEqual(json.loads(out.read_text())['digest'],digest(r.observable(cl(3))))
  child=Runner.restore(cp);self.assertEqual(child.coverage.exported(),r.coverage.exported());child.event(op(4));r.event(op(4));self.assertEqual(digest(child.observable(op(4))),digest(r.observable(op(4))))
  bad=pickle.loads(pickle.dumps(r));bad.coverage.receivables[f.settlement_id]['amount']+=D(1)
  # Already settled assets also retain the exact amount/receipt; edits cannot
  # become an extra future claim.
  with self.assertRaises(ValueError):bad.assert_observers()
  self.keep('05_restart_ownership',r,op(4),checkpoint_sha256=N.sha(cp))
 def test06_full_fill_cleanup_and_structure_cancel_once(self):
  r=Runner('C_BATCH20');ss=fixtures(r,2,sector=lambda i:'S'+str(i));close(r,0,packet(r,ss,0),{'G':obs(r,'G',0)});r.event(op(1),is_open=True,capacities={ss[0]:0})
  self.assertGreater(r.account.quantity(ss[1]),0);self.assertTrue(any(o['filled']>0 and o['remaining']==0 for o in r.authority.orders.values()))
  rows=packet(r,ss,1,receipt=False,core=False);rows[ss[0]]['i_valid']=False;close(r,1,rows,{})
  a=r.account;oid=a.buys[ss[0]].order_id;cash=a.available;a.ack_buy_cancel(ss[0]);after=a.available;a.ack_buy_cancel(ss[0]);self.assertEqual(a.available,after);self.assertGreater(after,cash)
  self.assertEqual(r.authority.orders[oid]['remaining'],0);r.assert_observers()
  self.keep('06_native_cleanup_cancel',r,cl(1),refund_once=after-cash)
 def blocked_H1_close(self):
  r,ss=funded('C_BATCH20');normal=pickle.loads(pickle.dumps(r));rows=packet(r,ss,1,receipt=False,core=False);rows[ss[0]]['i_valid']=False
  sectors=sorted(set(r.account.market.sectors.values()));e=dict(day=cl(1).date().isoformat(),known_at=cl(1).isoformat(),industry_H1={s:100-i for i,s in enumerate(sectors)})
  bad=copy.deepcopy(e);bad['industry_H1'][r.account.market.sectors[ss[2]]]=None;observations={'G':obs(r,'G',1,105)}
  r.event(cl(1),observations=observations,stocks=rows,next_open=op(2),industry_evidence=bad)
  return r,normal,ss,rows,observations,bad,e
 def test07_missing_H1_commits_exit_F1_and_no_optional_orders(self):
  r,normal,ss,rows,observations,bad,good=self.blocked_H1_close();a=r.account
  stage=r.close_stages[cl(1).isoformat()];self.assertTrue(stage['necessary_done']);self.assertEqual(stage['optional_status'],'blocked_unknown_H1')
  self.assertEqual(r.last_completed_event,cl(1));self.assertEqual(r.f1seq['G'],2);self.assertEqual(a.exits[ss[0]].remaining_target,a.quantity(ss[0]));self.assertFalse(a.pending)
  self.assertEqual(len(r.authority.certificates),1);self.assertIn('UNKNOWN industry H1',stage['attempts'][0]['error']);before=digest(r.observable(cl(1)))
  # Duplicate source event and identical optional retry do NOT repeat ACT/F1,
  # line ratchets, native exit requests, budget or old callbacks.
  r.event(cl(1),observations=observations,stocks=rows,next_open=op(2),industry_evidence=bad)
  self.assertEqual(digest(r.observable(cl(1))),before);retry=r.retry_optional(cl(1),bad);self.assertTrue(retry['repeated_input']);self.assertEqual(digest(r.observable(cl(1))),before)
  self.keep('07_H1_necessary_committed',r,cl(1),error=stage['attempts'][0]['error'],optional_orders=0,exit_quantity=a.exits[ss[0]].remaining_target)
 def test08_blocked_phase_checkpoint_restore_optional_only_retry(self):
  r,normal,ss,rows,observations,bad,good=self.blocked_H1_close();cp=self.root/'checkpoints'/'H1-blocked.pkl';r.checkpoint(cp);out=self.root/'H1-child.json'
  subprocess.run([sys.executable,'-B',str(HERE/'restore_check.py'),str(cp),str(out),cl(1).isoformat()],check=True,capture_output=True,text=True)
  self.assertEqual(json.loads(out.read_text())['digest'],digest(r.observable(cl(1))));r=Runner.restore(cp);exit_ids={s:o.event_id for s,o in r.account.exits.items()};seq=dict(r.f1seq)
  with self.assertRaises(ValueError):r.retry_optional(cl(1),good)
  correction=dict(old_input=digest(bad),new_input=digest(good),reason='synthetic same-as-of source availability correction; not neutral fill')
  result=r.retry_optional(cl(1),good,correction=correction);self.assertEqual(result['state'],'NATIVE_BOUND');self.assertEqual(r.f1seq,seq);self.assertEqual({s:o.event_id for s,o in r.account.exits.items()},exit_ids)
  normal.event(cl(1),observations=observations,stocks=rows,next_open=op(2),industry_evidence=good)
  self.assertEqual(digest(r.account.exported(cl(1))),digest(normal.account.exported(cl(1))))
  frozen=digest(r.observable(cl(1)));self.assertEqual(r.retry_optional(cl(1),good)['state'],'OPTIONAL_ALREADY_SUCCEEDED');self.assertEqual(digest(r.observable(cl(1))),frozen)
  self.keep('08_optional_only_recovery',r,cl(1),checkpoint_sha256=N.sha(cp),financial_state_equals_correct_asof_branch=True)
 def test09_old_exit_executes_despite_H1_failure_no_late_revive(self):
  r,normal,ss,rows,observations,bad,good=self.blocked_H1_close();oid=r.account.exits[ss[0]].event_id;r.event(op(2),is_open=True)
  self.assertEqual(r.account.quantity(ss[0]),0);self.assertTrue(any(f.side=='sell' for f in r.account.fills));self.assertEqual(len(r.authority.certificates),1)
  with self.assertRaises(ValueError):r.retry_optional(cl(1),good,correction=dict(old_input=digest(bad),new_input=digest(good),reason='late'))
  self.keep('09_exit_after_optional_failure',r,op(2),original_exit=oid,new_optional_buys=0)
 def test10_malformed_bound_retry_complete_rollback_and_recovery(self):
  r,normal,ss,rows,observations,bad,good=self.blocked_H1_close();broken=copy.deepcopy(good);broken['industry_H1'][r.account.market.sectors[ss[2]]]='malformed-H1'
  correction=dict(old_input=digest(bad),new_input=digest(broken),reason='bound malformed same-as-of input, adversarial')
  before=digest(r.observable(cl(1)));whole_before=hashlib.sha256(pickle.dumps(r)).hexdigest();budget=r.budget.dumps();binding=r.binding_id
  with self.assertRaises(ValueError):r.retry_optional(cl(1),broken,correction=correction)
  self.assertEqual(digest(r.observable(cl(1))),before);self.assertEqual(r.budget.dumps(),budget);self.assertEqual(r.binding_id,binding)
  self.assertEqual(hashlib.sha256(pickle.dumps(r)).hexdigest(),whole_before)
  cp=self.root/'checkpoints'/'after-malformed.pkl';r.checkpoint(cp);r=Runner.restore(cp);self.assertEqual(digest(r.observable(cl(1))),before)
  out=self.root/'malformed-child.json';subprocess.run([sys.executable,'-B',str(HERE/'restore_check.py'),str(cp),str(out),cl(1).isoformat()],check=True,capture_output=True,text=True)
  self.assertEqual(json.loads(out.read_text())['digest'],before)
  legal=dict(old_input=digest(bad),new_input=digest(good),reason='valid same-as-of fixture availability correction')
  self.assertEqual(r.retry_optional(cl(1),good,correction=legal)['state'],'NATIVE_BOUND');self.assertEqual(r.f1seq['G'],2)
  self.keep('10_malformed_retry_atomic',r,cl(1),failed_attempt_hash_unchanged=before,complete_pickle_state_sha256=whole_before,original_budget_binding=binding,child_hash=before)
 def test11_bad_correction_binding_and_future_retry_do_not_mutate(self):
  r,normal,ss,rows,observations,bad,good=self.blocked_H1_close();before=digest(r.observable(cl(1)))
  for correction in [None,dict(old_input='wrong',new_input=digest(good),reason='bad'),dict(old_input=digest(bad),new_input='wrong',reason='bad'),dict(old_input=digest(bad),new_input=digest(good),reason='')]:
   with self.assertRaises(ValueError):r.retry_optional(cl(1),good,correction=correction)
   self.assertEqual(digest(r.observable(cl(1))),before)
  future=copy.deepcopy(good);future['known_at']=cl(2).isoformat()
  with self.assertRaises(ValueError):r.retry_optional(cl(1),future,correction=dict(old_input=digest(bad),new_input=digest(future),reason='future'))
  self.assertEqual(digest(r.observable(cl(1))),before);self.keep('11_bad_bindings_atomic',r,cl(1))
 def test12_first_optional_exception_preserves_necessary_stage(self):
  r,ss=funded('C_BATCH20');rows=packet(r,ss,1,receipt=False,core=False);rows[ss[0]]['i_valid']=False
  sectors=sorted(set(r.account.market.sectors.values()));e=dict(day=cl(1).date().isoformat(),known_at=cl(1).isoformat(),industry_H1={s:100-i for i,s in enumerate(sectors)})
  good=copy.deepcopy(e);e['industry_H1'][r.account.market.sectors[ss[2]]]='not-a-number';obs1={'G':obs(r,'G',1,105)}
  with self.assertRaises(ValueError):r.event(cl(1),observations=obs1,stocks=rows,next_open=op(2),industry_evidence=e)
  self.assertEqual(r.last_completed_event,cl(1));self.assertIn(ss[0],r.account.exits);self.assertEqual(r.f1seq['G'],2);self.assertEqual(r.close_stages[cl(1).isoformat()]['optional_status'],'failed_exception')
  before=digest(r.observable(cl(1)));r.event(cl(1),observations=obs1,stocks=rows,next_open=op(2),industry_evidence=e);self.assertEqual(digest(r.observable(cl(1))),before)
  self.assertEqual(r.retry_optional(cl(1),good,correction=dict(old_input=digest(e),new_input=digest(good),reason='corrected malformed same-asof fixture'))['state'],'NATIVE_BOUND')
  self.keep('12_first_exception_required_committed',r,cl(1))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=HERE/'runs-incremental');args=parser.parse_args();Coordination.root=args.out;args.out.mkdir(parents=True,exist_ok=True)
 start=time.monotonic();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Coordination))
 payload=dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),seconds=time.monotonic()-start,historical_account_events=0,scope='incremental native synthetic target coordination')
 IO.write_json(args.out/'RESULTS.json',payload);print(json.dumps(payload));raise SystemExit(not result.wasSuccessful())
