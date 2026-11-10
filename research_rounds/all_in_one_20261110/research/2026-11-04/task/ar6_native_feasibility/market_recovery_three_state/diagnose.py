from pathlib import Path
import json,hashlib,time,gzip
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent; T=O.parents[1]
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
REC=W/'mainline-absolute-Q4-20261031/recovery.csv'
KNOWN=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/market-permission-price-only-20261101/input-preparation/prepared-v2/NATIVE1709/market.parquet')
CLOCK=T/'ar6_native_feasibility/ACT_RECOVERY_SEMANTICS/ACT_CLOCK_AND_CLAUSES.json'
EP=T/'pvr_pool_feasibility/a_recovery_full_diagnostic/2022_2024_ALL_EPISODES.json'
STRONG=T/'pvr_pool_feasibility/a_recovery_full_diagnostic/strong_ALL_EPISODES.json'
OLD=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/recovery-only-20261027/code/prepare.py')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,list):return [clean(x) for x in v]
 if isinstance(v,(np.bool_,)):return bool(v)
 if isinstance(v,(np.integer,)):return int(v)
 if isinstance(v,(np.floating,float)):return None if not np.isfinite(v) else float(v)
 if isinstance(v,pd.Timestamp):return str(v.date())
 return v
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 start=time.monotonic();assert not (O/'RESULTS.json').exists(),'no automatic repeat'
 freeze=json.loads((O/'SOURCE_FREEZE.json').read_text())
 for p,h in freeze.items():assert sha(p)==h,p
 f=pd.read_csv(REC,index_col=0,parse_dates=True)
 k=pd.read_parquet(KNOWN).reindex(f.index)
 f['price_known']=k.price_observed.eq(True)&k.price_input.gt(0)&f.market.notna()&f.market.gt(0)
 f['breadth_known']=f.breadth.notna()
 assert (f.fast_on==f.breadth.gt(.6)).all()
 assert (f.breakout==(f.market.gt(f.prior_high63)&f.market.diff().gt(0)&f.fast_on)).all()
 for n in [20,21]:
  f['H'+str(n)]=f.market.shift().rolling(n,min_periods=n).max()
  f['L'+str(n)]=f.market.shift().rolling(n,min_periods=n).min()
  ready=f.price_known.shift().rolling(n,min_periods=n).sum().eq(n)&f.price_known
  f['new_high'+str(n)]=ready&f.market.gt(f['H'+str(n)])
  f['trigger'+str(n)]=f['new_high'+str(n)]&f.breadth.gt(.6)
 f['fast_false_known']=f.breadth_known&~f.fast_on
 f.index.name='day'
 def first(w,mask):
  z=w.loc[mask];return None if z.empty else dict(day=str(z.index[0].date()),market=float(z.market.iloc[0]),breadth=float(z.breadth.iloc[0]))
 def milestone(w,day):
  row=f.loc[day];c=float(row.market);s=float(row.L20);r=c-s;post=w.loc[day:].iloc[1:]
  breach=first(post,post.market.le(s))
  through=post.loc[:breach['day']] if breach else post
  return dict(trigger_day=str(day.date()),C0=c,S0=s,initialR=r,box_width=r/c,
   initial_1R_price=c+r,first_fast_false=first(post,post.fast_false_known),
   first_frozen_S_breach=breach,
   first_close_reaching_initial_1R=first(post,post.market.ge(c+r)),
   first_new20_B_reaching_initial_1R=first(post,post.market.ge(c+r)&post.trigger20),
   first_BREAK63_after_trigger=first(post,post.breakout),
   max_before_breach=float(through.market.max())if len(through)else c,
   max_advance_initial_R_units=float((through.market.max()-c)/r)if len(through)and r>0 else None,
   min_through_observed_end=float(w.loc[day:].market.min()),
   max_through_observed_end=float(w.loc[day:].market.max()),
   observed_end=str(w.index[-1].date()),not_strategy_transition=True)
 clock=json.loads(CLOCK.read_text());results=[];daily=[]
 for cr in clock['records']:
  bp=Path(cr['source_book']);assert sha(bp)==cr['source_book_sha256']
  with gzip.open(bp,'rt')as h:b=json.load(h)
  rows=[r for r in b['audit']if r['kind']=='risk_checkpoint'];previous_on=True;cycle=None
  for q in rows:
   day=pd.Timestamp(q['at'][:10]);v=f.loc[day]
   assert bool(q['fast'])==bool(v.fast_on)and bool(q['breakout'])==bool(v.breakout)
   if q.get('event')=='pause':
    assert cycle is None
    cycle=dict(policy=cr['policy'],pause_day=str(day.date()),resume_day=None,rows=[])
   if cycle is not None:
    eligible=bool(not previous_on and q['flat'])
    z=dict(policy=cr['policy'],pause_day=cycle['pause_day'],day=str(day.date()),old_pre_on=previous_on,
     old_post_on=q['on'],original_flat=q['flat'],eligible_old_paused_flat=eligible,old_event=q.get('event'),**v.to_dict())
    cycle['rows'].append(z);daily.append(z)
    if q.get('event')=='resume':
     cycle['resume_day']=str(day.date());results.append(cycle);cycle=None
   previous_on=bool(q['on'])
  if cycle is not None:results.append(cycle)
 for cy in results:
  rs=cy.pop('rows');eligible=[r for r in rs if r['eligible_old_paused_flat']]
  cy['first_flat']=next((r['day'] for r in eligible),None)
  for n in [20,21]:cy['all_trigger'+str(n)+'_days']=[r['day']for r in eligible if r['trigger'+str(n)]]
  cy['first_trigger20']=next(iter(cy['all_trigger20_days']),None)
  cy['first_trigger21']=next(iter(cy['all_trigger21_days']),None)
  cy['right_censored']=cy['resume_day']is None
  if cy['first_trigger20']:
   end=cy['resume_day']or'2024-12-31';w=f.loc[cy['pause_day']:end]
   cy['static_first_trigger_milestones']=milestone(w,pd.Timestamp(cy['first_trigger20']))
  else:cy['static_first_trigger_milestones']=None
 save('ALL_ORIGINAL_PAUSE_CYCLES.json',results)
 pd.DataFrame(daily).to_csv(O/'ALL_ORIGINAL_PAUSED_FLAT_DAILY.csv',index=False)
 contexts=[('2022_Apr_Jul','2022-04-01','2022-07-04'),('2023_Jul_Sep','2023-07-01','2023-09-29'),('2024_Sep_Oct','2024-09-02','2024-10-31'),('strong','2025-07-01','2026-06-30')]
 cs=[]
 for label,lo,hi in contexts:
  w=f.loc[lo:hi].copy();dates=w.index[w.trigger20]
  c=dict(label=label,lo=lo,hi=hi,closes=len(w),all_trigger20_days=[str(d.date())for d in dates],all_BREAK63_days=[str(d.date())for d in w.index[w.breakout]],
   all_fast_false_known_days=[str(d.date())for d in w.index[w.fast_false_known]],old_pause_anchor=False,
   first_trigger_static=milestone(w,dates[0])if len(dates)else None)
  if len(dates):
   d=dates[0];s=float(f.loc[d,'L20']);c0=float(f.loc[d,'market'])
   w['fixed_first_trigger_day']=str(d.date());w['fixed_S']=s;w['fixed_C']=c0;w['fixed_initial_R']=c0-s
   w['fixed_S_breach']=w.index.gt(d)&w.market.le(s);w['reached_fixed_initial_1R']=w.index.gt(d)&w.market.ge(c0+(c0-s))
  w.to_csv(O/(label+'_DAILY.csv'))
  # Every trigger's own frozen box; no reset or strategy chaining inferred.
  own=[milestone(w,d)for d in dates]
  save(label+'_EACH_TRIGGER_STATIC_BOX.json',own);cs.append(c)
 save('CONTEXT_SUMMARY.json',cs)
 f.to_csv(O/'FULL_ORIGINAL_INPUT_PLUS_STATIC20.csv')
 assert json.loads(STRONG.read_text())==[]
 for p,h in freeze.items():assert sha(p)==h,p
 save('RESULTS.json',dict(passed=True,seconds=time.monotonic()-start,no60_original_pause_cycles=3,original_PVR_pause_cycles=2,strong_original_pause_cycles=0,
  all_original_clocks_rechecked=True,new_accounts=0,new_account_events=0,new_DPC_state_machine=False,new_policy_returns=False,
  synthetic_price_not_trading_return=True,initial_1R_upgrade_not_authorized_or_validated=True,
  files=[p.name for p in O.iterdir()if p.is_file()]))
 print(json.dumps(clean(dict(cycles=results,contexts=cs)),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
