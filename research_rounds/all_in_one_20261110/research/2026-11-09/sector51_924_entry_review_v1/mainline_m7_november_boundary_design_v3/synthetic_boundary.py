from pathlib import Path
import sys,importlib.util,json,types,copy,contextlib,io
P=Path(__file__).resolve().parent;sp=importlib.util.spec_from_file_location('boundary_test',P/'engine.py');e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
checks=[]
def ok(n,v=True):
 assert v,n
 checks.append(n)
static=e.self_check();ok('all_unmodified_methods_identity');ok('loop_has_atomic_paused_state',"keys=['paused_new_requests','cash'" in e.source)
# Actual sealed pending request, not invented budget/identity.
r=next(x for x in e.read(e.BASE/'once_20260630/PENDING_AT_END.json') if x['sid']==e.SID);before=copy.deepcopy(r)
x=e.Engine(types.SimpleNamespace());p=[copy.deepcopy(r)];old=e.b.Engine.economic_preflight;oldclose=e.b.Engine.close
try:
 e.b.Engine.economic_preflight=lambda self,d,p:ok('halt_request_removed_only_from_execution',not any(x['sid']==e.SID for x in p))
 e.b.Engine.close=lambda self,d,p:[]
 x.economic_preflight(e.pd.Timestamp(e.HALT),p);ok('identity_preserved_in_paused_state',x.paused_new_requests[e.SID]['request']==before and not x.tickets)
 back=x.close(e.pd.Timestamp(e.HALT),None);ok('original_pending_restored_unchanged',back==[before]);ok('no_cash_position_mutation',x.cash==e.D(1200000) and not x.active and not x.orders)
 try:x.economic_preflight(e.pd.Timestamp(e.RESUME),back)
 except e.Blocked as ex:ok('ST_tier_B_fails_closed',str(ex).endswith('ST_EXECUTION_TIER_B_NOT_ADMITTED'))
 else:raise AssertionError('ST bypass')
 e.b.Engine.close=lambda self,d,p:[copy.deepcopy(before)]
 try:x.close(e.pd.Timestamp(e.HALT),None)
 except AssertionError:ok('no_replacement_halt_signal')
 else:raise AssertionError('conflict')
finally:e.b.Engine.economic_preflight=old;e.b.Engine.close=oldclose
# Exercise actual inherited atomic loop when failure follows a partial pause mutation.
class Failing(e.Engine):
 def economic_preflight(self,d,pending):self.paused_new_requests['test']={'request':copy.deepcopy(before)};self.cash-=e.D(1);raise e.Blocked('SYNTHETIC_POST_PAUSE_FAILURE')
 def scan_restored_targets(self,d,p):return []
y=Failing(types.SimpleNamespace(cal=e.pd.DatetimeIndex(['2024-11-06','2024-11-07']),days=e.pd.DatetimeIndex(['2024-11-07'])))
with contextlib.redirect_stdout(io.StringIO()):e.run_loop(y,False)
ok('atomic_paused_state_and_cash_rollback',not y.paused_new_requests and y.cash==e.D(1200000) and not y.ledger)
for side,bar,expect in [('sell','4.87','DIRECTIONAL_LIMIT_NO_FILL'),('buy','4.87','OPPOSITE_DIRECTION_ONEPRICE_CONDITIONAL_ONLY_NOT_PROVEN_FILL'),('buy','5.39','DIRECTIONAL_LIMIT_NO_FILL'),('sell','5.39','OPPOSITE_DIRECTION_ONEPRICE_CONDITIONAL_ONLY_NOT_PROVEN_FILL')]:ok('direction_'+side+'_'+bar,e.st_oneprice_gate(side,[bar]*4,'5.13')==expect)
ok('unknown_ST_blocks',e.st_oneprice_gate('buy',['4.87']*4,'5.13',False)=='UNKNOWN_STOP')
ok('outside_limit_blocks',e.st_oneprice_gate('buy',['4.80']*4,'5.13')=='REFERENCE_OR_LIMIT_MISMATCH_STOP')
ok('normal_bar_only_conditional',e.st_oneprice_gate('buy',['5.00','5.20','4.90','5.10'],'5.13')=='CONDITIONAL_OPEN_ONLY_NOT_PROVEN_FILL')
# Actual hash-bound cash event source bridge, no historical strategy run.
ev=e.read(P/'CASH_EVENT.json');s=ev['sid'];raw=e.pd.read_parquet(ev['signal_path']);
if not isinstance(raw.index,e.pd.DatetimeIndex):
 column='date' if 'date' in raw else 'trade_date';raw=raw.set_index(column)
data=types.SimpleNamespace(end=e.pd.Timestamp('2026-06-30'),actions={s:e.read(Path(ev['local_action_path']))},raw={s:raw},events={},admission=[],sid_sector={s:'医疗器械'})
def checked(p,h):assert e.sha(Path(p))==h
allowed={(s,ev['ex_date'],ev['economic_event_id_candidate'])};e.admit_cash(data,ev,checked,allowed);ok('actual_300760_bridge_admitted',(s,e.pd.Timestamp(ev['ex_date'])) in data.events)
z=e.Engine(data);z.register_pay(e.pd.Timestamp(ev['record_date']));z.accrue(e.pd.Timestamp(ev['ex_date']));z.register_pay(e.pd.Timestamp(ev['pay_date']));ok('zero_record_holding_no_cash',z.cash==e.D(1200000) and z.receivable==0)
for key,value in [('sid','002602.SZ'),('ex_date','2024-11-08')]:
 bad=dict(ev,**{key:value})
 try:e.admit_cash(data,bad,checked,{(bad['sid'],bad['ex_date'],bad['economic_event_id_candidate'])})
 except AssertionError:ok('scope_reject_'+key)
 else:raise AssertionError('scope widened')
manifest=e.validate_inputs();ok('thirty_full_economic_families',len(manifest['comparison_families'])==30)
try:e.b.require_exact(manifest['required_json_families'][:-1],manifest['required_json_families'],'test')
except AssertionError:ok('missing_baseline_family_rejected')
else:raise AssertionError('vacuous prefix')
qa=dict(result='PASS',total=len(checks),checks=checks,history_run=False,tier_B_integrated=False,engine_sha256=e.sha(P/'engine.py'),contract_sha256=e.sha(P/'CONTRACT.md'))
e.save(P/'STATIC_QA.json',static);e.save(P/'SYNTHETIC_QA.json',qa);print(json.dumps(qa))
