"""R2 adversarial repairs and native scheduling. No historical account paths."""
import sys,unittest,json,pickle,subprocess
from datetime import timedelta
from decimal import Decimal as D
from dataclasses import asdict
from test_native import Cases,fixtures,proof,intents,clock,op,cl,win,allow,activate
from native_capital import SyntheticRunner,encode,digest
from imports_native import IO,O,T,COMPOSITE,sha

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

def main():
 root=O/'runs'/(sys.argv[1] if len(sys.argv)>1 else 'attempt-001');root.mkdir(parents=True,exist_ok=False);Revision.root=root
 IO.prepare_targets(dict(final=root/'RESULTS.json',checkpoint=root/'checkpoints'/'probe.pkl',failure=root/'failure'/'ERROR.json'))
 for p in O.glob('*.py'):IO.write_bytes(root/'source'/p.name,p.read_bytes())
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Revision))
 out=dict(contract=COMPOSITE,adapter_sha256=sha(O/'native_capital.py'),tests=result.testsRun,passed=result.wasSuccessful(),failures=[dict(test=str(t),trace=v) for t,v in result.failures+result.errors],historical_paths=0)
 IO.write_json(root/'RESULTS.json',out);print(json.dumps(out,ensure_ascii=False,indent=2));return not result.wasSuccessful()
if __name__=='__main__':raise SystemExit(main())
