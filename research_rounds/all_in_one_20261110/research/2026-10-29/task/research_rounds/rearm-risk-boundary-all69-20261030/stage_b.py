"""Frozen v2 requests; original verified local cash/holding accounting, no new buying."""
from pathlib import Path
from datetime import datetime,time as dt,timezone
from decimal import Decimal as D,getcontext
from dataclasses import replace
from collections import Counter
import ast,sys,json,gzip,csv,time,hashlib,importlib.util,bisect
import pandas as pd

T=time.monotonic();O=Path(__file__).resolve().parent;W=O.parent;R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');S=R/'s-entry-mechanism-audit-20261029';BASE=R/'pvr-local-finite-capital-20261029/baseline';OLD=W/'old-side-exit-all69-20261030';PREV=W/'down-event-transfer-local-20261030/study.py';Z=D(0);ONE=D(1)
stage=sys.argv[1];assert stage in ['sample','full'];dest=O/stage;dest.mkdir(exist_ok=False)
sp=importlib.util.spec_from_file_location('v2_same_accounting',S/'code/audit.py');H=importlib.util.module_from_spec(sp);sys.modules[sp.name]=H;sp.loader.exec_module(H)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(H.encoded(x),ensure_ascii=False,indent=2,allow_nan=False))
def export(p,x):pd.DataFrame(H.encoded(x)).to_csv(p,index=False)
def stamp(x):return datetime.fromisoformat(x)
fr=read(O/'FREEZE.json');assert all(sha(p)==h for p,h in fr['sha256'].items())
av=read(O/'VERIFICATION.json');assert av['passed_adapter_checks'] and av['cases']==69
mother=list(csv.DictReader((O/'FROZEN_CASES.csv').open()));beh={x['cycle_id']:x for x in csv.DictReader((O/'CASE_RESULTS.csv').open())};assert len(mother)==len(beh)==69
for e in mother:
 if e['old_quantity']:
  q=D(e['old_quantity']);assert q==q.to_integral_value();e['old_quantity']=int(q)
ca=list(csv.DictReader((O/'CORPORATE_ACTION_COMPARABILITY.csv').open()));assert all(x['status']=='source_price_and_original_ledger_consistent' for x in ca if x['date'])
old13={x['cycle_id']:x for x in csv.DictReader((W/'rearm-risk-boundary-historical13-20261030/CASE_RESULTS.csv').open())}
for cid,x in old13.items():assert all(beh[cid][k]==v for k,v in x.items() if k!='role')
warning_diffs=[]
for e in mother:
 b=beh[e['cycle_id']]
 if b['first_known_native_negative']!=e['date']:
  assert not e['date'] and not b['added_request'] and b['first_known_native_negative']==b['original_request'][:10]
  warning_diffs.append(dict(cycle_id=e['cycle_id'],raw_negative=b['first_known_native_negative'],old_legal_warning=e['date'],reason='original_exit_already_has_priority_same_day_no_policy_divergence'))
 if b['added_request']:assert e['date'] and e['date']==b['first_known_native_negative']
gate=dict(passed=True,known_data_conditional_cases=[k for k,b in beh.items() if int(b['unknown_count'])],blocked_economic_cases=[],same_fixed13_behavior_exact=len(old13),corporate_actions_checked=sum(bool(x['date']) for x in ca),raw_negative_vs_old_legal_warning=warning_diffs,core_sha256=sha(W/'rearm-risk-boundary-design-20261030/risk_boundary_v2.py'),stage_a_seconds=av['seconds'])
save(O/'STAGE_A_GATE.json',gate)
targets=['605118.SH|2024-01-02','301486.SZ|2024-03-27','688143.SH|2026-06-03'];first_other=next(e['cycle_id'] for e in mother if e['cycle_id'] not in targets and beh[e['cycle_id']]['added_request']);sample_ids=targets+[first_other]
inputs=[Path(__file__),O/'ADAPTER_CONTRACT.txt',O/'FREEZE.json',O/'STAGE_A_GATE.json',O/'CASE_RESULTS.csv',O/'FROZEN_CASES.csv',O/'PROTECTION_EPISODES.csv',PREV,OLD/'full/unit-ledgers.csv',OLD/'full/VERIFICATION.json',BASE/'accounts-v2/I__S0_base.json',BASE/'analysis/campaigns.csv',S/'market-cache.parquet',W/'act-loss-facts-20261030/actual-holding-close-paths.csv']
if stage=='sample':save(O/'ECONOMIC_FREEZE.json',dict(at=datetime.now(timezone.utc).isoformat(),before_new_v2_returns=True,samples=sample_ids,mother_ids=[e['cycle_id'] for e in mother],sha256={str(p):sha(p) for p in inputs},core_unchanged=True,cost2_activation='original_known_legal_negative_warning_shared_with_old_A'))
identity=read(O/'ECONOMIC_FREEZE.json');assert identity['mother_ids']==[e['cycle_id'] for e in mother];assert all(sha(p)==h for p,h in identity['sha256'].items())
events=mother if stage=='full' else [e for e in mother if e['cycle_id'] in sample_ids];ids={e['old'] for e in events};_,m,_,_=H.context(ids,False)
obj=read(BASE/'accounts-v2/I__S0_base.json');audit=obj['audit_log'];actualfills=[x for x in audit if x['kind']=='fill'];cycles={f"{x['symbol']}|{x['entry_at'][:10]}":x for x in csv.DictReader((BASE/'analysis/campaigns.csv').open()) if x['scenario']=='base'}
olddiv=[x['receivable'] for x in audit if x['kind']=='dividend_accrual'];oldrows=list(csv.DictReader((OLD/'full/unit-ledgers.csv').open()));oi={(x['cycle_id'],int(x['cost']),x['arm']):x for x in oldrows};assert len(oi)==276 and read(OLD/'full/VERIFICATION.json')['passed']
cache=pd.read_parquet(S/'market-cache.parquet');cc={(x.symbol,str(x.date.date())):x for x in cache.itertuples(index=False)};calendar=sorted({k[1] for k in cc});cp={x['at'][:10]:x for x in audit if x['kind']=='risk_checkpoint'}
paths=list(csv.DictReader((W/'act-loss-facts-20261030/actual-holding-close-paths.csv').open()));path_by={k:[x for x in paths if x['cycle_id']==k] for k in cycles}
checks=Counter();maxres=Z;results=[];curves=[];flowlogs=[];control_checks=[];execution_rows=[]
names=['near','seed','consume','marks_at','snapshot'];nodes=[n for n in ast.parse(PREV.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in names];assert {n.name for n in nodes}==set(names);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(PREV),'exec'),globals())
def endpoints(e):
 t=H.at(e['date'],dt(15,10));first=m.sessions['A'][bisect.bisect_right(m.sessions['A'],t)];end=H.at(cycles[e['cycle_id']]['exit_at'][:10],dt(15,10));return t,first,end,end,'original_cycle_exit'
def risk(vs):
 peak=vs[0];dd=Z
 for v in vs:peak=max(peak,v);dd=max(dd,ONE-v/peak)
 return min(vs)/vs[0]-ONE,dd
loadsec=time.monotonic()-T
for n,e in enumerate(events):
 cid=e['cycle_id'];b=beh[cid];c=cycles[cid];basis=D(c['buy_gross'])+D(c['buy_fees']);newday=b['added_request'];conditional=bool(int(b['unknown_count']))
 for cost in [1,2]:
  ar=dict(oi[cid,cost,'A']);ar.update(reused=True,reuse_reason='verified_old_A_same69_same_cost_activation',new_request=newday,conditional_missing=conditional,behavior_unknown_dates=b['unknown_dates']);results.append(ar)
 if not newday:
  for cost in [1,2]:
   br=dict(oi[cid,cost,'A']);br.update(arm='B',reused=True,reuse_reason='v2_no_added_request_same_actions',new_request='',conditional_missing=conditional,behavior_unknown_dates=b['unknown_dates']);results.append(br)
  continue
 t,first,end,_,_=endpoints(e);states=[]
 # Samples independently replay both A and B. Full repeats only B; A is exact validated reuse.
 for cost in [1,2]:
  for arm in (['A','B'] if stage=='sample' else ['B']):
   st=seed(e,cost,'A');st['arm']=arm;st['windows']=[];states.append(st);snapshot(st,e,t,'trigger_close')
 for day in calendar[calendar.index(str(first.date())):bisect.bisect_right(calendar,str(end.date()))]:
  op=H.at(day,dt(9,30));cl=H.at(day,dt(15,10))
  for st in states:
   a=st['a']
   for act in m.actions.get(e['old'],[]):
    if act['effective_date']==day:H.action(a,m,e['old'],act)
   H.pay(a,m,op)
   for s in tuple(a.exits):
    q=a.quantity(s);w=m.window(s,op,'sell',st['cost']);fill=a.fill_exit(s,w) if w else None
    st['windows'].append(dict(at=op,shares_before=q,shares_after=a.quantity(s),window_known=w is not None,sell_allowed=w.sell_allowed if w else None,capacity=w.capacity_shares if w else None,filled=fill is not None,exit_still_pending=s in a.exits))
   H.pay(a,m,op);snapshot(st,e,op,'open');H.pay(a,m,cl)
   if a.quantity(e['old']) and e['old'] not in a.exits:
    r=cc[e['old'],day]
    if pd.isna(r.i_target):st['unknowns'].append(day+':I_unknown')
    else:
     orig=not bool(r.i_target) or not cp[day]['on'];new=st['arm']=='B' and day==newday
     if orig or new:
      quote=m.quote(e['old'],cl)
      if quote is None:st['unknowns'].append(day+':exit_quote_unknown')
      else:
       a.request_exit(quote,H.A.Clock(cl,m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)],cl.date()));st['requests'].append(dict(sid=e['old'],at=cl,reason=('ACT' if not cp[day]['on'] else 'I_structure') if orig else 'frozen_v2_boundary'))
   snapshot(st,e,cl,'close')
 for st in states:
  sr=st['snapshots'][-1];assert sr['at']==end;prefix=[basis]+[basis+D(x['nav_mark_pnl']) for x in path_by[cid] if x['day']<=e['date']];near(prefix[-1],st['I0']);mn,dd=risk(prefix+[x['nav'] for x in st['snapshots'][1:]]);postmn,postdd=risk([x['nav'] for x in st['snapshots']]);sells=[x for x in st['fills'] if x['side']=='sell'];fullnet=sr['nav']-basis;close=[x for x in st['snapshots'] if x['phase']=='close'];prefixheld=sum(x['day']<=e['date'] for x in path_by[cid]);originalA=oi[cid,st['cost'],'A']
  row=dict(cycle_id=cid,symbol=e['old'],name=c['name'],cost=st['cost'],arm=st['arm'],triggered=True,trigger=e['date'],unknown_event_days=e['unknown_event_days'],unknown_before_first=e['unknown_before_first'],previous32=e['previous32'],original_tail30=originalA['original_tail30'],original_profitable=originalA['original_profitable'],original_entry=c['entry_at'],original_exit=c['exit_at'],initial_actual_cost=basis,original_pretrigger_pnl=st['prior_pnl'],trigger_equity=st['I0'],final_equity=sr['nav'],full_cycle_net=fullnet,full_cycle_return=fullnet/basis,post_trigger_pnl=sr['nav']-st['I0'],fees_after_trigger=sr['fees'],full_fees=D(c['buy_fees'])+sr['fees'],dividend=sr['dividend'],first_sell=sells[0]['at'] if sells else None,last_sell=sells[-1]['at'] if sells else None,sold_quantity=sum(x['shares'] for x in sells),sell_fill_count=len(sells),final_shares=st['a'].quantity(e['old']),terminal_claim=sr['claim'],min_full_cycle_return=mn,max_full_cycle_DD=dd,min_post_trigger_return=postmn,max_post_trigger_DD=postdd,holding_close_observations=prefixheld+sum(x['inventory']>0 for x in close),cash_close_after_trigger=sum(x['inventory']==0 for x in close),status='v2_exit_requested' if st['arm']=='B' else 'original_hold',reused=False,reuse_reason='',new_request=newday,conditional_missing=conditional,behavior_unknown_dates=b['unknown_dates'],execution_unknown='|'.join(st['unknowns']),terminal_sale_receivable=sr['sale_receivable'],terminal_inventory=sr['inventory'])
  if st['arm']=='A':
   for k in ['full_cycle_net','full_fees','dividend','sold_quantity','final_shares']:assert D(str(row[k]))==D(originalA[k]),(cid,st['cost'],k,row[k],originalA[k])
   assert len(sells)==1 and str(sells[0]['at'])==c['exit_at'];control_checks.append(dict(cycle_id=cid,cost=st['cost'],A_net=row['full_cycle_net'],reused_A_net=originalA['full_cycle_net'],difference=Z))
  else:
   assert sum(x['reason']=='frozen_v2_boundary' for x in st['requests'])==1
   trigger_snap=next(x for x in st['snapshots'] if x['at']==H.at(newday,dt(15,10)));execution_rows.append(dict(cycle_id=cid,cost=st['cost'],request=newday,request_shares=trigger_snap['shares'],request_nav=trigger_snap['nav'],request_est_net_liquidation=trigger_snap['nav']-trigger_snap['estimated_liquidation_fee']-trigger_snap['estimated_liquidation_slippage'],final_equity=sr['nav'],request_est_to_final=sr['nav']-trigger_snap['nav']+trigger_snap['estimated_liquidation_fee']+trigger_snap['estimated_liquidation_slippage'],first_sell=row['first_sell'],last_sell=row['last_sell'],sold_quantity=row['sold_quantity'],final_shares=row['final_shares'],sell_fill_count=row['sell_fill_count'],actual_sell_fees=row['fees_after_trigger'],actual_slippage=st['slippage'],unknown=row['execution_unknown']))
   results.append(row)
  maxres=max(maxres,st['maxres']);curves.extend(st['snapshots']);flowlogs.append(dict(cycle_id=cid,cost=st['cost'],arm=st['arm'],fills=st['fills'],requests=st['requests'],windows=st['windows'],audit=st['a'].audit_log))
 print(json.dumps(dict(stage=stage,cycles=n+1,total=len(events),seconds=time.monotonic()-T),ensure_ascii=False),flush=True)
 if time.monotonic()-T+float(identity.get('sample_seconds',0))+av['seconds']>300:raise TimeoutError('300s cumulative stages A/sample/full budget')
assert len(results)==len(events)*4
export(dest/'unit-ledgers.csv',results);export(dest/'independent-A-controls.csv',control_checks);export(dest/'exit-execution.csv',execution_rows);pd.DataFrame(H.encoded(curves)).to_parquet(dest/'local-equity.parquet',index=False)
with gzip.open(dest/'audit.json.gz','wt') as f:json.dump(H.encoded(flowlogs),f,ensure_ascii=False,allow_nan=False)
if stage=='full':
 sm=pd.read_csv(O/'sample/unit-ledgers.csv',dtype=str).fillna('').set_index(['cycle_id','cost','arm']);fu=pd.read_csv(dest/'unit-ledgers.csv',dtype=str).fillna('').set_index(['cycle_id','cost','arm']);pd.testing.assert_frame_equal(sm,fu.loc[sm.index],check_exact=True)
 assert sum((D(str(x['full_cycle_net'])) for x in results if x['arm']=='A' and str(x['cost'])=='1'),Z)==D('2984160.2756603511085')
assert all(sha(p)==h for p,h in identity['sha256'].items())
elapsed=time.monotonic()-T;save(dest/'VERIFICATION.json',dict(passed=True,stage=stage,cycles=len(events),ledgers=len(results),v2_requested=sum(bool(beh[e['cycle_id']]['added_request']) for e in events),A_independent_reproduction=len(control_checks),known_missing_conditional_cycles=sum(bool(int(beh[e['cycle_id']]['unknown_count'])) for e in events),blocked_cycles=[],checks=dict(checks),max_NAV_residual=maxres,sample_full_exact=stage=='full',seconds=elapsed,load_seconds=loadsec,portfolio_paths=0,new_buys=0,frozen_rule_changes=0))
if stage=='sample':identity['sample_seconds']=elapsed;save(O/'ECONOMIC_FREEZE.json',identity)
print(json.dumps(dict(stage=stage,complete=True,seconds=elapsed),ensure_ascii=False),flush=True)
