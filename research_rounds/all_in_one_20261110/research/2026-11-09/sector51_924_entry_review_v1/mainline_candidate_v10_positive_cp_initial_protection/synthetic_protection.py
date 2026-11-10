"""Synthetic unit/integration and source audit only. Never instantiate historical Data."""
from pathlib import Path
import importlib.util,sys,types,copy,inspect,json,hashlib,tempfile
P=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('m10_test',P/'engine.py');e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
D=e.D;pd=e.pd;checks=[]
B=pd.Timestamp('2024-09-09');C=pd.Timestamp('2024-09-10');N=pd.Timestamp('2024-09-11');L=pd.Timestamp('2024-09-12')
def ok(name,c=True):assert c,name;checks.append(name)
def fixture():
 z=pd.Series(dict(raw_open=10,raw_close=10,adjustment_factor=1,source_kind='SYNTHETIC',source_path='SYNTHETIC',segment_id='0',observed_bar=True,price_eligible=True,volume_eligible=True,source_invalid=False,synthetic_event_bar=False))
 qr=e.m3.b.QuantityRule('SYNTHETIC',100,100,100,True,1)
 data=types.SimpleNamespace(sid_sector={'S':'SEC'},names={'S':'Synthetic'},events={},
  sectors={'SEC':pd.DataFrame({'state':[1]*4,'strength':[False]*4},index=[B,C,N,L])},
  cal=pd.DatetimeIndex([B,C,N,L]),days=[N],ids=[],stock=pd.DataFrame({'S':[1]*4},index=[B,C,N,L]))
 data.z=lambda s,d:z;data.m=lambda s,d:types.SimpleNamespace(M=0)
 data.f=lambda s,d:{'i_target':True,'i_floor':2}
 data.c=lambda s,d:{'receipt':False,'candidate':None}
 data.action=lambda s,d:[];data.getmeta=lambda s,d:(qr,None,None);data.fee=lambda s,d,q,p,side:D(5)
 x=e.Engine(data)
 a=dict(id='ROUND',sid='S',lots=[],exit=None,plan=None,cp=None,factor=D(1),ifloor=D(2),origin=e.m3.lineage(z),fees=D(0),cashflow=D(-2000),dividend=D(0),confirmed_history=True,add_count=1,seed_day=e.day(B),nav0=D(1200000))
 for k,(kind,role) in enumerate([('SEED','INITIAL'),('ADD','EXPANSION'),('SEED','EXPANSION')]):
  a['lots'].append(dict(id=str(k),kind=kind,capital_role=role,q=100,bought=e.day(B),floor=D(4)))
 x.active={'S':a};x.archive={'ROUND':a};x.cash=D(1200000)
 return x,a,z

def cp(a,d=C,floor=9):
 a['cp']=dict(id='CP-'+e.day(d)+'-'+str(floor),date=e.day(d),floor=D(floor),origin=a['origin'],consumed=False,invalid=False)
 return a['cp']
def adopt(x,a,d=C,floor=9):cp(a,d,floor);x.adopt_seed_protection(d)
def primed():
 x,a,z=fixture();adopt(x,a);return x,a,z

def real_close(x,d=C,prev=B):
 # Stub only unrelated planning/attribution; execute actual inherited CLOSE protection/receipt path.
 orig=e.m7.Engine.plan_transfers;e.m7.Engine.plan_transfers=lambda *args:None
 x.refresh_tickets=lambda d:[];x.register_pay=lambda d:None;x.attribute=lambda *args:None
 try:return x.close(d,prev)
 finally:e.m7.Engine.plan_transfers=orig

x,a,z=primed();l=a['lots'][0]
ok('positive_current_and_CP_adopts_INITIAL_only',bool(l.get('seed_cp')) and all('seed_cp' not in k for k in a['lots'][1:]))
ok('account_I_unchanged',a['ifloor']==2)
ok('exact_CP_net_formula',D(l['seed_cp']['net_at_CP'])==D(-2000)+D(300)*D(9)*(1-e.SLIP)-D(5))
ok('actual_layered_floor_not_all_CP',D(x.candidates[-1]['layered_pressure_after']['net'])<0 and D(l['seed_cp']['net_at_CP'])>0)
ok('layered_separate_commissions',sum(D(r['separate_lot_fee']) for r in x.candidates[-1]['layered_pressure_after']['lots'])==15)
for mode in ['cpzero','cpnegative','closezero','closenegative']:
 x,a,z=fixture();cp(a)
 if mode=='cpzero':a['cashflow']=-(D(300)*D(9)*(1-e.SLIP)-D(5))
 elif mode=='cpnegative':a['cashflow']=D(-2800)
 elif mode=='closezero':a['cashflow']=-(D(300)*D(10)*(1-e.SLIP)-D(5))
 else:a['cashflow']=D(-4000)
 x.adopt_seed_protection(C);ok('reject_'+mode,'seed_cp' not in a['lots'][0])
for mode in ['old','consumed','invalid','source','already_breached','prebuy','unknown_price']:
 x,a,z=fixture();c=cp(a)
 if mode=='old':c['date']=e.day(B)
 elif mode=='consumed':c['consumed']=True
 elif mode=='invalid':c['invalid']=True
 elif mode=='source':c['origin']=('OTHER',)
 elif mode=='already_breached':c['floor']=D(11)
 elif mode=='prebuy':a['lots'][0]['bought']=e.day(N)
 else:z['observed_bar']=False
 x.adopt_seed_protection(C);ok('reject_'+mode,'seed_cp' not in a['lots'][0])
x,a,z=fixture();a['lots'][0]['bought']=e.day(C);adopt(x,a)
ok('same_day_OPEN_buy_CLOSE_CP_allowed','seed_cp' in a['lots'][0])
x,a,z=primed();initial=copy.deepcopy(a['lots'][0]['seed_cp']);a['cp']['consumed']=True
x.exit_open(N)
ok('consumption_INVALIDATED_not_price_breach',a['cp']['invalid'] and not x.orders and a['lots'][0]['seed_cp']==initial)
x,a,z=primed();old=copy.deepcopy(a['lots'][0]['seed_cp']);adopt(x,a,N,8)
ok('SUPERSEDED_lower_new_CP_keeps_latched_constraint',a['lots'][0]['seed_cp']==old)
x,a,z=primed();adopt(x,a,N,D('9.5'))
ok('higher_fresh_CP_raises',D(a['lots'][0]['seed_cp']['floor'])==D('9.5'))
x,a,z=primed();old=copy.deepcopy(a['lots'][0]['seed_cp']);a['cashflow']=D(-9999);adopt(x,a,N,D('9.5'))
ok('losing_current_round_does_not_remove_or_raise_latch',a['lots'][0]['seed_cp']==old)
z['raw_open']=8;x.exit_open(N);ok('breach_executes_even_after_loss',x.orders[0]['reason']==e.REASON)
x,a,z=fixture();cp(a,B);x.adopt_seed_protection(C);ok('unadopted_superseded_old_never_retrieved','seed_cp' not in a['lots'][0])
x,a,z=primed();x.active={};x.archive={};b=fixture()[1];x.active={'S':b};x.archive={'ROUND':b}
cp(b,B);x.adopt_seed_protection(N);ok('new_round_lots_no_inherited_latch','seed_cp' not in b['lots'][0])

# Gap and equality use actual OPEN, with INITIAL-only grouping and provenance.
for raw in [D(8),D(9)]:
 x,a,z=primed();z['raw_open']=raw;x.exit_open(N)
 ok('OPEN_breach_inclusive_'+str(raw),x.orders[0]['reason']==e.REASON and x.orders[0]['qty']==100)
 ok('OPEN_real_fill_not_CP_'+str(raw),D(x.orders[0]['price'])==raw*(1-e.SLIP))
 ok('INITIAL_only_exit_'+str(raw),[l['id'] for l in a['lots']]==['1','2'])
 ok('one_fee_'+str(raw),a['fees']==5)
 ok('lot_reason_'+str(raw),x.orders[0]['lot_reasons']=={'0':e.REASON})
x,a,z=primed();z['raw_close']=8;real_close(x);z['raw_open']=12;x.exit_open(N)
ok('CLOSE_lock_survives_rebound',x.orders[0]['reason']==e.REASON and D(x.orders[0]['price'])==D(12)*(1-e.SLIP))
x,a,z=primed();z['raw_close']=8;x.d.c=lambda s,d:{'receipt':True,'candidate':7};real_close(x)
ok('old_line_breached_before_new_CP_and_not_rescued',a['lots'][0]['m10_locked']['phase']=='CLOSE' and D(a['lots'][0]['seed_cp']['floor'])==9)
x,a,z=fixture();x.d.c=lambda s,d:{'receipt':True,'candidate':9};z['raw_open']=8
x.exit_open(C);ok('no_future_CP_at_same_day_OPEN',not x.orders)
real_close(x);ok('actual_inherited_new_receipt_adopted',D(a['lots'][0]['seed_cp']['floor'])==9)
ok('holdings_effective_floor_matches_execution',next(r for r in x.holdings if r['lot_id']=='0')['effective_protection_signal']=='9' and next(r for r in x.holdings if r['lot_id']=='0')['baseline_I_signal']=='2')
z['raw_open']=D('8.5');x.exit_open(N);ok('exported_floor_is_actually_executed',x.orders[0]['lot_reasons']['0']==e.REASON)
x,a,z=fixture();x.d.c=lambda s,d:{'receipt':True,'candidate':11};real_close(x)
ok('actual_RECEIPT_ALREADY_BREACHED_not_adopted','seed_cp' not in a['lots'][0])

for why in ['I_INVALID','I_CLOSE_PROTECTION','TRIAL_SECTOR_FALSE']:
 x,a,z=primed();a['exit']=why;z['raw_open']=8;x.exit_open(N)
 ok('hard_account_precedence_'+why,len(x.orders)==1 and x.orders[0]['reason']==why and x.orders[0]['qty']==300)
x,a,z=primed();z['raw_open']=1;x.exit_open(N)
ok('hard_I_OPEN_precedence',x.orders[0]['reason']=='I_OPEN_PROTECTION' and x.orders[0]['qty']==300)
x,a,z=primed();a['lots'][1]['exit']='CP_CLOSE_PROTECTION';z['raw_open']=8;x.exit_open(N)
ok('mixed_CP_INITIAL_single_order',len(x.orders)==1 and x.orders[0]['reason']=='CP_LAYER_EXIT' and x.orders[0]['qty']==200 and a['fees']==5)
ok('mixed_per_lot_reasons',x.orders[0]['lot_reasons']=={'1':'CP_CLOSE_PROTECTION','0':e.REASON})
x,a,z=primed();a['lots'][0]['q']=150;z['raw_open']=8;x.exit_open(N)
ok('partial_legal_INITIAL_only',x.orders[0]['qty']==100 and a['lots'][0]['q']==50 and a['lots'][0]['m10_locked'])
x.exit_open(L);ok('partial_remainder_not_rounded_using_unprotected_lots',len(x.orders)==1 and a['lots'][0]['q']==50)
x,a,z=primed();a['lots']=a['lots'][:1];a['lots'][0]['q']=150;z['raw_open']=8;x.exit_open(N)
ok('full_position_odd_lot',x.orders[0]['qty']==150 and 'S' not in x.active)
x,a,z=primed();a['lots'][0]['q']=50;a['lots'][1]['q']=100;a['lots'][1]['exit']='CP_CLOSE_PROTECTION';z['raw_open']=8;x.exit_open(N)
ok('never_reduce_original_CP_order_for_new_odd_lot',x.orders[0]['qty']==100 and x.orders[0]['lots']==['1'] and a['lots'][0]['q']==50)
x,a,z=primed();a['lots'][0]['bought']=e.day(N);z['raw_open']=8;x.exit_open(N)
ok('T1_locked_no_sale',not x.orders and a['lots'][0]['m10_locked']);x.exit_open(L)
ok('T1_later_eligible_execution',x.orders[0]['qty']==100)
x,a,z=fixture();a['lots'][0]['q']=0;adopt(x,a);ok('zero_INITIAL_no_adoption','seed_cp' not in a['lots'][0])
a['lots']=[];x.adopt_seed_protection(C);ok('zero_round_no_liquidation_fee',x.layered_pressure(a,C)['lots']==[])

x,a,z=primed();x.d.sectors['SEC'].loc[C,'state']=0;real_close(x)
ok('sector_false_and_stock_one_unbroken_structure_retained',not a['lots'][0].get('m10_locked'))
x,a,z=fixture();x.capital_lots=[dict(day=e.day(C),sid='S',round_id='ROUND',lot_id='0')]
x.d.c=lambda s,d:{'receipt':True,'candidate':9};real_close(x)
ok('CAPITAL_LOTS_and_HOLDINGS_actual_effective_floor_agree',x.capital_lots[0]['effective_protection_signal']==next(r for r in x.holdings if r['lot_id']=='0')['effective_protection_signal']=='9')
x,a,z=fixture();a['dividend']=D(13);cp(a);seen=[]
def only_current(s,d):
 seen.append(d);assert d==C,'noncurrent quote read';return z
x.d.z=only_current;x.adopt_seed_protection(C)
ok('adoption_only_current_completed_close_no_lookahead',seen and all(d==C for d in seen))
ok('CP_net_includes_dividend',D(a['lots'][0]['seed_cp']['net_at_CP'])==D(-2000)+13+D(300)*D(9)*(1-e.SLIP)-5)

# Existing INITIAL non-M10 lock must not become quantity-constrained new exit.
x,a,z=primed();a['lots'][0]['q']=150;a['lots'][0]['exit']='BASELINE_EXISTING_LOCK';z['raw_close']=8
real_close(x);z['raw_open']=8;x.exit_open(N)
ok('baseline_INITIAL_exit_survives_same_CLOSE_M10_breach',x.orders[0]['qty']==150 and x.orders[0]['reason']=='CP_LAYER_EXIT' and x.orders[0]['lot_reasons']['0']=='BASELINE_EXISTING_LOCK')
x,a,z=primed();a['lots'][0]['q']=150;a['lots'][0]['exit']='BASELINE_EXISTING_LOCK';a['lots'][0]['bought']=e.day(N);z['raw_open']=8
x.exit_open(N);x.exit_open(L)
ok('baseline_INITIAL_lock_preserved_across_T1',x.orders[0]['qty']==150 and x.orders[0]['lot_reasons']['0']=='BASELINE_EXISTING_LOCK')
x,a,z=primed();z['raw_open']=8;x.exit_open(C)
ok('same_adoption_day_cannot_retroactively_act_at_OPEN',not x.orders)

# Unified signal coordinate: adjusted-coordinate comparison survives a raw-price/factor change.
x,a,z=primed();a['factor']=D(2);z['adjustment_factor']=2;z['raw_open']=D('4.6');x.exit_open(N)
ok('factor_change_no_false_raw_price_breach',not x.orders)
z['raw_open']=D('4.5');x.exit_open(L);ok('factor_change_correct_signal_breach',x.orders[0]['qty']==100 and D(x.orders[0]['price'])==D('4.5')*(1-e.SLIP))
x,a,z=primed();z['source_path']='OTHER'
try:real_close(x)
except e.Blocked:ok('source_change_fail_closed')
else:raise AssertionError('source change not blocked')

# Without any adopted INITIAL protection, existing economic OPEN results match baseline.
for mode in ['none','I','CPclose','CPopen','T1']:
 x,a,z=fixture();y,b,w=fixture()
 for eng,rd,bar in [(x,a,z),(y,b,w)]:
  if mode=='I':rd['exit']='I_INVALID'
  elif mode=='CPclose':rd['lots'][1]['exit']='CP_CLOSE_PROTECTION'
  elif mode=='CPopen':bar['raw_open']=3
  elif mode=='T1':rd['exit']='I_INVALID';rd['lots'][0]['bought']=e.day(N)
 x.exit_open(N);e.m7.Engine.exit_open(y,N)
 ok('baseline_economic_identity_'+mode,x.cash==y.cash and x.active==y.active and a['cashflow']==b['cashflow'] and a['fees']==b['fees'])
 for left,right in zip(x.orders,y.orders):
  ok('baseline_order_economics_'+mode,all(left[k]==right[k] for k in right if k!='lot_quantities'))

# Real atomic loop rolls back sale and close-time new adoption, not a manual imitation.
x,a,z=primed();z['raw_open']=8;before=copy.deepcopy({k:getattr(x,k) for k in ['active','archive','orders','candidates','cash']})
x.accrue=lambda d:None;x.alloc_open=lambda *args:(_ for _ in ()).throw(e.Blocked('AFTER_M10_SALE'))
e.run_loop(x,checkpoint=False)
ok('atomic_sale_rollback',all(getattr(x,k)==v for k,v in before.items()) and x.active['S'] is x.archive['ROUND'])
x,a,z=fixture();cp(a,N);before=copy.deepcopy({k:getattr(x,k) for k in ['active','archive','orders','candidates','cash']})
x.accrue=lambda d:None;x.alloc_open=lambda *args:None
x.close=lambda d,prev:(x.adopt_seed_protection(d),(_ for _ in ()).throw(e.Blocked('AFTER_M10_ADOPTION')))[-1]
e.run_loop(x,checkpoint=False)
ok('atomic_adoption_rollback',all(getattr(x,k)==v for k,v in before.items()))
x,a,z=primed();z['raw_open']=float('nan');before=copy.deepcopy(x.active);e.run_loop(x,checkpoint=False)
ok('missing_OPEN_no_synthetic_fill',not x.orders and x.active==before and 'OPEN_MISSING' in x.blockers[0])

x,a,z=primed();x.ledger=[dict(day=e.day(C),NAV=str(x.cash+D(3000)))];x.pending=[];x.d.excluded=[];x.d.admission=[];x.d.hashes={};x.all_blockers=[]
with tempfile.TemporaryDirectory(prefix='synthetic_export_',dir=P) as td:
 out=Path(td)/'export';x.export(out);r=e.read(out/'INITIAL_CP_PROTECTION.json')
 ok('native_export_protection_and_evidence',len(r)==1 and r[0]['protection']['admission_evidence']['net_at_CP'] is not None)
 ok('native_export_hash_covers_protection',e.read(out/'OUTPUT_HASHES.json')['INITIAL_CP_PROTECTION.json']==e.sha(out/'INITIAL_CP_PROTECTION.json'))
ok('static_method_identities',e.self_check()['result']=='PASS')
ok('no_M9_inheritance',e.Engine.__bases__==(e.m7.Engine,))
ok('old_CLOSE_check_precedes_inherited_CLOSE',inspect.getsource(e.Engine.close).index('self.lock_seed')<inspect.getsource(e.Engine.close).index('super().close'))
ok('no_account_ifloor_write',"a['ifloor']=" not in inspect.getsource(e.Engine))
try:x.run()
except RuntimeError:ok('history_entrypoint_disabled')
else:raise AssertionError('history enabled')
seal=e.read(P/'DEPENDENCY_SEAL.json');ok('dependencies_unchanged',all(Path(p).exists() and e.sha(Path(p))==h for p,h in seal['hashes'].items()))
e.save(P/'STATIC_QA.json',e.self_check());e.save(P/'SYNTHETIC_QA.json',dict(result='PASS',history_run=False,count=len(checks),checks=checks,engine_sha256=e.sha(P/'engine.py'),contract_sha256=e.sha(P/'CONTRACT.md'),test_sha256=e.sha(Path(__file__))))
print('PASS',len(checks),'synthetic/static checks; historical strategy NOT RUN')
