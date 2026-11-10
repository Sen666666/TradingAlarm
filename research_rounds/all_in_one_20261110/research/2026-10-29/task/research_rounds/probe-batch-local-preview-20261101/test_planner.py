import unittest,copy,json
from pathlib import Path
from types import SimpleNamespace as NS
from decimal import Decimal as D
import planner as P

AT=P.J.M.N.iso('2023-01-20T09:30:00+08:00');DEC=P.J.M.N.iso('2023-01-19T15:10:00+08:00')
RULES=json.loads(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json').read_text())
sd=next(x['schedule'] for x in RULES['fee_versions']['SZSE_CHINEXT'] if x['from']<='2023-01-20' and (not x.get('to') or x['to']>'2023-01-20'))
SCHEDULE=P.J.LR.L.FeeSchedule(sd['schedule_id'],tuple(P.J.LR.L.FeeComponent(**x) for x in sd['components']))
def sector(s,level=0):return P.N.Sector('E-'+s,0,level=level,active=True,attempt='A-'+s,status=['probe','confirmed','expanded'][level],episode_started=0)
def state(levels=None,**kwargs):
    levels=levels or {'S':0};return P.State(cash=kwargs.pop('cash',1000000),sectors={s:sector(s,l) for s,l in levels.items()},**kwargs)
def item(sid,sec,rank=0,role='mobile',p='10',floor='9.9',target=100,budget=None,minimum=100,step=100):
    p=D(p);floor=D(floor);rule=P.J.LR.L.QuantityRule('dated-test',minimum,step,step,True,1)
    i=dict(sid=sid,role=role,kind='core' if role=='core' else 'add',rank=rank,score=100-rank,clock=NS(decision_at=DEC,earliest_execution_at=AT),quote=NS(par_value=D(1)),floor=floor,budget=D(str(budget)) if budget is not None else D(20000),cap=target,weight=1.,epoch=('E',1) if role=='core' else None,CP1_id=None if role=='core' else sid+'-canonical',CP1_trace=None if role=='core' else dict(formation_start_exclusive='2023-01-18'))
    if role=='core':i['risk_budget']=D(2500)
    x,why=P.LR.preview(i,p/(1+P.LR.SLIP),D(1),rule,SCHEDULE)
    if x:x['known_open']=p/(1+P.LR.SLIP)
    i['_preview']=x;i['_preview_failure']=why
    return i
def assign(s,items,sec):
    for i in items:s.sector_by_sid[i['sid']]=sec[i['sid']]
    return s
def simple_orders(r):return [(x['sid'],x['role'],x['pool'],x['quantity'],x['fee']) for x in r['orders']]

class Cases(unittest.TestCase):
 def test_01_full_target_route_and_evolving_prefix_reversal(self):
    lot=P.N.Lot('old','OLD','O','E-O','probe',100,80,65,attempt='A-O')
    s=state({'S':1,'O':0},cash=990000,lots=[lot],prices={'OLD':100});i=item('X','S',p='30.015',floor='20.015',target=500)
    assign(s,[i],{'X':'S'});r=P.plan(s,[i],AT,'two_pass');self.assertEqual((r['orders'][0]['pool'],r['orders'][0]['quantity']),('confirmed',500))
    s=state({'A':0,'X':1});a=item('A','A',p='49.8249',floor='39.8449',target=400);x=item('X','X',rank=1,p='30.015',floor='20.015',target=300);assign(s,[a,x],{'A':'A','X':'X'})
    baseline=P.plan(s,[a,x],AT,'single_pass');new=P.plan(s,[a,x],AT,'two_pass')
    self.assertEqual([(o['pool'],o['quantity']) for o in baseline['orders']],[('probe',400),('confirmed',300)])
    self.assertEqual([(o['pool'],o['quantity']) for o in new['orders']],[('probe',400),('probe',100)])
 def test_02_core_mobile_collision_receipt_and_no_fill_rearming(self):
    s=state();c=item('X','S',role='core',target=100);m=item('X','S',target=500);assign(s,[c,m],{'X':'S'})
    r=P.plan(s,[m,c],AT);self.assertEqual([(x['role'],x['quantity']) for x in r['orders']],[('core',100)]);self.assertEqual(r['proposed_stock_receipt_consumptions'],[])
    self.assertEqual(P.digest(s),P.digest(s));self.assertEqual(simple_orders(r),simple_orders(P.plan(s,[m,c],AT)))
    c=item('X','S',role='core',target=100,budget='500');r=P.plan(s,[c,m],AT);self.assertEqual(r['orders'][0]['role'],'mobile');self.assertEqual(r['proposed_stock_receipt_consumptions'],['X-canonical'])
    old=copy.deepcopy(s);old.consumed.add('X-canonical');self.assertFalse(P.plan(old,[m],AT)['orders'])
 def test_03_frozen_targets_gap_and_stable_original_priority(self):
    s=state({'S':0,'T':0});c=item('C','S',role='core',p='100',floor='50',target=100);m=item('M','T',p='250',floor='240',target=100);assign(s,[c,m],{'C':'S','M':'T'})
    r=P.plan(s,[c,m],AT);self.assertFalse(r['orders']);self.assertTrue(all(x['_preview'] is None for x in [c,m]))
    a=item('A','S',rank=0);b=item('B','T',rank=1);assign(s,[a,b],{'A':'S','B':'T'});self.assertEqual(simple_orders(P.plan(s,[a,b],AT)),simple_orders(P.plan(s,[b,a],AT)))
    gap=item('G','S',p='30',floor='10',target=100,budget='2000');assign(s,[gap],{'G':'S'});self.assertFalse(P.plan(s,[gap],AT)['orders'])
 def test_04_dated_minimum_step_and_fill_granularity(self):
    s=state();i=item('STAR','S',p='50',floor='45',target=201,minimum=200,step=1);assign(s,[i],{'STAR':'S'});r=P.plan(s,[i],AT);self.assertEqual(r['first_pass'][0]['quantity'],200);self.assertEqual(r['orders'][0]['quantity'],201)
    bad=item('STAR','S',target=100,minimum=200,step=1);self.assertFalse(P.plan(s,[bad],AT)['orders'])
    ordinary=item('A','S',target=201);assign(s,[ordinary],{'A':'S'});self.assertEqual(P.plan(s,[ordinary],AT)['orders'][0]['quantity'],200)
 def test_05_fee_aggregation_and_fee_adjusted_hard_cap(self):
    s=state();i=item('A','S',target=1000);assign(s,[i],{'A':'S'});r=P.plan(s,[i],AT);o=r['orders'][0]
    self.assertEqual(o['fee'],P.LR.fees(1000,D(10),SCHEDULE,'buy',D(1)));self.assertLess(o['fee'],2*P.LR.fees(100,D(10),SCHEDULE,'buy',D(1)))
    s=state(cash=1000,decision_nav=1000);j=item('B','S',p='.2',floor='.19',target=100,budget='20');assign(s,[j],{'B':'S'});self.assertFalse(P.plan(s,[j],AT)['orders'])
 def test_06_failed_candidate_migration_cancel_pending_and_old_attempt(self):
    lot=P.N.Lot('old','OLD','S','E-S','probe',2000,9,9.9,attempt='A-S')
    s=state({'S':1},cash=0,receivables=980000,lots=[lot],prices={'OLD':10});i=item('X','S');assign(s,[i],{'X':'S'});r=P.plan(s,[i],AT);self.assertFalse(r['orders']);self.assertEqual(r['final_state']['lots'][0]['pool'],'confirmed');self.assertTrue(r['migrations'][0]['result'])
    pending=P.N.Order('pending','P','S','E-S','probe',100,10,9.9,0,status='cancel_pending',attempt='A-S')
    t=state({'S':1},cash=10000,receivables=970000,lots=[lot],orders={'pending':pending},prices={'OLD':10});assign(t,[i],{'X':'S'});r=P.plan(t,[i],AT);self.assertFalse(r['migrations'][0]['result']);self.assertEqual(r['final_state']['lots'][0]['pool'],'probe');self.assertEqual(r['cash_reserve'],1000)
    old=copy.deepcopy(lot);old.attempt='OLD';t=state({'S':1},cash=0,receivables=980000,lots=[old],prices={'OLD':10});assign(t,[i],{'X':'S'});self.assertEqual(P.plan(t,[i],AT)['final_state']['lots'][0]['pool'],'probe')
 def test_07_original_input_purity_and_fixed_plan_never_reroutes(self):
    s=state();i=item('A','S',target=1000);assign(s,[i],{'A':'S'});before=P.digest([s.view(),P.intent_view(i)]);r=P.plan(s,[i],AT);self.assertEqual(before,P.digest([s.view(),P.intent_view(i)]))
    bad=copy.deepcopy(r['orders']);bad[0]['quantity']=2000
    v=P.fixed_validation(s,[i],r['attempts'],bad,AT,r['migrations']);self.assertFalse(v['valid']);self.assertIn('original_minimum_step_or_frozen_target',str(v['failures']));self.assertEqual(before,P.digest([s.view(),P.intent_view(i)]))
    broken=copy.deepcopy(i);del broken['sid']
    with self.assertRaises(KeyError):P.plan(s,[broken],AT)
    self.assertEqual(before,P.digest([s.view(),P.intent_view(i)]))
 def test_08_all_minimum_or_no_order_and_budget_conservation(self):
    s=state({'A':0,'B':0,'C':0});items=[item(x,x,rank=n,role='core',p='190',floor='170',target=100,budget='19000') for n,x in enumerate(['A','B','C'])];assign(s,items,{x:x for x in ['A','B','C']})
    old=P.plan(s,items,AT,'single_pass');new=P.plan(s,items,AT);self.assertEqual(simple_orders(old),simple_orders(new));self.assertEqual(len(new['orders']),2);self.assertLessEqual(new['nominal_risk'],.005*(1000000-float(new['fees'])))
    s.cash=0;s.receivable_equity=1000000;self.assertFalse(P.plan(s,items,AT)['orders']);self.assertFalse(P.plan(s,items,AT,'single_pass')['orders'])
 def test_native_single_pass_identity_single_intent(self):
    for role in ['core','mobile']:
        s=state();i=item('X','S',role=role,target=100);assign(s,[i],{'X':'S'});self.assertEqual(simple_orders(P.plan(s,[i],AT,'single_pass')),simple_orders(P.plan(s,[i],AT)))
 def test_native_single_pass_identity_initial_minimum_batch(self):
    s=state({'A':0,'B':0});items=[item(x,x,rank=n,role='core',target=100) for n,x in enumerate(['A','B'])];assign(s,items,{'A':'A','B':'B'});a=P.plan(s,items,AT,'single_pass');self.assertEqual([o['quantity'] for o in a['orders']],[100,100]);self.assertEqual(simple_orders(a),simple_orders(P.plan(s,items,AT)))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Cases);r=unittest.TextTestRunner(verbosity=2).run(suite)
    P.O.joinpath('SYNTHETIC_RESULTS.json').write_text(json.dumps(dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),passed=r.wasSuccessful(),scope='8 reviewer groups plus 2 native single-pass identities; pure allocation projections, no financial account'),indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
