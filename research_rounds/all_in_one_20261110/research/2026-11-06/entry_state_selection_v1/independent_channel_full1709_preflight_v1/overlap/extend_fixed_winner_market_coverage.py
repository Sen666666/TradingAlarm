"""Frozen outcome-selected diagnostic of full old winner holding windows. No economics."""
from pathlib import Path
import sys,json,hashlib,time
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;N=O.parent;R=N.parent;E=R/'m3_stock_birth_during_sector_v1'
sys.path.insert(0,str(N));import engine as e
from fast_core import simulate
H=e.H

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
assert not (O/'WINNER_FULL_HOLD_RUN_ONCE.json').exists()
seal=json.loads((N/'FINAL_MARKET_SEAL.json').read_text())['files']
for name in ['engine.py','fast_core.py','DAILY_STATES.parquet','PROTOCOL.md']:
 assert sha(N/name)==seal[name]
legacy=[E/'relative_priority_equity_run_2022_v1/report/CORE_AND_FULL_ROUNDS.csv',E/'cash_equity_baseline_2024_v1/report/CORE_AND_FULL_ROUNDS.csv']
# Membership is explicitly historical/outcome-selected, not an OOS validation set.
parts=[]
for path in legacy:
 z=pd.read_csv(path,low_memory=False);z=z[z.arm.eq('A_UNION_B')&z.evidence_usable_closed.eq(True)&z.core_return.ge(.5)].copy();parts.append(z)
z=pd.concat(parts,ignore_index=True)
for c in ['signal_day','entry_day','exit_day']:z[c]=pd.to_datetime(z[c],format='mixed')
z['window']=z.window.astype(str)
assert z.groupby('window').size().to_dict()=={'2022':44,'2024_924':64}
cohort=z[['round_id','window','sid','name','industry','sector','signal_day','entry_day','exit_day']].copy();cohort.to_csv(O/'WINNER_FULL_HOLD_FIXED_COHORT.csv',index=False)
hashes={str(p):sha(p) for p in [*legacy,N/'engine.py',N/'fast_core.py',N/'PROTOCOL.md',N/'FINAL_MARKET_SEAL.json',O/'WINNER_FULL_HOLD_FIXED_COHORT.csv',Path(__file__)]}
for sid in sorted(cohort.sid.unique()):
 mm=e.manifest[sid]
 for p in [next(p for p in mm['source_sha256'] if p.endswith('/signal.parquet')),mm['refs']['facts'],mm['refs']['CP1']]:
  expected=mm['source_sha256'].get(p,mm['output_sha256'].get(p));assert sha(p)==expected;hashes[p]=expected
save('WINNER_FULL_HOLD_RUN_ONCE.json',dict(started_utc=str(pd.Timestamp.now(tz='UTC')),rounds=108,stocks=cohort.sid.nunique(),scope='Fixed old financially covered CORE >=50% rounds only; diagnostic membership is outcome-selected. Frozen formula and no tuning.',source_hashes=hashes,new_account_runs=0,new_fills=0,new_returns=0))
old=pd.read_parquet(N/'DAILY_STATES.parquet');old=old[old.sid.isin(cohort.sid)]
cal=e.full_cal;ci={d:i for i,d in enumerate(cal)};states=[];rows=[];checks=0;began=time.monotonic()
for n,(sid,rs) in enumerate(cohort.groupby('sid',sort=True)):
 cut=rs.exit_day.max();q=e.data(sid,cut);xx=simulate(q)
 oldsid=old[old.sid.eq(sid)&old.day.le(cut)].set_index('day')
 cols=['valid','born','receipt','active','failed','root_unknown','root_day','a_day','U','B','R','Q','F','S_old','S_new','phase','E0','I','G','i_buy','CP']
 pd.testing.assert_frame_equal(xx.loc[oldsid.index,cols],oldsid[cols],check_dtype=False,check_exact=True,check_freq=False)
 checks+=len(oldsid)
 for rr in rs.itertuples():
  interval=xx.loc[rr.signal_day:rr.exit_day].copy();interval['sid']=sid;interval['window']=rr.window;interval['round_id']=rr.round_id
  interval['in_original_entry_to_exit_close_interval']=(interval.index>=rr.entry_day)&(interval.index<rr.exit_day)
  states.append(interval.reset_index())
  hold=xx[(xx.index>=rr.entry_day)&(xx.index<rr.exit_day)];receipts=hold[hold.receipt];births=hold[hold.born]
  sig=xx.loc[rr.signal_day];root=sig.root_day;linked=hold[hold.root_day.eq(root)] if pd.notna(root) else hold.iloc[0:0]
  terminal=linked[linked.failed|linked.root_unknown];first=terminal.iloc[0] if len(terminal) else None;fd=terminal.index[0] if len(terminal) else pd.NaT
  sale=cal[ci[fd]+1] if first is not None and first.failed and ci[fd]+1<len(cal) else pd.NaT
  after=receipts[receipts.index>fd] if first is not None and first.failed else receipts.iloc[0:0]
  afternew=after[after.root_day.gt(fd)]
  clock='NO_ACTIVE_PRICE_ROOT_AT_OLD_SIGNAL' if not sig.active else 'UNKNOWN_SOURCE_OR_PRICE_BOUNDARY' if first is not None and first.root_unknown else 'SAME_OPEN_AS_OLD_EXIT' if pd.notna(sale) and sale==rr.exit_day else 'EARLIER_OPEN_THAN_OLD_EXIT' if pd.notna(sale) and sale<rr.exit_day else 'NO_PRICE_FAILURE_BEFORE_OLD_EXIT'
  rows.append(dict(round_id=rr.round_id,window=rr.window,sid=sid,name=rr.name,industry=rr.industry,sector=rr.sector,old_signal_day=rr.signal_day,old_entry_day=rr.entry_day,old_exit_day=rr.exit_day,full_common_close_days=len(hold),price_known_days=int(hold.valid.sum()),price_unknown_days=int((~hold.valid).sum()),market_root_active_days=int(hold.active.sum()),fresh_receipts_entry_to_exit=len(receipts),market_roots_with_fresh_receipts=receipts.root_day.nunique(),new_births_entry_to_exit=len(births),first_fresh_receipt_entry_to_exit=receipts.index.min() if len(receipts) else pd.NaT,first_new_birth_entry_to_exit=births.index.min() if len(births) else pd.NaT,first_receipt_next_common_open=cal[ci[receipts.index.min()]+1] if len(receipts) and ci[receipts.index.min()]+1<len(cal) else pd.NaT,price_failures_in_hold=int(hold.failed.sum()),unknown_root_boundaries_in_hold=int(hold.root_unknown.sum()),root_at_old_signal=root,root_active_at_old_signal=bool(sig.active),first_signal_root_price_failure=fd if first is not None and first.failed else pd.NaT,first_signal_root_unknown_boundary=fd if first is not None and first.root_unknown else pd.NaT,first_signal_root_failure_next_open=sale,market_exit_clock_vs_old_exit=clock,fresh_receipts_after_signal_root_price_failure=len(after),later_new_roots_after_signal_root_price_failure=afternew.root_day.nunique(),first_later_new_root_receipt=afternew.index.min() if len(afternew) else pd.NaT,full_holding_calendar_exported=True,upstream_price_unknown_is_not_negative=True,actual_participation='NOT_SIMULATED',new_strategy_return='NOT_COMPUTED'))
 if (n+1)%20==0:print('WINNER_STOCKS',n+1,flush=True)
y=pd.concat(states,ignore_index=True);out=pd.DataFrame(rows)
y.to_parquet(O/'WINNER_FULL_HOLD_MARKET_STATES.parquet',index=False);y[y.receipt].to_parquet(O/'WINNER_FULL_HOLD_RECEIPTS.parquet',index=False);out.to_csv(O/'WINNER_FULL_HOLD_COVERAGE.csv',index=False)
summary=[]
for w,g in out.groupby('window'):
 d=dict(window=w,fixed_old_winners=len(g),stocks=g.sid.nunique(),all_original_entry_exit_clock_exported=bool(g.full_holding_calendar_exported.all()),winners_with_receipt_between_entry_exit=int(g.fresh_receipts_entry_to_exit.gt(0).sum()),winners_with_new_birth_between_entry_exit=int(g.new_births_entry_to_exit.gt(0).sum()),winners_with_price_unknown_inside_hold=int(g.price_unknown_days.gt(0).sum()),winners_with_unknown_root_boundary_inside_hold=int(g.unknown_root_boundaries_in_hold.gt(0).sum()),total_fresh_receipts=int(g.fresh_receipts_entry_to_exit.sum()),total_births=int(g.new_births_entry_to_exit.sum()),winners_with_later_new_root_after_first_signal_root_failure=int(g.later_new_roots_after_signal_root_price_failure.gt(0).sum()),actual_new_participation='NOT_SIMULATED')
 for c in ['NO_ACTIVE_PRICE_ROOT_AT_OLD_SIGNAL','UNKNOWN_SOURCE_OR_PRICE_BOUNDARY','SAME_OPEN_AS_OLD_EXIT','EARLIER_OPEN_THAN_OLD_EXIT','NO_PRICE_FAILURE_BEFORE_OLD_EXIT']:d[c]=int(g.market_exit_clock_vs_old_exit.eq(c).sum())
 summary.append(d)
pd.DataFrame(summary).to_csv(O/'WINNER_FULL_HOLD_SUMMARY.csv',index=False)
for p,h in hashes.items():assert sha(p)==h
save('WINNER_FULL_HOLD_QA.json',dict(passed=True,rounds=108,stocks=cohort.sid.nunique(),old_window_exact_comparison_rows=checks,state_rows=len(y),receipt_rows=int(y.receipt.sum()),all_source_hashes_unchanged=True,source_hashes=hashes,new_accounts=0,new_size_runs=0,new_fills=0,new_returns=0,seconds=time.monotonic()-began))
print(pd.DataFrame(summary).to_string(index=False));print('COMPLETE',round(time.monotonic()-began,1))
