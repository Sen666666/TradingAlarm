"""R3 K-only allocation repair; no historical market/account path."""
import sys,json,unittest
from decimal import Decimal as D
from datetime import timedelta
from test_revision import Revision,packet,seed,observation
from test_native import fixtures,intents,proof,allow,activate,clock,op,cl,win
from native_capital import SyntheticRunner,UnsupportedOperation,digest,encode,LR
from imports_native import O,IO,COMPOSITE,sha

def k_scene(new_stock_count):
 r=SyntheticRunner();a=r.account;old=fixtures(a,8,lambda i:'A',100,95,prefix='A');seed(r,'A');seed(r,'B')
 r.event(cl(0),observations={'A':observation('A',cl(0),101)},stocks=packet(a,old,0,core=False));r.event(op(1),is_open=True)
 r.event(cl(1),observations={'A':observation('A',cl(1),105)},stocks=packet(a,old,1,core=False));r.event(op(2),is_open=True)
 new=fixtures(a,new_stock_count,lambda i:'B',50,D('47.5'),cl(2),'B')
 rows=packet(a,old,2,core=False,fresh=False);rows.update(packet(a,new,2,q=False,core=False,fresh=False))
 r.event(cl(2),observations={'A':observation('A',cl(2),105),'B':observation('B',cl(2),101)},stocks=rows)
 before=dict(capital=sum(D(z['qty'])*a.market.prices[z['sid']] for z in a.layers if z['qty']),available=a.available,quantities={s:a.quantity(s) for s in old})
 rows=packet(a,old,3,core=False,fresh=False);rows.update(packet(a,new,3,core=False))
 r.event(cl(3),observations={'A':observation('A',cl(3),105),'B':observation('B',cl(3),105)},stocks=rows)
 return r,old,new,before

class KChange(Revision):
 def test_32_K_growth_zero_cash_gap_no_old_reduction(self):
  r,old,new,before=k_scene(1);a=r.account;plan=r.lifecycle[-1]['allocation']
  self.assertEqual(list(a.policy.k),['A','B']);self.assertEqual(plan['needed'],0);self.assertEqual(plan['reductions'],[]);self.assertFalse(a.exits)
  self.assertEqual(a.available,before['available']);self.assertEqual({s:a.quantity(s) for s in old},before['quantities']);self.assertEqual(before['capital'],D(799200))
  r.event(op(4),is_open=True);self.assertTrue(a.quantity(new[0]));self.assertEqual({s:a.quantity(s) for s in old},before['quantities'])
  self.keep('32_K_zero_gap_no_sale',dict(before=before,new_target=a.policy.targets('A'),actual_demand=plan,state=r.observable(op(4)),old_capital_unchanged=True))
 def test_33_K_growth_positive_gap_only_bounded_excess_S_sale(self):
  r,old,new,before=k_scene(2);a=r.account;plan=r.lifecycle[-1]['allocation'];self.assertGreater(plan['needed'],0)
  self.assertTrue(all(x['allocation_class']=='S_excess' for x in plan['reductions']))
  scheduled=sum(x['capital'] for x in plan['reductions']);net=sum(x['estimated_net'] for x in plan['reductions']);excess=before['capital']-a.policy.targets('A')
  rounding_bound=sum(a.market.prices[x['sid']] for x in plan['reductions'])
  self.assertGreaterEqual(net,plan['needed']);self.assertLessEqual(net-plan['needed'],rounding_bound);self.assertLessEqual(scheduled,excess);self.assertLess(scheduled,excess/2)
  self.assertEqual(a.available,before['available']);self.assertEqual({s:a.quantity(s) for s in old},before['quantities'])
  old_after_requested=before['capital']-scheduled;self.assertGreater(old_after_requested,a.policy.targets('A'))
  r.event(op(4),is_open=True);self.assertTrue(all(a.quantity(s)>0 for s in new))
  self.keep('33_K_positive_gap_bounded',dict(before=before,plan=plan,scheduled_mark_capital=scheduled,estimated_net=net,exact_cash_gap=plan['needed'],rounding_bound=rounding_bound,old_paper_excess=excess,old_capital_after_actual_sale=sum(D(a.quantity(s))*a.market.prices[s] for s in old),state=r.observable(op(4))))
 def test_34_price_support_failure_still_mandatory_exit(self):
  r,old,new,before=k_scene(1);a=r.account;self.assertFalse(a.exits)
  rows=packet(a,old,4,core=False,fresh=False);rows.update(packet(a,new,4,core=False,fresh=False))
  r.event(cl(4),observations={'A':observation('A',cl(4),80,.2),'B':observation('B',cl(4),105)},stocks=rows)
  self.assertFalse(a.policy.scopes['A'].support);self.assertEqual(set(a.exits),set(old));self.assertEqual(sum(e.remaining for e in a.policy.locks.values()),sum(a.quantity(s) for s in old))
  self.assertEqual(a.available,before['available']);self.keep('34_support_failure_mandatory',r.observable(cl(4)))
 def test_35_unsupported_funding_and_G_subset_atomically_block(self):
  # Multi-order downgrade: do not silently cancel every order or retain a
  # capacity-violating subset. Neither cash nor order fields may change.
  r=SyntheticRunner();a=r.account;ss=fixtures(a,3,lambda i:'A',50,D('47.5'));proof(r,'G',0);allow(a.policy,'A',10,True);activate(a,ss)
  for i in intents(a,ss):a.submit(i,op(1))
  a.policy.scopes['A'].permit=False;before=digest(a.exported(op(1)))
  with self.assertRaisesRegex(UnsupportedOperation,'multi-order G fallback'):a.revalidate_batch(op(1)+timedelta(minutes=1))
  self.assertEqual(before,digest(a.exported(op(1))));self.assertFalse(a.cancel_requests)
  # Multi-layer old-G fee allocation remains unsupported; all planning is
  # rejected BEFORE the first native reduction/exit request.
  t=SyntheticRunner();b=t.account;sid=fixtures(b,1,lambda i:'OLD',50,D('47.5'))[0];proof(t,'G',0)
  b.submit(intents(b,[sid])[0],op(1));b.fill_buy(sid,win(b,sid,op(1),400,'first-layer','buy'));b.ack_buy_cancel(sid)
  j=b.intent(sid,clock(1),receipt='second-layer',core=False,cp_floor=D('47.5'));b.submit(j,op(2));b.fill_buy(sid,win(b,sid,op(2),200,'second-layer','buy'));b.ack_buy_cancel(sid)
  others=fixtures(b,7,lambda i:'O'+str(i//2),100,95,cl(1),'O');t.opening(intents(b,others,1),op(2))
  fresh=fixtures(b,8,lambda i:'NEW',160,152,cl(2),'N');allow(b.policy,'NEW',30,True);activate(b,fresh);before_fund=digest(b.exported(cl(2)))
  with self.assertRaisesRegex(UnsupportedOperation,'multi-layer funding'):b.funding_reductions(intents(b,fresh,2),clock(2))
  self.assertEqual(before_fund,digest(b.exported(cl(2))));self.assertFalse(b.exits)
  self.keep('35_unsupported_atomic_guards',dict(G_subset_unchanged_digest=before,multi_layer_funding_unchanged_digest=before_fund,declared_unsupported=True))

def main():
 root=O/'runs'/(sys.argv[1] if len(sys.argv)>1 else 'attempt-001');root.mkdir(parents=True,exist_ok=False);KChange.root=root
 IO.prepare_targets(dict(final=root/'RESULTS.json',checkpoint=root/'checkpoints'/'probe.pkl',failure=root/'failure'/'ERROR.json'))
 for p in O.glob('*.py'):IO.write_bytes(root/'source'/p.name,p.read_bytes())
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(KChange))
 report=dict(contract=COMPOSITE,adapter_sha256=sha(O/'native_capital.py'),tests=result.testsRun,passed=result.wasSuccessful(),failures=[dict(test=str(t),trace=v) for t,v in result.failures+result.errors],historical_paths=0)
 IO.write_json(root/'RESULTS.json',report);print(json.dumps(report,indent=2));return not result.wasSuccessful()
if __name__=='__main__':raise SystemExit(main())
