"""R4 same-goal funding coverage, actual liquidity and cancel/ACK regressions."""
import sys,json,unittest,subprocess
from datetime import timedelta
from decimal import Decimal as D
from test_k_change import KChange
from test_revision import packet,seed,observation
from test_native import fixtures,op,cl,win
from native_capital import SyntheticRunner,UnsupportedOperation,digest,encode
from imports_native import O,IO,COMPOSITE,sha

def rows(a,old,new,n,*,fresh=True,core_price=20,mobile_valid=True):
 out=packet(a,old,n,core=False,fresh=False);out[old[1]]['close']=D(core_price);out[old[0]]['i_valid']=mobile_valid
 out.update(packet(a,new,n,core=False,fresh=fresh));return out
def funding_scene():
 r=SyntheticRunner();a=r.account;m=fixtures(a,1,lambda i:'OLD_M',100,95,prefix='M')[0];c=fixtures(a,1,lambda i:'OLD_C',20,19,prefix='C')[0];old=[m,c];seed(r,'G');seed(r,'B')
 first=packet(a,[m],0,core=False);first.update(packet(a,[c],0,fresh=False,core=True));r.event(cl(0),observations={'G':observation('G',cl(0),101)},stocks=first);r.event(op(1),is_open=True)
 a.migrate(next(z['id'] for z in a.layers if z['sid']==c))  # Real optional pool transfer; no cash/risk change.
 new=fixtures(a,8,lambda i:'B',50,D('47.5'),cl(1),'B');p=rows(a,old,new,1,fresh=False)
 for s in new:p[s]['q']=False
 r.event(cl(1),observations={'G':observation('G',cl(1),101),'B':observation('B',cl(1),101)},stocks=p);r.event(op(2),is_open=True)
 r.event(cl(2),observations={'G':observation('G',cl(2),101),'B':observation('B',cl(2),105)},stocks=rows(a,old,new,2));first_plan=r.lifecycle[-1]['allocation']
 r.event(op(3),is_open=True,sell_windows=lambda s,t:None)
 r.event(cl(3),observations={'G':observation('G',cl(3),101),'B':observation('B',cl(3),105)},stocks=rows(a,old,new,3));return r,old,new,first_plan,r.lifecycle[-1]['allocation']
def close_again(r,old,new,n,*,core_price=20,mobile_valid=True,Bclose=105,Bbreadth=.8,fresh=True):
 r.event(cl(n),observations={'G':observation('G',cl(n),101),'B':observation('B',cl(n),Bclose,Bbreadth)},stocks=rows(r.account,old,new,n,core_price=core_price,mobile_valid=mobile_valid,fresh=fresh))
 return r.lifecycle[-1]['allocation']

class Funding(KChange):
 def test_36_same_goal_cross_day_fresh_no_second_core_sale(self):
  r,old,new,first,second=funding_scene();a=r.account
  self.assertEqual(first['reductions'][0]['q'],199);self.assertEqual(a.exits[old[0]].remaining_target,199);self.assertNotIn(old[1],a.exits)
  self.assertGreater(second['needed'],0);self.assertEqual(second['uncovered'],0);self.assertEqual(second['reductions'],[])
  self.assertEqual(first['demand'][0]['goal_id'],second['demand'][0]['goal_id']);self.assertNotEqual(first['demand'][0]['sid'],second['demand'][0]['sid'])
  cash=a.available;before=sum(a.quantity(s) for s in new);r.event(op(4),is_open=True,sell_windows=lambda s,t:None)
  self.assertEqual(cash,a.available);self.assertEqual(before,sum(a.quantity(s) for s in new));self.assertNotIn('source-CP1|'+new[-1]+'|3',a.policy.consumed)
  self.keep('36_repeat_goal_no_double_sale',dict(first=first,second=second,state=r.observable(op(4)),coverage_did_not_buy_stock=True))
 def test_37_partial_sale_AR_then_settlement_not_double_counted(self):
  r,old,new,first,second=funding_scene();a=r.account;cash=a.available
  f=a.fill_exit(old[0],win(a,old[0],op(4),100,'partial-funding',due=op(5)));self.assertEqual(f.shares,100);self.assertEqual(a.available,cash)
  p=close_again(r,old,new,4);self.assertEqual(p['reductions'],[]);self.assertEqual(p['uncovered'],0)
  assets=p['coverage']['assets'];self.assertEqual(sum(x['kind']=='sale_receivable' for x in assets),1);self.assertEqual(sum(x['kind']=='pending_exit' for x in assets),1)
  ar=sum(x['amount'] for x in assets if x['kind']=='sale_receivable');before_need=p['needed'];a.settle_due(op(5));self.assertEqual(a.available,cash+ar)
  q=close_again(r,old,new,5);self.assertEqual(q['reductions'],[]);self.assertEqual(q['uncovered'],0);self.assertEqual(before_need-q['needed'],ar)
  self.assertFalse(any(x['kind']=='sale_receivable' for x in q['coverage']['assets']));self.assertEqual(a.exits[old[0]].remaining_target,99)
  self.keep('37_partial_sale_and_settlement',dict(partial_receipt=f,unsettled=p,settled=q,actual_AR=ar,state=r.observable(cl(5))))
 def test_38_replacement_waits_cancel_ACK_and_fresh_receipt(self):
  r,old,new,first,second=funding_scene();a=r.account;cash=a.available;oldid=a.exits[old[0]].event_id;lock_risk=a.totals()['risk']
  a.request_funding_cancel(old[0],op(4),'explicit_replace_illiquid_order');waiting=close_again(r,old,new,4)
  self.assertTrue(waiting['waiting_cancel_ack']);self.assertEqual(waiting['reductions'],[]);self.assertEqual(a.exits[old[0]].event_id,oldid);self.assertNotIn(old[1],a.exits);self.assertEqual(a.available,cash)
  r.event(op(5),is_open=True,funding_cancel_acks=[(old[0],True)],sell_windows=lambda s,t:None);self.assertNotIn(old[0],a.exits);self.assertEqual(a.available,cash);self.assertEqual(a.totals()['risk'],lock_risk)
  replacement=close_again(r,old,new,5);self.assertTrue(replacement['reductions']);self.assertTrue(all(x['sid']==old[1] for x in replacement['reductions']));self.assertNotIn(old[0],a.exits)
  self.assertNotIn('source-CP1|'+new[-1]+'|3',a.policy.consumed);self.assertEqual(a.available,cash)
  self.keep('38_cancel_ACK_before_replacement',dict(waiting=waiting,replacement=replacement,old_order=oldid,old_risk_lock_retained=True,state=r.observable(cl(5))))
 def test_39_target_invalid_cancels_only_funding_not_forced_exit(self):
  r,old,new,first,second=funding_scene();a=r.account;cash=a.available;bad=close_again(r,old,new,4,Bclose=80,Bbreadth=.2,fresh=False)
  self.assertIn(old[0],a.funding.cancel_requests);self.assertIn(old[0],a.exits);self.assertEqual(bad['reductions'],[]);self.assertEqual(a.available,cash)
  mandatory=next(s for s in new if s in a.exits)
  with self.assertRaisesRegex(UnsupportedOperation,'mandatory exit'):a.request_funding_cancel(mandatory,cl(4))
  r.event(op(5),is_open=True,funding_cancel_acks=[(old[0],True)],sell_windows=lambda s,t:None);self.assertNotIn(old[0],a.exits);self.assertIn(mandatory,a.exits);self.assertEqual(a.available,cash)
  e=next(e for e in a.policy.locks.values() if e.sid==old[0]);self.assertGreater(e.remaining,0)
  self.keep('39_target_invalidation',dict(plan=bad,risk_lock_not_freed=e,state=r.observable(op(5))))
 def test_40_funding_checkpoint_cross_process_resume(self):
  r,old,new,first,second=funding_scene();cp=self.root/'checkpoints'/'funding.pkl';out=self.root/'checkpoints'/'funding-child.json';r.checkpoint(cp)
  subprocess.run([sys.executable,'-B',str(O/'restore_revision.py'),str(cp),str(out),op(4).isoformat()],capture_output=True,text=True,check=True)
  restored=SyntheticRunner.restore(cp);self.assertEqual(digest(restored.observable(cl(3))),digest(r.observable(cl(3))))
  r.event(op(4),is_open=True);restored.event(op(4),is_open=True);child=json.loads(out.read_text());self.assertEqual(child['digest'],digest(r.observable(op(4))));self.assertEqual(child['digest'],digest(restored.observable(op(4))))
  self.keep('40_funding_restart',dict(checkpoint_sha=sha(cp),cross_process=child,state=restored.observable(op(4))))
 def test_41_price_requote_supplements_only_gap_then_cancels_excess(self):
  r,old,new,first,second=funding_scene();a=r.account;p=close_again(r,old,new,4,core_price=22)
  self.assertGreater(p['uncovered'],0);self.assertTrue(p['reductions']);self.assertLess(sum(x['estimated_net'] for x in p['reductions']),D(1000));self.assertEqual(a.exits[old[0]].remaining_target,199)
  q=close_again(r,old,new,5,core_price=20);self.assertIn(old[1],a.funding.cancel_requests);self.assertTrue(q['waiting_cancel_ack']);self.assertEqual(q['reductions'],[])
  cash=a.available;r.event(op(6),is_open=True,funding_cancel_acks=[(old[1],True)],sell_windows=lambda s,t:None);self.assertEqual(a.available,cash);self.assertNotIn(old[1],a.exits);self.assertIn(old[0],a.exits)
  self.keep('41_requote_and_reduce',dict(positive_delta=p,price_restored=q,state=r.observable(op(6))))
 def test_42_forced_exit_requotes_one_asset_and_preserves_obligation(self):
  r,old,new,first,second=funding_scene();a=r.account;p=close_again(r,old,new,4,mobile_valid=False)
  self.assertEqual(a.exits[old[0]].remaining_target,a.quantity(old[0]));self.assertEqual(p['reductions'],[])
  assets=[x for x in p['coverage']['assets'] if x.get('sid')==old[0]];self.assertEqual(len(assets),1);self.assertEqual(assets[0]['quantity'],999);self.assertFalse(assets[0]['pure_funding'])
  self.assertFalse(a._is_pure_funding_exit(old[0]));self.keep('42_forced_exit_one_asset',dict(plan=p,state=r.observable(cl(4))))

def main():
 root=O/'runs'/(sys.argv[1] if len(sys.argv)>1 else 'attempt-001');root.mkdir(parents=True,exist_ok=False);Funding.root=root
 IO.prepare_targets(dict(final=root/'RESULTS.json',checkpoint=root/'checkpoints'/'probe.pkl',failure=root/'failure'/'ERROR.json'))
 for p in O.glob('*.py'):IO.write_bytes(root/'source'/p.name,p.read_bytes())
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Funding))
 report=dict(contract=COMPOSITE,adapter_sha256=sha(O/'native_capital.py'),tests=result.testsRun,passed=result.wasSuccessful(),failures=[dict(test=str(t),trace=v) for t,v in result.failures+result.errors],historical_paths=0)
 IO.write_json(root/'RESULTS.json',report);print(json.dumps(report,indent=2));return not result.wasSuccessful()
if __name__=='__main__':raise SystemExit(main())
