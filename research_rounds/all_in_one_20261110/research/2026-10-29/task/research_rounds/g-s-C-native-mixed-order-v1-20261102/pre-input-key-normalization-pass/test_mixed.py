"""Affected mixed-role native cases only; no historical account events."""
from test_native import *
from dispatch_order import freeze_priority,dispatch_key
import argparse

class Mixed(unittest.TestCase):
 root=None;records={}
 def keep(self,name,r,at,**extra):
  x=dict(state=r.observable(at),extra=extra);self.records[name]=x;IO.write_json(self.root/(name+'.json'),x,encoder=encode)
 def test01_core_mobile_both_actual_orders(self):
  for mode in ('C10','C_BATCH20'):
   r=Runner(mode);ss=fixtures(r,3,sector=lambda j:'S'+str(j));rows=packet(r,ss,0,priorities={s:(j,0,s) for j,s in enumerate(ss)})
   rows[ss[0]]['receipt']=None;rows[ss[1]]['core_event']=False
   close(r,0,rows,{'G':obs(r,'G',0)});r.event(op(1),is_open=True)
   a=r.account;by={z['sid']:a.capital_meta[z['id']] for z in a.layers};self.assertEqual(by[ss[0]]['role'],'core');self.assertEqual(by[ss[0]]['purpose'],'T')
   self.assertEqual(by[ss[1]]['role'],'mobile');self.assertEqual(by[ss[2]]['role'],'mobile');self.assertEqual(len(a.layers),3)
   b=next(x for x in a.native_callbacks if x['kind']=='entire_C_batch_reserved_before_windows');self.assertEqual([s for s,_ in b['orders']],ss[1:]+ss[:1]);self.assertEqual([f.security_id for f in a.fills],ss[1:]+ss[:1])
   self.assertEqual(len(a.policy.consumed),2);self.assertLessEqual(a.quantity(ss[0])*a.market.prices[ss[0]],a.policy.nd*D('.02'))
   self.keep('01_mixed_'+mode,r,op(1),dispatch=[s for s,_ in b['orders']])
 def test02_core_only_cannot_bypass_permission_or_be_large(self):
  r=Runner('C_BATCH20');ss=fixtures(r,1,sector='S',price=20,floor=19);rows=packet(r,ss,0,receipt=False,priorities={ss[0]:(0,0,ss[0])})
  close(r,0,rows,{});r.event(op(1),is_open=True);self.assertFalse(r.account.buys);self.assertFalse(r.account.positions)
  close(r,1,packet(r,ss,1,receipt=False,priorities={ss[0]:(0,0,ss[0])}),{'S':obs(r,'S',1)})
  r.event(op(2),is_open=True);a=r.account;z=a.layers[0];m=a.capital_meta[z['id']];self.assertEqual((m['purpose'],m['role'],m['pool']),('T','core','probe'))
  self.assertLessEqual(D(z['qty'])*a.market.prices[ss[0]],D('.02')*a.policy.nd);self.assertFalse(a.policy.consumed);self.keep('02_core_permission',r,op(2))
 def test03_confirmed_failure_trial_core_zero_fill_suppresses_mobile(self):
  r=Runner('C_BATCH20');ss=fixtures(r,1,price=99,floor=94);rows=packet(r,ss,0,priorities={ss[0]:(0,0,ss[0])});rows[ss[0]]['cp_floor']=D('98.8')
  close(r,0,rows,{'G':obs(r,'G',0)});r.account.mark(ss[0],D('98.5'),op(1),'S0',False)
  r.event(op(1),is_open=True,capacities={ss[0]:0});a=r.account;o=a.buys[ss[0]];m=a.supports[o.order_id]
  self.assertEqual((m['use'],m['role'],m['pool']),('T','core','probe'));self.assertEqual(len(a.buys),1);self.assertFalse(a.layers);self.assertFalse(a.policy.consumed)
  self.assertFalse(any(x['sid']==ss[0] for x in r.authority.orders.values()));self.keep('03_C_failed_core_reserved_zero',r,op(1))
 def test04_trial_core_risk_failure_falls_back_mobile_once(self):
  r=Runner('C_BATCH20');ss=fixtures(r,1,sector='S',price=50,floor=10);rows=packet(r,ss,0,priorities={ss[0]:(0,0,ss[0])});rows[ss[0]]['cp_floor']=D('49.8')
  close(r,0,rows,{'S':obs(r,'S',0)});r.event(op(1),is_open=True);a=r.account;m=next(iter(a.capital_meta.values()))
  self.assertEqual((m['purpose'],m['role'],m['pool']),('T','mobile','probe'));self.assertEqual(len(a.layers),1);self.assertEqual(len(a.policy.consumed),1)
  self.assertEqual(len([x for x in a.audit_log if x['kind']=='reserve']),1);self.keep('04_trial_fallback',r,op(1))
 def test05_missing_H1_and_PVR_have_distinct_semantics(self):
  # PVR true NA stays its original slot; equal ready values use original H1.
  ids=['NA','B','C'];vals={'NA':None,'B':7.,'C':7.};domain=[dict(sid=s,rank=j,role='mobile') for j,s in enumerate(ids)]
  keys,log=B.priority_plan(domain,lambda s,d:vals[s],'fixture-day');self.assertEqual(keys,dict(NA=0,B=1,C=2));self.assertFalse(log[0]['PVR_ready'])
  r=Runner('C_BATCH20');ss=fixtures(r,3,sector=lambda j:'S'+str(j));rows=packet(r,ss,0,core=False,priorities={s:(keys[k],0,s) for s,k in zip(ss,ids)})
  rows[ss[2]]['q']=None # Original retained stock-H1 readiness unknown.
  close(r,0,rows,{'G':obs(r,'G',0)});r.event(op(1),is_open=True);self.assertEqual(set(r.account.positions),set(ss[:2]))
  self.keep('05_NA_stock_qualification',r,op(1),original_PVR_log=log)
 def test06_industry_H1_unknown_blocks_new_not_core_bypass(self):
  r=Runner('C_BATCH20');ss=fixtures(r,2,sector=lambda j:'S'+str(j));rows=packet(r,ss,0,priorities={s:(j,0,s) for j,s in enumerate(ss)});rows[ss[0]]['receipt']=None
  close(r,0,rows,{'G':obs(r,'G',0)},dict(S0=100,S1=None));self.assertEqual(r.close_stages[cl(0).isoformat()]['optional_status'],'blocked_unknown_H1')
  r.event(op(1),is_open=True);self.assertFalse(r.account.positions);self.assertFalse(r.account.buys);self.keep('06_industry_unknown',r,op(1))
 def test07_equal_industry_and_stock_scores_stable_ties(self):
  r=Runner('C_BATCH20');ss=fixtures(r,3,sector=lambda j:['Z','A','A'][j]);priority={ss[0]:(0,0,ss[0]),ss[1]:(1,0,ss[1]),ss[2]:(2,0,ss[2])}
  close(r,0,packet(r,ss,0,core=False,priorities=priority),{'G':obs(r,'G',0)},dict(A=10,Z=10));r.event(op(1),is_open=True)
  self.assertEqual([f.security_id for f in r.account.fills],ss[1:]+ss[:1]);self.keep('07_stable_ties',r,op(1))
 def test08_retained_native_sequence_not_current_rank(self):
  r=Runner('C_BATCH20');ss=fixtures(r,2,sector=lambda j:'S'+str(j));rows=packet(r,ss,0,priorities={ss[0]:(99,0,ss[0]),ss[1]:(0,0,ss[1])});rows[ss[0]]['receipt']=None;rows[ss[1]]['core_event']=False
  close(r,0,rows,{'G':obs(r,'G',0)})
  # A genuine native pre-reservation at its ORIGINAL earliest window. No fill
  # window is consulted before the rest of this batch reserves. This tests the
  # retained-order component; it is not a claimed normal cross-day GTC path.
  a=r.account;i=next(i for i in a.pending if i['sid']==ss[0]);x=a.submit(i,op(1),use='T');oid=x['order_id'];frozen=copy.deepcopy(a.supports[oid]['dispatch']);raw=copy.deepcopy(a.supports[oid]['priority'])
  r.event(op(1),is_open=True,capacities={ss[0]:0,ss[1]:10**8})
  batch=[x for x in a.native_callbacks if x['kind']=='entire_C_batch_reserved_before_windows'][-1]
  self.assertEqual([s for s,_ in batch['orders']],ss);self.assertEqual(a.supports[oid]['dispatch'],frozen);self.assertEqual(a.supports[oid]['priority'],raw);self.assertGreater(a.quantity(ss[1]),0)
  self.keep('08_retained_first',r,op(1),retained_order=oid,fixture_scope='original-clock native reserve before complete batch, no extended lifetime')
 def test09_typed_keys_preserve_numeric_order_and_reject_unknown(self):
  raw=[(10,0,'Z'),(2,0,'B'),(2,0,'A')];self.assertEqual(sorted(raw),sorted(raw,key=freeze_priority))
  for raw in [(None,),('ready',float('nan')),([],),(float('inf'),)]:
   with self.assertRaises(ValueError):freeze_priority(raw)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=HERE/'runs-mixed');args=p.parse_args();Mixed.root=args.out;args.out.mkdir(parents=True,exist_ok=True)
 t=time.monotonic();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Mixed));payload=dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),seconds=time.monotonic()-t,historical_account_events=0,scope='mixed-role native synthetic only')
 IO.write_json(args.out/'RESULTS.json',payload);print(json.dumps(payload));raise SystemExit(not result.wasSuccessful())
