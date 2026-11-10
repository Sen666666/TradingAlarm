"""Synthetic only: no Data loader, historical prices, strategy-history run or outcomes."""
from pathlib import Path
import importlib.util, sys, copy, types, inspect, ast
P=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('m9_test', P/'engine.py')
e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
D=e.D;pd=e.pd;checks=[]
B=pd.Timestamp('2024-09-09');C=pd.Timestamp('2024-09-10');N=pd.Timestamp('2024-09-11');L=pd.Timestamp('2024-09-12')
def ok(name, condition=True):
    assert condition, name
    checks.append(name)
def fixture(state=0, main=0, cash=1200000, kinds=('SEED','ADD','SEED')):
    z=pd.Series(dict(raw_open=10,raw_close=10,adjustment_factor=1,
         source_kind='SYNTHETIC',source_path='SYNTHETIC',segment_id='0',
         observed_bar=True,price_eligible=True,volume_eligible=True,source_invalid=False,synthetic_event_bar=False))
    qr=e.m3.b.QuantityRule('SYNTHETIC',100,100,100,True,1)
    data=types.SimpleNamespace(sid_sector={'S':'SEC'},names={'S':'Synthetic'},events={},
         sectors={'SEC':pd.DataFrame({'state':[state,state,state,state]},index=[B,C,N,L])},
         cal=pd.DatetimeIndex([B,C,N,L]),days=[N],
         stock=pd.DataFrame({'S':[0,0,0,0]},index=[B,C,N,L]))
    data.m=lambda s,d:types.SimpleNamespace(M=main)
    data.z=lambda s,d:z
    data.action=lambda s,d:[]
    data.getmeta=lambda s,d:(qr,None,None)
    data.fee=lambda s,d,q,p,side:D('5')
    x=e.Engine(data)
    a=dict(id='ROUND',sid='S',lots=[],exit=None,plan=None,cp=None,factor=D(1),ifloor=D(1),
           origin=e.m3.lineage(z),fees=D(0),cashflow=D(-100000),dividend=D(0),confirmed_history=True,
           add_count=1,seed_day='2024-09-09',nav0=D(1200000))
    for k,(kind,role) in enumerate(zip(kinds,['INITIAL','EXPANSION','EXPANSION'])):
        a['lots'].append(dict(id=str(k),kind=kind,capital_role=role,q=100,bought='2024-09-09',floor=D(2)))
    x.active={'S':a};x.archive={'ROUND':a};x.cash=D(cash)
    return x,a,z

def confirm(x,d):
    previous=x.d.cal[x.d.cal.get_loc(d)-1]
    x.mark_retirements(previous);x.mark_retirements(d)

# Exact tri-state truth table. Includes no-trigger controls and unknown combinations.
for state in [-1,0,1]:
    for main in [-1,0,1]:
        x,a,z=fixture(state,main);confirm(x,C)
        marked=[l['id'] for l in a['lots'] if 'retirement_signal_day' in l]
        ok(f'trigger_state_{state}_M_{main}',marked==(['1','2'] if state==main==0 else []))
        ok(f'INITIAL_unchanged_{state}_{main}','retirement_signal_day' not in a['lots'][0])

# Mixed round, both acquisition kinds, no cash/receiver dependency, inherited order accounting.
for cash in [0,1200000,9000000]:
    x,a,z=fixture(cash=cash);initial=copy.deepcopy(a['lots'][0]);confirm(x,C)
    ok('no_account_or_protective_exit_mutation_'+str(cash),a['exit'] is None and all(not l.get('exit') for l in a['lots']))
    x.economic_preflight(N,[]);x.exit_open(N)
    ok('mixed_INITIAL_preserved_'+str(cash),x.active['S']['lots']==[initial])
    ok('SEED_and_ADD_expansion_retired_'+str(cash),[o['lots'] for o in x.orders]==[['1','2']] and x.orders[0]['lot_quantities']=={'1':100,'2':100})
    ok('reason_and_sizing_'+str(cash),all(o['reason']==e.REASON and o['qty']==200 and o['side']=='SELL_LAYERS' and o['signal_day']==e.day(C) for o in x.orders))
    ok('fees_slippage_cash_'+str(cash),x.cash==D(cash)+D(200)*D(10)*(1-e.SLIP)-D(5) and a['fees']==D(5))

# Idempotent irreversible marker; no timing parameter or re-entry addition.
x,a,z=fixture();confirm(x,C);before=copy.deepcopy(a['lots']);n=sum(r['event']=='EXPANSION_RETIREMENT' for r in x.candidates)
x.mark_retirements(N);ok('marker_not_retimed_or_duplicated',a['lots']==before and sum(r['event']=='EXPANSION_RETIREMENT' for r in x.candidates)==n)
x.d.m=lambda s,d:types.SimpleNamespace(M=1);x.d.sectors['SEC'].loc[N,'state']=1
x.exit_open(N);ok('prior_CLOSE_instruction_survives_recovery',len(x.orders)==1)
x,a,z=fixture();confirm(x,C);x.exit_open(C);ok('no_same_CLOSE_day_execution',not x.orders)

# Existing account I exits and lot CP exits execute first with unchanged baseline attribution.
for why in ['I_INVALID','I_CLOSE_PROTECTION','TRIAL_SECTOR_FALSE']:
    x,a,z=fixture();confirm(x,C);a['exit']=why;x.exit_open(N)
    ok('existing_account_exit_'+why,len(x.orders)==1 and x.orders[0]['reason']==why and 'S' not in x.active)
x,a,z=fixture();confirm(x,C);z['raw_open']=D('.5');x.exit_open(N)
ok('I_OPEN_precedes_retirement',len(x.orders)==1 and x.orders[0]['reason']=='I_OPEN_PROTECTION')
for mode in ['close','open']:
    x,a,z=fixture();confirm(x,C)
    if mode=='close':a['lots'][1]['exit']='CP_CLOSE_PROTECTION'
    else:a['lots'][1]['floor']=D(11)
    x.exit_open(N)
    ok('CP_'+mode+'_precedes_retirement',[o['reason'] for o in x.orders]==['CP_LAYER_EXIT',e.REASON] and x.orders[0]['lots']==['1'])
x,a,z=fixture();a['lots'][1]['exit']='CP_CLOSE_PROTECTION';confirm(x,C)
ok('protective_lot_not_marked','retirement_signal_day' not in a['lots'][1] and 'retirement_signal_day' in a['lots'][2])

# Dated share-size applies to aggregated eligible expansion only, with one fee per stock.
for q1,q2 in [(150,50),(50,50)]:
    x,a,z=fixture();a['lots'][1]['q']=q1;a['lots'][2]['q']=q2;confirm(x,C);x.exit_open(N)
    ok('aggregate_odd_lots_'+str((q1,q2)),len(x.orders)==1 and x.orders[0]['qty']==q1+q2 and [l['id'] for l in a['lots']]==['0'])
    ok('single_fee_and_mapping_'+str((q1,q2)),a['fees']==D(5) and x.orders[0]['lot_quantities']=={'1':q1,'2':q2})
x,a,z=fixture();a['lots'][1]['q']=150;a['lots'][2]['q']=100;confirm(x,C);x.exit_open(N)
ok('legal_aggregate_partial_sell',len(x.orders)==1 and x.orders[0]['qty']==200 and x.orders[0]['lot_quantities']=={'1':150,'2':50})
ok('INITIAL_never_used_to_round',[(l['id'],l['q']) for l in a['lots']]==[('0',100),('2',50)])
ok('remainder_marker_preserved','retirement_signal_day' in a['lots'][1])
x,a,z=fixture();a['lots']=a['lots'][1:2];a['lots'][0]['q']=150;confirm(x,C);x.exit_open(N)
ok('full_exit_odd_rule',x.orders[0]['qty']==150 and x.orders[0]['side']=='SELL_ALL' and 'S' not in x.active)

# T+1 leaves marker intact, executes at later eligible OPEN without changing protection semantics.
x,a,z=fixture();a['lots'][1]['bought']=e.day(N);confirm(x,C);x.exit_open(N)
ok('T1_defers_only_new_lot',[l['id'] for l in a['lots']]==['0','1'] and a['lots'][1]['retirement_signal_day']==e.day(C))
x.exit_open(L);ok('T1_later_execution',[l['id'] for l in a['lots']]==['0'])

# Exercise actual unchanged preflight and actual unchanged atomic loop, not a manual rollback imitation.
for bad in [float('nan'),0]:
    x,a,z=fixture();confirm(x,C);z['raw_open']=bad;before=copy.deepcopy(x.active)
    e.run_loop(x,checkpoint=False)
    ok('held_nontradable_fail_closed_'+str(bad),not x.orders and x.active==before and len(x.blockers)==1 and 'OPEN_MISSING' in x.blockers[0])
x,a,z=fixture();confirm(x,C);before=copy.deepcopy({k:getattr(x,k) for k in ['cash','active','archive','orders','candidates']})
x.accrue=lambda d:None
x.alloc_open=lambda d,p:(_ for _ in ()).throw(e.Blocked('SYNTHETIC_BLOCK_AFTER_RETIREMENT'))
e.run_loop(x,checkpoint=False)
ok('atomic_rollback_after_real_retirement_sales',all(getattr(x,k)==v for k,v in before.items()))
ok('partial_orders_are_diagnostic_only',len(x.uncertified_day['partial_orders'])==1 and len(x.blockers)==1)
ok('rollback_preserves_active_archive_alias',x.active['S'] is x.archive['ROUND'])

# Frozen donor execution cannot sell an already retired lot a second time.
for gap in [D(0),D(90000000)]:
    x,a,z=fixture();confirm(x,C)
    x.transfer_plan=[dict(sid='S',sector51='SEC',round_id='ROUND',lot_id='1',
                         max_q=100,reason='NON_MAINLINE_EXPANSION',rank=1,signal_day=e.day(C))]
    x.exit_open(N);before=copy.deepcopy(x.orders);cash=x.cash
    x.demand=lambda *args:(gap,[])
    x.execute_transfers(N,[],D(1200000),{'S':D(1000)})
    ok('stale_donor_no_double_sale_'+str(gap),x.orders==before and x.cash==cash and not x.transfer_plan)
    why='RECEIVER_GAP_ZERO' if gap==0 else 'DONOR_ALREADY_EXITED'
    ok('stale_donor_diagnostic_'+str(gap),x.transfers[-2]['decision']==why)

# Actual full synthetic export exposes pending partial-retirement lots and seals that file.
import tempfile
x,a,z=fixture();a['lots'][1]['q']=150;a['lots'][2]['q']=100
confirm(x,C);x.exit_open(N)
x.ledger=[dict(day=e.day(N),NAV=str(x.cash+D(2000)))];x.pending=[]
x.d.excluded=[];x.d.admission=[];x.d.hashes={};x.all_blockers=[]
with tempfile.TemporaryDirectory(prefix='synthetic_export_',dir=P) as td:
    out=Path(td)/'export';x.export(out)
    pending=e.read(out/'PENDING_RETIREMENTS.json')
    ok('export_pending_per_lot',len(pending)==1 and all(r['remaining_qty']==50 and r['signal_day']==e.day(C) and r['reason']==e.REASON for r in pending))
    ok('export_hash_covers_pending',e.read(out/'OUTPUT_HASHES.json')['PENDING_RETIREMENTS.json']==e.sha(out/'PENDING_RETIREMENTS.json'))

# Actual CLOSE hook dispatch order, using only a spy in the inherited planning body.
x,a,z=fixture();x.mark_retirements(B);original=e.m7.Engine.plan_transfers
try:
    def spy(self,d,pending):
        assert all('retirement_signal_day' in l for l in self.active['S']['lots'][1:])
        return 'BASELINE_PLANNING_UNCHANGED'
    e.m7.Engine.plan_transfers=spy
    ok('hook_before_baseline_transfer_planning',x.plan_transfers(C,[])=='BASELINE_PLANNING_UNCHANGED')
finally:e.m7.Engine.plan_transfers=original
ok('static_checks',e.self_check()['result']=='PASS')
try:x.run()
except RuntimeError:ok('historical_entrypoint_disabled')
else:raise AssertionError('history entrypoint unexpectedly enabled')

# M9-specific persistence and no-lookahead contract checks.
def marked(a):return [l['id'] for l in a['lots'] if 'retirement_signal_day' in l]
x,a,z=fixture();a['cashflow']=D(-1000);confirm(x,C)
ok('profitable_round_retained',not marked(a) and D(a['m9_close_observation']['close_net'])>0)
x,a,z=fixture();x.mark_retirements(C)
ok('one_false_day_retained',not marked(a));x.mark_retirements(C)
ok('duplicate_same_day_not_second_confirmation',not marked(a));x.mark_retirements(N)
ok('two_consecutive_simultaneous_failures_trigger',marked(a)==['1','2'])
for field in ['sector','M','stock']:
    for unknown in [-1,float('nan')]:
        x,a,z=fixture();x.mark_retirements(B)
        if field=='sector':x.d.sectors['SEC'].at[C,'state']=unknown
        elif field=='M':x.d.m=lambda s,d:types.SimpleNamespace(M=unknown if d==C else 0)
        else:x.d.stock.at[C,'S']=unknown
        x.mark_retirements(C);x.mark_retirements(N)
        ok('unknown_resets_'+field+'_'+str(unknown),not marked(a))
        x.mark_retirements(L);ok('fresh_two_days_after_unknown_'+field+'_'+str(unknown),marked(a)==['1','2'])
x,a,z=fixture();x.mark_retirements(B);a['id']='NEW_ROUND';x.mark_retirements(C)
ok('round_replacement_cannot_reuse_prior',not marked(a));x.mark_retirements(N)
ok('new_round_own_two_records_can_confirm',marked(a)==['1','2'])
x,a,z=fixture();x.mark_retirements(B);x.mark_retirements(N)
ok('nonconsecutive_known_days_do_not_confirm',not marked(a))
x,a,z=fixture();x.mark_retirements(B);a['cashflow']=D(100000);x.mark_retirements(C)
ok('current_profitable_does_not_confirm',not marked(a))
x,a,z=fixture();a['cashflow']=D(100000);x.mark_retirements(B);a['cashflow']=D(-100000);x.mark_retirements(C)
ok('prior_profitable_not_recomputed_from_current_cashflow',not marked(a) and x.candidates[-1]['prior']['close_net']!=a['m9_close_observation']['close_net'])
x,a,z=fixture();a['cashflow']=-(D(300)*D(10)*(1-e.SLIP)-D(5));confirm(x,C)
ok('exact_zero_net_is_nonpositive',marked(a)==['1','2'] and D(a['m9_close_observation']['close_net'])==0)
for bad in ['observed_bar','price_eligible','volume_eligible','source_invalid','synthetic_event_bar','raw_close','absent']:
    x,a,z=fixture();x.mark_retirements(B);original=z.copy()
    if bad=='absent':x.d.z=lambda s,d:{} if d==C else original
    elif bad=='raw_close':z[bad]=float('nan')
    else:z[bad]=bad in ['source_invalid','synthetic_event_bar']
    x.mark_retirements(C);x.d.z=lambda s,d:original;x.mark_retirements(N)
    ok('bad_close_breaks_confirmation_'+bad,not marked(a))
x,a,z=fixture();reads=[]
def current_only(s,d):
    reads.append(d);assert d==C,'lookahead or prior reconstruction';return z
x.d.z=current_only;x.mark_retirements(C)
ok('observation_reads_only_requested_completed_close',reads==[C,C])
x,a,z=fixture();a['dividend']=D(23);a['cashflow']=D(-4000)
x.mark_retirements(B);saved=copy.deepcopy(a['m9_close_observation']);a['lots'][1]['q']=200;a['cashflow']-=D(1005)
x.mark_retirements(C)
ok('frozen_prior_uses_prior_holdings_and_cashflow',x.candidates[-1]['retirement_evidence']['prior']==saved)
ok('net_includes_dividend_fees_and_slippage',D(saved['close_net'])==D(-4000)+D(23)+D(300)*D(10)*(1-e.SLIP)-D(5))
# Close-time new observation and new markers are rolled back by real atomic loop.
x,a,z=fixture();x.mark_retirements(C);before=copy.deepcopy({k:getattr(x,k) for k in ['active','archive','candidates','orders','cash']})
x.accrue=lambda d:None;x.alloc_open=lambda *args:None
x.close=lambda d,prev:(x.mark_retirements(d),(_ for _ in ()).throw(e.Blocked('AFTER_M9_CLOSE_EVIDENCE')))[-1]
e.run_loop(x,checkpoint=False)
ok('atomic_rollback_new_observation_and_marker',all(getattr(x,k)==v for k,v in before.items()) and x.active['S'] is x.archive['ROUND'])
x,a,z=fixture();confirm(x,C);ev=copy.deepcopy(a['lots'][1]['retirement_evidence']);x.exit_open(N)
ok('sale_export_preserves_current_prior_evidence',x.orders[0]['retirement_evidence']['1']==ev and ev['prior']['day']==e.day(B) and ev['current']['day']==e.day(C))

# Snapshot the immutable dependencies read by imports and all frozen baseline output artifacts.
paths=set()
for module in list(sys.modules.values()):
    f=getattr(module,'__file__',None)
    if f and Path(f).is_file() and '/Users/bytedance/Documents/' in f and P not in Path(f).parents:
        paths.add(Path(f).resolve())
paths.update(p for p in e.BASE.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
# Check against a pre-test seal when present; no outcome/fact mutation permitted.
seal_path=P/'DEPENDENCY_SEAL.json'
if seal_path.exists():
    prior=e.read(seal_path)
    ok('all_pretest_dependencies_unchanged',all(Path(p).is_file() and e.sha(Path(p))==h for p,h in prior['hashes'].items()))
else:raise AssertionError('Dependency seal must be created before QA')
e.save(P/'STATIC_QA.json',e.self_check())
e.save(P/'SYNTHETIC_QA.json',dict(result='PASS',checks=checks,count=len(checks),history_run=False,
    engine_sha256=e.sha(P/'engine.py'),contract_sha256=e.sha(P/'CONTRACT.md'),test_sha256=e.sha(Path(__file__))))
e.save(P/'OUTPUT_SEAL.json',dict(history_run=False,files={p.name:e.sha(p) for p in P.iterdir() if p.is_file() and p.name!='OUTPUT_SEAL.json'}))
print('PASS',len(checks),'synthetic/static checks; historical strategy NOT RUN')
