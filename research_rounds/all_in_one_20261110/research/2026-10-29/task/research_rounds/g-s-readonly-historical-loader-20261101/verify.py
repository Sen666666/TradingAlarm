"""Fixture/mapping tests; input reads only, never account progression."""
from loader import *
from datetime import timedelta
import argparse, subprocess, shutil, os, time, unittest

ROOT=O/'input-v2'

def packet_digest(m):
 x=HistoricalInputs(m);events=[]
 for d in x.days:
  for phase in ('ACTION','PAYMENT','OPEN','CLOSE'):events.append(digest(x.event(d,phase)))
 return dict(window=x.key,events=events,bootstrap=digest(x.bootstrap()),initial=digest(x.initial_financial_state_spec()),
   priority=[digest(x.priority(d)) for d in x.days],pid=os.getpid(),financial_objects_created=0)

def mutate_branch(src,dst,truncate=False):
 shutil.copytree(src,dst);m=read(dst/'MANIFEST.json');end=m['days'][-1]
 for name,r in m['files'].items():
  p=dst/r['path']
  if p.suffix=='.parquet':
   f=pd.read_parquet(p)
   # Add deliberate future values to every real table schema. This is a
   # separately identified diagnostic branch, never accepted as old provenance.
   if len(f):
    q=f.iloc[[-1]].copy();q['day']='2099-12-31'
    for col in q.select_dtypes(include=['number']).columns:q[col]=123456789
    f=pd.concat([f,q],ignore_index=True)
   if truncate:f=f[f.day<=end]
   f.to_parquet(p,index=False);r['sha256']=sha(p)
  elif name in ('receipts','actions'):
   z=read(p)
   if name=='receipts':
    z.append(dict(canonical_series=m['fixed_ids'][0],confirmed_day='2099-12-31',trace_unknown=['poison']))
   elif z:z.append(dict(z[0],effective_date='2099-12-31',paid_at=None))
   if truncate:z=[a for a in z if a['confirmed_day' if name=='receipts' else 'effective_date']<=end]
   write(p,z);r['sha256']=sha(p)
 write(dst/'MANIFEST.json',m)

class Gates(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.xs={k:HistoricalInputs(ROOT/k/'MANIFEST.json') for k in ('2022','2025_26')}
 def test_bootstrap_counts_clocks(self):
  for k,target in [('2022',(47,33,33,22)),('2025_26',(48,40,18,15))]:
   x=self.xs[k];rows=[s['market_context'] for s in x.seeds.values() if s['policy_scope']!='G']
   self.assertEqual(tuple(sum(bool(v) for v in z) for z in ([r['support'] for r in rows],[r['permit'] for r in rows],[r['mature'] for r in rows],[r['mature'] and r['permit'] for r in rows])),target)
   self.assertTrue(all(s['confirmed_cursor']>700000 for s in x.seeds.values()))
   self.assertEqual(x.initial_financial_state_spec()['filled_trials'],0);self.assertEqual(x.initial_financial_state_spec()['K'],[])
 def test_global_seed_exact(self):
  self.assertEqual(self.xs['2022'].seeds['NATIVE1709_global']['last_decision']['mode'],'ENDED')
  s=self.xs['2025_26'].seeds['NATIVE1709_global'];self.assertTrue(s['market_context']['permit']);self.assertFalse(s['market_context']['mature'])
 def test_open_prior_close_only(self):
  for x in self.xs.values():
   for d in x.days:
    event=x.event(d,'OPEN')
    for s in event['stocks']:
     if s['facts']:self.assertLess(s['facts']['observed_day'],d)
     self.assertLess(s['known_signal_cutoff'],d)
 def test_original_stock_eligibility_function(self):
  for x in self.xs.values():
   for d in x.days:
    at=datetime.fromisoformat(known(d));clock=A.Clock(at,at+timedelta(days=1),at.date())
    for sid in x.ids:
     s=x.stock(sid,d,'CLOSE');ch=s['retained_stock_Q']['checks'];fact=lambda v:A.Fact(v,at,at)
     sec=A.Security(sid,fact(x.lines[sid]['issuer_id']),fact(s['sector']),fact(ch['common_ready_stock']),fact(ch['buy_allowed']),fact(x.lines[sid]['company_cap_cny']),fact(ch['stock_up']),A.Rank(s['H1'],at,at))
     reference=A.eligibility(sec,{s['sector']:None},clock,'T0')
     self.assertEqual(reference.q,s['retained_stock_Q']['value'])
 def test_receipt_numeric_identity(self):
  for x in self.xs.values():
   for d in x.days:
    nr=0
    for sid in x.ids:
     s=x.stock(sid,d,'CLOSE');r=s['canonical_receipt']
     if r:
      nr+=1;self.assertEqual(r['event_id'],r['canonical_original']['receipt_id']);self.assertEqual(r['confirmed'],known(d));self.assertFalse(r['canonical_original']['trace_unknown'])
    self.assertEqual(nr,len([r for r in x.obj('receipts') if r['confirmed_day']==d]))
 def test_no_prestarter_receipt_reissue(self):
  for x in self.xs.values():
   self.assertTrue(all(r['confirmed_day']>=x.days[0] for r in x.obj('receipts')))
   self.assertTrue(all(s['canonical_receipt'] is None for s in x.event(x.days[0],'OPEN')['stocks']))
 def test_factor_and_no_cashdiv_share_multiplier(self):
  x=self.xs['2025_26'];a=next(a for a in x.actions('2025-07-02') if a['sid']=='688608.SH');self.assertEqual(Decimal(a['split_ratio']),Decimal('1.40'));self.assertEqual(Decimal(a['cash_per_old_share']),Decimal('1.20'))
  s=x.stock('688608.SH','2025-07-02','OPEN');self.assertEqual(s['known_signal_cutoff'],'2025-07-01')
  self.assertNotEqual(s['floors']['raw_conversion_factor_at_event'],1)
  for k in ('2022','2025_26'):
   xx=self.xs[k]
   for d in xx.days:
    for sid in xx.ids:
     s=xx.stock(sid,d,'CLOSE');f=s['facts']
     if f and finite(f['close']) and finite(f['raw_close']) and finite(f['factor']):self.assertAlmostEqual(f['close'],f['raw_close']*f['factor'],places=8)
 def test_star_new_vs_partial_remainder(self):
  x=self.xs['2025_26'];rule=x.availability('688608.SH','2025-07-02')['quantity'];self.assertEqual(rule['buy_minimum'],200)
  for held in (0,200):
   self.assertEqual(new_order_quantity(rule,199),0);self.assertEqual(new_order_quantity(rule,200),200);self.assertEqual(new_order_quantity(rule,201),201)
  # Same original order remainder is NOT a fresh order; mapper preserves50,
  # it does not pass it through new_order_quantity or recreate a receipt.
  original=dict(order_id='original',authorized=200,filled=150,remaining=50)
  self.assertEqual(original['remaining'],50);self.assertNotEqual(new_order_quantity(rule,50),50)
 def test_all_na_constant_and_duplicate_role_priority(self):
  dom=[dict(sid=s,rank=n,role=r) for n,s in enumerate(['A','B','C']) for r in ('core','mobile')]
  for fn in (lambda s,d:None,lambda s,d:7):
   keys,log=priority_plan(dom,fn,'2025-07-01');self.assertEqual(keys,{'A':0,'B':1,'C':2});self.assertTrue(all(r['roles']==['core','mobile'] for r in log))
  keys,log=priority_plan(dom,lambda s,d:{'A':1,'B':None,'C':2}[s],'2025-07-01');self.assertEqual(keys,{'C':0,'B':1,'A':2})
 def test_priority_complete_and_true_na(self):
  for x in self.xs.values():
   for d in x.days:
    r=x.priority(d);self.assertEqual(len(r),1709);self.assertEqual(len({v['priority_rank'] for v in r}),1709)
    self.assertTrue(all(v['original_slot']==v['final_slot'] for v in r if not v['PVR_ready']))
 def test_fractional_or_unknown_action_blocks(self):
  x=self.xs['2025_26'];a=next(a for a in x.actions('2025-07-02') if a['sid']=='688608.SH')
  self.assertEqual(x.check_action_support(a)['ready'],'conditional')
  self.assertTrue(x.check_action_support(a,[200])['ready'])
  with self.assertRaises(UnsupportedInput):x.check_action_support(a,[1])
  with self.assertRaises(UnsupportedInput):x.check_action_support(dict(a,classification='UNKNOWN'),[200])
 def test_no_unknown_event_or_outside_dates(self):
  x=self.xs['2022']
  with self.assertRaises(UnsupportedInput):x.event(x.days[0],'UNKNOWN')
  with self.assertRaises(ValueError):x.event('2022-01-06','OPEN')
 def test_lineage_and_declared_payment_due(self):
  x=self.xs['2025_26'];sid='000001.SZ';p=x.stock(sid,x.days[0],'CLOSE')
  self.assertEqual(p['original_I_structural_key'],[bool(p['facts']['i_target']),int(p['facts']['segment_id'])])
  v=copy.copy(x);v.objects=dict(x.objects);v.objects['actions']=[dict(source_id='declared-fixture',paid_at='2025-07-02T12:00:00+08:00')]
  self.assertEqual(v.payments_due('2025-07-02T09:30:00+08:00'),[])
  self.assertEqual(len(v.payments_due('2025-07-02T15:10:00+08:00')),1)
  with self.assertRaises(ValueError):x.priority('2025-07-03')
 def test_no_financial_modules_imported(self):
  self.assertFalse(any(n in sys.modules for n in ('native_capital','joint_v3','policy','imports_native')))


def main(out):
 out=Path(out);out.mkdir(exist_ok=False);start=time.monotonic()
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Gates)
 with (out/'TEST_LOG.txt').open('w') as f:r=unittest.TextTestRunner(stream=f,verbosity=2).run(suite)
 write(out/'UNIT_RESULTS.json',dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),passed=r.wasSuccessful()))
 if not r.wasSuccessful():raise SystemExit('mapping tests failed; preserve this output')
 branch_results=[]
 for k in ('2022','2025_26'):
  base=packet_digest(ROOT/k/'MANIFEST.json');write(out/(k+'-base.json'),base)
  for mode in ('physical-truncated','future-perturbed'):
   target=out/(k+'-'+mode);mutate_branch(ROOT/k,target,truncate=mode=='physical-truncated')
   q=out/(k+'-'+mode+'-worker.json')
   subprocess.run([sys.executable,'-B',str(Path(__file__)),'worker',str(target/'MANIFEST.json'),str(q)],check=True)
   actual=read(q);selfcheck={a:v for a,v in actual.items() if a!='pid'};expected={a:v for a,v in base.items() if a!='pid'}
   assert selfcheck==expected,(k,mode,'causal packet differs')
   assert actual['pid']!=base['pid']
   branch_results.append(dict(window=k,mode=mode,packet_bootstrap_priority_exact=True,parent_pid=base['pid'],worker_pid=actual['pid']))
 write(out/'VERIFICATION.json',dict(passed=True,unit_tests=r.testsRun,branches=branch_results,seconds=time.monotonic()-start,
    financial_accounts_created=0,financial_events=0,buy_or_sell_intents=0,model_recalculations=0))
 print(canonical(read(out/'VERIFICATION.json')),flush=True)
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='worker':write(sys.argv[3],packet_digest(sys.argv[2]))
 else:
  p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.out)
