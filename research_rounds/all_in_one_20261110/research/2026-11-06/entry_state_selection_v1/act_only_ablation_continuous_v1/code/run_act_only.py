"""One authorized ACT-only continuous ablation. No real orders; no old account import."""
from pathlib import Path
import sys,json,hashlib,time,copy,pickle,traceback,argparse,math
from decimal import Decimal as D
from datetime import datetime,time as dtime,date
from dataclasses import is_dataclass,asdict
from collections import Counter
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
S=O.parents[1]/'account_comparison_continuous_v1'
ROOT=O.parent
sys.path.insert(0,str(S/'inputs'));import continuous_inputs as C
sys.path.insert(0,str(S/'factors'));from continuous_factors import OpenFactorTimeline,FactorSource
from continuous_execution import attach
import ablation_support as H
A,N,J,L,IO=C.A,C.N,C.J,C.L,C.IO
START,END=C.START,C.END
Z=D(0)
CAPITAL=D('1200000')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canon(x):return J.W.canon(x)
def save(p,x):IO.write_json(p,canon(x))
def read(p):return json.loads(Path(p).read_text())
def normalize(x):
 if x is None or isinstance(x,(str,bool,int)):return x
 if isinstance(x,float):return x if math.isfinite(x) else repr(x)
 if isinstance(x,(D,Path)):return str(x)
 if isinstance(x,(datetime,date)):return x.isoformat()
 if isinstance(x,np.generic):return normalize(x.item())
 if isinstance(x,dict):return {repr(k):normalize(v) for k,v in sorted(x.items(),key=lambda z:repr(z[0]))}
 if isinstance(x,(list,tuple)):return [normalize(v) for v in x]
 if isinstance(x,(set,frozenset)):return sorted([normalize(v) for v in x],key=repr)
 if isinstance(x,np.ndarray):return normalize(x.tolist())
 if is_dataclass(x):return normalize(asdict(x))
 if hasattr(x,'__dict__'):return normalize(vars(x))
 raise TypeError(('unsupported snapshot',type(x)))
def payload(r):
 exclude={'bundle','market','facts','accounts','cp','pv','matrix','matrix_days','industry_rows','industry_cp','receipts','actions_by_date'}
 return dict(runner={k:v for k,v in vars(r).items() if k not in exclude},accounts={k:{f:v for f,v in vars(a).items() if f not in ('market','facts')} for k,a in r.accounts.items()})
def digest(x):return hashlib.sha256(json.dumps(normalize(x),sort_keys=True,separators=(',',':')).encode()).hexdigest()
def clone_account(a):
 b=copy.copy(a);b.__dict__=copy.deepcopy({k:v for k,v in vars(a).items() if k not in ('market','facts')});b.market=a.market;b.facts=a.facts;return b

def event(r,m,at,opens,closes,e3):
 phase='OPEN' if at in opens else 'CLOSE' if at in closes else 'ACTION';m.set_phase(at,phase)
 for a in r.accounts.values():a.settle_due(at)
 r._actions(at)
 for a in r.accounts.values():r._payments(a,at)
 if phase=='OPEN':
  for a in r.accounts.values():
   bef=a.balance(at,m.marks(at,a.positions));nt=len(a.trades)
   r.opening(a,at)
   aft=a.balance(at,m.marks(at,a.positions));tr=a.trades[nt:]
   flow=sum((D(t['gross_cny'])-D(t['fees_cny']) if t['side']=='sell' else -D(t['gross_cny'])-D(t['fees_cny']) for t in tr),Z)
   gap=aft['available']+aft['order_reserved']+aft['sale_receivable']-bef['available']-bef['order_reserved']-bef['sale_receivable']-flow
   assert abs(gap)<D('1e-8'),('open cash bridge',a.label,at,gap)
   r.open_checks.append(dict(account=a.label,at=at,cash_gap=gap,buy_fills=sum(t['side']=='buy' for t in tr),sell_fills=sum(t['side']=='sell' for t in tr),available_before=bef['available'],available_after=aft['available'],pending_reserve=aft['order_reserved']))
 if phase=='CLOSE':
  r.planning(at)

def poison_future(m,at,ids):
 """Engineering-only mutation, restored before any CLOSE event. No source writes."""
 backup=[];day=pd.Timestamp(at.date());dv=day.value//86400000000000
 for sid in ids:
  ar=m.arr[sid];k=np.searchsorted(ar['days'],dv)
  for field in ('high','low','close','volume','valid'):
   old=ar[field];z=old.copy();backup.append(('array',ar,field,old));z[k:]=False if field=='valid' else (-999999.0 if field=='low' else 999999.0);ar[field]=z
  f=m._raw_source[sid];ix=f.index>=day
  # Only already-float source columns are changed. Public OPEN view exposes open alone.
  for field in ('high','low','close','volume'):
   old=f.loc[ix,field].copy();backup.append(('frame',f,(ix,field),old));f.loc[ix,field]=(-999999.0 if field=='low' else 999999.0)
 return backup

def unpoison(backup):
 for kind,obj,key,value in reversed(backup):
  if kind=='array':obj[key]=value
  else:obj.loc[key[0],key[1]]=value

def metrics(r):
 out=[];periods=[]
 for label in r.accounts:
  rows=[x for x in r.daily if x['account']==label];previous=CAPITAL
  for year in sorted({x['at'].year for x in rows}):
   rr=[x for x in rows if x['at'].year==year];vals=np.array([float(previous)]+[float(x['nav']) for x in rr]);peak=np.maximum.accumulate(vals)
   trades=[t for t in r.accounts[label].trades if t['at'].year==year]
   out.append(dict(account=label,year=year,start_NAV=str(previous),end_NAV=str(rr[-1]['nav']),return_fraction=float(rr[-1]['nav']/previous-1),max_drawdown_fraction=float(np.min(vals/peak-1)),days=len(rr),mean_inventory_fraction=float(np.mean([float(x['inventory']/x['nav'])for x in rr])),mean_stock_count=float(np.mean([len(x['positions'])for x in rr])),buy_fills=sum(t['side']=='buy' for t in trades),sell_fills=sum(t['side']=='sell' for t in trades),fees=str(sum((D(t['fees_cny'])for t in trades),Z)),ending_cash=str(rr[-1]['available']),ending_dividend_receivable=str(rr[-1]['dividend_receivable'])))
   previous=rr[-1]['nav']
  # All quarters, plus two dates already specified before this account experiment.
  windows=[(str(p),str(p.start_time.date()),str(p.end_time.date())) for p in pd.period_range('2022Q1','2026Q2',freq='Q')]
  windows += [('2024_0924_1008','2024-09-24','2024-10-08'),('2026_0115_0130','2026-01-15','2026-01-30')]
  for name,start,end in windows:
   rr=[x for x in rows if start<=str(x['at'].date())<=end]
   if not rr:continue
   prior=[x for x in rows if str(x['at'].date())<start];base=prior[-1]['nav']if prior else CAPITAL;vs=np.array([float(base)]+[float(x['nav'])for x in rr]);pk=np.maximum.accumulate(vs)
   periods.append(dict(account=label,period=name,start=str(rr[0]['at'].date()),end=str(rr[-1]['at'].date()),start_NAV=str(base),end_NAV=str(rr[-1]['nav']),return_fraction=float(rr[-1]['nav']/base-1),max_drawdown_fraction=float(np.min(vs/pk-1)),mean_inventory_fraction=float(np.mean([float(x['inventory']/x['nav'])for x in rr])),mean_stock_count=float(np.mean([len(x['positions'])for x in rr]))))
 return out,periods

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',default='run');z=ap.parse_args();out=ROOT/z.out
 assert out.resolve().parent==ROOT.resolve(), 'Output must be one fresh direct child of isolated study root'
 assert not out.exists(),'Never overwrite or implicitly rerun an account'
 out.mkdir(parents=True);started=time.monotonic();r=None;m=None;last=None
 try:
  assert read(S/'factors/SUMMARY.json')['passed']
  H.verify_static_freeze(ROOT)
  H.install_dispatch(J.M.E.risk_policy)
  H.static_checks(J,ROOT,save)
  baseline=H.Baseline(S/'run_1200000',canon,save,out)
  baseline.verify_frozen_original_sources()
  print('LOAD_CONTINUOUS_INPUTS',flush=True);shared,receipts,cp,states,ir,identity=C.inputs()
  print('INPUTS_READY',round(time.monotonic()-started,1),flush=True)
  b,original_market,original_facts=shared;timelines={};no_factor_source=[]
  for sid,raw in original_market.raw.items():
   if raw.empty:no_factor_source.append(sid);continue
   timelines[sid]=OpenFactorTimeline(raw,original_market.actions.get(sid,[]),method=b.series[sid].record['adjustment']['method'],end=END)
  factors=FactorSource(timelines)
  # Original B financial policy in both arms, same initial empty ledger and industry warm state.
  r=A.Runner(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir)
  base=r.accounts['B']
  assert not base.positions and not base.trades and not base.buys and not base.exits and not base.budget.lots and not base.budget.orders
  base.available=CAPITAL;base.initial_cash=CAPITAL;base.current_nav=CAPITAL;base.minimum_available=CAPITAL;base.budget.cash=float(CAPITAL)
  base.risk_state=dict(on=True,peak=CAPITAL,saw_off=False,previous_fast=False,episode=0)
  assert base.budget.exhausted_policy=='record_only' # Original shared-loss threshold is diagnostic, not an admission override.
  assert base.available==base.initial_cash==base.current_nav==base.minimum_available==D(str(base.budget.nav))==CAPITAL
  other=clone_account(base)
  assert digest({k:v for k,v in vars(base).items() if k not in ('market','facts')})==digest({k:v for k,v in vars(other).items() if k not in ('market','facts')})
  base.label='PVR';other.label='NOACT';r.accounts={'PVR':base,'NOACT':other}
  H.assert_isolation(r)
  save(out/'INITIAL_DEEP_ISOLATION.json',H.assert_deep_initial_isolation(r))
  m,f=attach(original_market,original_facts,factors,J.C.L);r.market=m;r.facts=f
  for a in r.accounts.values():a.market=m;a.facts=f
  r.open_checks=[]
  r.assert_native_wiring()
  e3=None # No E31 source or ranking adapter participates.
  r.source_freeze=A.source_freeze()
  for p,h in N.SCORES.source_manifest_sha256.items():r.source_freeze[p]=h
  for p in [Path(__file__),O/'continuous_execution.py',O/'ablation_support.py',ROOT/'CONTRACT.md',ROOT/'STATIC_FREEZE.json',S/'factors/continuous_factors.py',S/'factors/SUMMARY.json',S/'inputs/continuous_inputs.py',S/'inputs/H1_MANIFEST.json',S/'inputs/SOURCE_FREEZE.json']:
   r.source_freeze[str(p)]=sha(p)
  r.source_freeze.update(H.freeze_loaded_sources())
  H.check_native_wiring(r,J,A)
  save(out/'RUNTIME_DEPENDENCY_FREEZE.json',r.source_freeze)
  # Original common ACT/close clock, no annual resets and no old account import.
  J.M.E.risk_policy.RECOVERY=pd.read_csv(J.M.O/'recovery.csv',index_col=0,parse_dates=True).loc[:END]
  lo=J.M.N.iso(START+'T00:00:00+08:00');hi=J.M.N.iso(END+'T15:10:00+08:00')
  opens={x for x in m.sessions['A']if lo<=x<=hi};closes={x for x in m.cutoffs if lo<=x<=hi}
  actions={datetime.combine(datetime.fromisoformat(d).date(),dtime.min,J.M.N.TZ) for d in r.actions_by_date}
  events=sorted(opens|closes|{x for x in actions if lo<=x<=hi});assert max(closes)==hi
  save(out/'PREDECLARED.json',dict(start=START,end=END,arms=['PVR','NOACT'],sole_strategy_change='NOACT risk_policy.step routes to original CONTROL noop; PVR ACT20_BREAK unchanged',both_arms_rank='Original PVR_SLOT1',original_baseline=str(S/'run_1200000'),initial_cash_each=str(CAPITAL),initial_holdings_empty=True,account_history_imported=False,one_execution_assumption='known positive open +/-5bps; prior20positivevolume1%; historical tradability UNKNOWN',fixed_future_pool=1709,PIT_claim=False,action_terms_assumed_preknown=True,annual_resets=False,new_score_grid=False,score_identity=identity['score_manifest_sha256'],input_identity=identity,source_freeze=r.source_freeze,no_factor_source=no_factor_source,periods='all calendar quarters plus prior-specified 2024/09/24-10/08 and 2026/01/15-01/30',big_episode_definition='Frozen original-I complete60 labels, close MFE>=30% and terminal>=20%; same 1709 pool; report actual held early6 sessions, not proposal selection.'))
  gate_done=False;fixed_gates=[]
  with IO.atomic_runner_outputs(r,L,out,canonicalize=canon):
   for at in events:
    is_initial_gate=not gate_done and at in opens and at.date().isoformat()>='2022-02-01'
    is_divergent_gate=at in opens and at.date().isoformat()=='2022-04-22'
    if is_initial_gate or is_divergent_gate:
     report=H.replay_open_gate(r,m,at,last,opens,closes,e3,event,payload,digest,poison_future,unpoison,out,save,initial=is_initial_gate)
     fixed_gates.append(report);gate_done=True
     print('RESTART_OPEN_ORDER_GATE_PASS',str(at),flush=True)
    else:event(r,m,at,opens,closes,e3)
    H.assert_isolation(r)
    if at in closes:
     baseline.check_close(r,at)
     assert r.accounts['NOACT'].risk_state['on'] is True
     if str(at.date()) in H.FIXED_DATES:
      H.fixed_event_check(r,at,baseline,out,save)
    last=at
    if at in closes and (pd.Timestamp(at.date())+pd.offsets.BDay()).month!=at.month:
     print('MONTH',str(at.date()),{k:str(a.current_nav)for k,a in r.accounts.items()},'elapsed',round(time.monotonic()-started,1),flush=True)
    if at in closes and at.month==12 and at.day>=28:
     nxt=[x for x in closes if x>at and x.year==at.year]
     if not nxt:r.checkpoint(out/'latest_checkpoint',last)
   assert gate_done and len(fixed_gates)==2
   baseline.finish_daily(r)
   r.checkpoint(out/'latest_checkpoint',last);r.dump_joint(out/'pair')
  H.final_exact_regression(out,S/'run_1200000',save)
  H.verify_static_freeze(ROOT)
  baseline.verify_original_outputs()
  for p,h in r.source_freeze.items():assert sha(p)==h,('source drift',p)
  annual,periods=metrics(r)
  save(out/'ANNUAL_METRICS.json',annual);save(out/'PERIOD_METRICS.json',periods)
  IO.write_gzip_jsonl(out/'OPEN_CASH_CHECKS.jsonl.gz',r.open_checks,encoder=J.C.encoded)
  IO.write_gzip_jsonl(out/'SHARED_WINDOW_AUDIT.jsonl.gz',m.exec_rows,encoder=J.C.encoded)
  H.finish_metrics_and_hashes(out,save)
  save(out/'DONE.json',dict(completed=True,last_event=last,seconds=time.monotonic()-started,daily_rows=len(r.daily),open_checks=len(r.open_checks),baseline_daily_exact=baseline.days,baseline_trades_exact=baseline.trades_checked,ACT_only=True,shared_window_counts=dict(m.exec_counts),final_nav={k:str(a.current_nav)for k,a in r.accounts.items()},source_files_unchanged=True,real_orders=False,study_label='FIXED_FUTURE_1709_POOL_CAUSAL_OPEN_PROXY_NOT_PIT_TRADABLE'))
  H.hash_outputs(out,save)
  print('DONE',round(time.monotonic()-started,1),flush=True)
 except BaseException as exc:
  save(out/'FAILURE.json',dict(error=str(exc),traceback=traceback.format_exc(),last_complete_event=last,account_started=r is not None,failed_event=locals().get('at'),partial_event_not_resumable=True,auto_retry=False))
  if r is not None and last is not None:
   try:
    IO.write_pickle(out/'PARTIAL_STATE_NOT_RESUMABLE.pkl',dict(status='PARTIAL_FAILED_EVENT_NOT_A_CHECKPOINT',failed_event=locals().get('at'),last_complete_event=last,diagnostic_payload=payload(r)))
   except Exception as err:save(out/'FAILURE_SNAPSHOT_ERROR.json',dict(error=str(err)))
  raise
if __name__=='__main__':main()
