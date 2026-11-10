"""Causal signed-return / original amount transform divergence, no account run."""
from pathlib import Path
from decimal import Decimal as D, getcontext
from collections import defaultdict
import json, hashlib, datetime
import pandas as pd
import numpy as np

getcontext().prec=50
O=Path(__file__).resolve().parent
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
M=B/'risk_constraints/ma63_information_diagnostic_v1'
SRC={};CACHE={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);SRC[str(p)]=sha(p);return json.loads(p.read_text())
def save(name,x):
 with (O/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str,allow_nan=False)
def scalar(x):
 if pd.isna(x):return None
 if isinstance(x,(np.bool_,bool)):return bool(x)
 if isinstance(x,(np.integer,int)):return int(x)
 if isinstance(x,(np.floating,float)):return float(x)
 return str(x)
def agg(rows):
 cost=sum((D(x['cost']) for x in rows),D(0));net=sum((D(x['net']) for x in rows),D(0))
 return dict(layers=len(rows),stocks=len({x['sid'] for x in rows}),cost=cost,net=net,
  positive_net=sum((D(x['net']) for x in rows if D(x['net'])>0),D(0)),negative_net=sum((D(x['net']) for x in rows if D(x['net'])<0),D(0)),
  open_layers=sum(bool(x['qty']) for x in rows),strict_realized=None if any('strict_realized' not in x for x in rows) else sum((D(x['strict_realized']) for x in rows),D(0)),
  open_unrealized=None if any('open_unrealized' not in x for x in rows) else sum((D(x['open_unrealized']) for x in rows),D(0)),
  dividend_AR=None if any('recognized_dividend_AR' not in x for x in rows) else sum((D(x['recognized_dividend_AR']) for x in rows),D(0)))

def main():
 smp=W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json';sm={x['symbol']:x for x in read(smp)}
 entries={ref:read(M/(ref+'_ENTRIES.json')) for ref in ['2022_2024','strong']}
 tails=read(M/'ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json')['members']
 formula_source=W/'pvr-current-v3-information-capital-20261101/original_score_function.py'
 act_source=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/desk/refresh.py')
 SRC[str(formula_source)]=sha(formula_source);SRC[str(act_source)]=sha(act_source)
 save('PROTOCOL.json',dict(frozen_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
  problem='Daily raw return versus original signed amount transforms and original smoothing; all old funded layers and all fixed old tails, not policy returns',
  pvr='r=logC diff; s=1.4826 median previous63 abs r; u=tanh(r/s); b=tanh(log(amount/prior21median)); e=u*(1+.5*abs(u)*b); E=normalized .9**[20..0] weighted previous/current21 e; unweighted-price comparison uses identical weighted u',
  act='original eligible observed nonsynthetic source by segment; x=r*min(1,sqrt(amount/prior21median)); mom=EW span21 adjustFalse; first64 observations unknown; price comparison EW same r, identical mask',
  same_day_sign_invariant='sign(e)=sign(r), sign(x)=sign(r), positive finite multipliers; any direction difference is smoothing or different underlying directional summary',
  flags=['pvr_daily_down_smooth_positive','act_daily_down_smooth_positive','pvr_amount_smooth_positive_price_smooth_nonpositive','act_amount_smooth_positive_price_smooth_nonpositive'],
  historical_scope='latest and all occurrences only within the currently active original stock I-target episode up through decision CLOSE; no arbitrary lookback window; original I episode may be long, so any-past flags are descriptive',
  mothers='2265 2022-24/1557 2022-23/303 actual postOct8 fills; 1171 strong; full original tails83/94 including unmatched',
  account_events=0,new_signals=0,threshold_search=0,external_actions=0))
 weights=.9**np.arange(20,-1,-1);weights/=weights.sum()
 flags=['pvr_daily_down_smooth_positive','act_daily_down_smooth_positive','pvr_amount_smooth_positive_price_smooth_nonpositive','act_amount_smooth_positive_price_smooth_nonpositive']
 def frame(sid):
  if sid in CACHE:return CACHE[sid]
  m=sm[sid]
  def parquet(key,cols=None):
   p=Path(m['refs'][key]);assert sha(p)==m['output_sha256'][str(p)];SRC[str(p)]=sha(p);return pd.read_parquet(p,columns=cols)
  inp=parquet('CP1_input');cp=parquet('CP1');facts=parquet('facts',['i_target','segment_id'])
  z=pd.DataFrame(index=inp.index)
  for c in ['r','u','m','s','B','receipt','reset_reason','candidate','frontier','phase']:z['cp1_'+c]=cp[c]
  z['close']=inp.close;z['amount']=inp.amount;z['segment_id']=inp.segment_id;z['i_target']=facts.i_target
  # Exact original finite-window PVR; CP1 inputs already have original valid observation selection.
  for _,g in inp.groupby('segment_id',sort=False):
   r=np.log(g.close).diff();s=r.abs().shift().rolling(63,min_periods=63).median().mul(1.4826).clip(lower=1e-8)
   ar=g.amount.shift().rolling(21,min_periods=21).median();u=np.tanh(r/s);b=np.tanh(np.log(g.amount/ar));e=u*(1+.5*u.abs()*b)
   E=e.rolling(21,min_periods=21).apply(lambda a:np.dot(weights,a),raw=True)
   pure=u.rolling(21,min_periods=21).apply(lambda a:np.dot(weights,a),raw=True)
   np.testing.assert_allclose(r,cp.loc[g.index,'r'],rtol=0,atol=0,equal_nan=True)
   np.testing.assert_allclose(u,cp.loc[g.index,'u'],rtol=0,atol=0,equal_nan=True)
   for k,v in dict(pvr_r=r,pvr_u=u,pvr_b=b,pvr_e=e,pvr_E=E,pvr_price_smooth=pure).items():z.loc[g.index,k]=v
  source=[p for p in m['source_sha256'] if p.endswith('/signal.parquet')]
  assert len(source)==1,(sid,source)
  p=Path(source[0]);assert sha(p)==m['source_sha256'][str(p)];SRC[str(p)]=sha(p)
  signal=pd.read_parquet(p,columns=['close','amount','segment_id','price_eligible','observed_bar','synthetic_event_bar'])
  valid=signal.price_eligible&signal.observed_bar&~signal.synthetic_event_bar
  act=pd.DataFrame(index=signal.index)
  for _,g in signal.loc[valid].groupby('segment_id',sort=False):
   r=np.log(g.close).diff();q=g.amount/g.amount.shift().rolling(21,min_periods=21).median();w=np.minimum(1,np.sqrt(q));x=r*w;mom=x.ewm(span=21,adjust=False).mean();pure=r.ewm(span=21,adjust=False).mean()
   ready=np.arange(len(g))>=64;mom.iloc[:64]=np.nan;pure.iloc[:64]=np.nan
   for k,v in dict(act_r=r.where(ready),act_multiplier=w,act_x=x,act_mom=mom,act_price_smooth=pure).items():act.loc[g.index,k]=v
  z=z.join(act)
  z['pvr_daily_down_smooth_positive']=(z.pvr_r<0)&(z.pvr_E>0)
  z['act_daily_down_smooth_positive']=(z.act_r<0)&(z.act_mom>0)
  z['pvr_amount_smooth_positive_price_smooth_nonpositive']=(z.pvr_E>0)&(z.pvr_price_smooth<=0)
  z['act_amount_smooth_positive_price_smooth_nonpositive']=(z.act_mom>0)&(z.act_price_smooth<=0)
  ok=z.pvr_e.notna()&z.pvr_r.notna();assert ((np.sign(z.loc[ok,'pvr_e'])==np.sign(z.loc[ok,'pvr_r']))).all()
  ok=z.act_x.notna()&z.act_r.notna();assert ((np.sign(z.loc[ok,'act_x'])==np.sign(z.loc[ok,'act_r']))).all()
  # Original I episode identity only, not outcome or account history.
  episode=(z.segment_id.ne(z.segment_id.shift())|~z.i_target.eq(1)|~z.i_target.shift().eq(1)).cumsum()
  z['I_episode']=episode.where(z.i_target.eq(1))
  for flag in flags:
   # A reset/unknown does not carry historical positive evidence into a new I episode.
   for _,g in z.loc[z.I_episode.notna()].groupby('I_episode',sort=False):
    history=pd.Series(pd.NaT,index=g.index,dtype='datetime64[ns]');history.loc[g[flag]]=g.index[g[flag]]
    z.loc[g.index,flag+'_latest']=history.ffill();z.loc[g.index,flag+'_count']=g[flag].cumsum()
  CACHE[sid]=z;return z
 def enrich(e):
  x=dict(e);z=frame(x['sid']);d=pd.Timestamp(x['decision_at'][:10]);assert d in z.index
  r=z.loc[d];unknown=not all(pd.notna(r[k]) for k in ['pvr_r','pvr_e','pvr_E','act_r','act_x','act_mom'])
  cols=['close','amount','segment_id','i_target','I_episode','cp1_r','cp1_u','cp1_m','cp1_s','cp1_B','cp1_receipt','cp1_reset_reason','cp1_candidate','cp1_frontier','cp1_phase','pvr_r','pvr_u','pvr_b','pvr_e','pvr_E','pvr_price_smooth','act_r','act_multiplier','act_x','act_mom','act_price_smooth']
  x['direction_snapshot']={k:scalar(r[k]) for k in cols};x['unknown']=unknown
  x['divergence']={}
  for flag in flags:
   latest=r.get(flag+'_latest');dlast=None if pd.isna(latest) else pd.Timestamp(latest)
   old=None if dlast is None else z.loc[dlast]
   x['divergence'][flag]=dict(current=bool(r[flag]),ever_in_current_I_episode=dlast is not None,latest_day=None if dlast is None else str(dlast.date()),count=0 if pd.isna(r.get(flag+'_count')) else int(r[flag+'_count']),
    latest_snapshot=None if old is None else {k:scalar(old[k]) for k in cols},
    fresh_CP1_after_prior_divergence=bool(r.cp1_receipt) and dlast is not None and dlast<d)
  return x
 out={};allrows={};alltails={}
 for ref,rows in entries.items():
  rr=[enrich(x) for x in rows];allrows[ref]=rr
  scopes={'ALL':rr}
  if ref=='2022_2024':
   scopes['2022_2023']=[x for x in rr if x['opened'][:10]<='2023-12-29'];scopes['strict303_postOct8']=[x for x in rr if '2024-10-08'<x['opened'][:10]<='2024-12-31'];assert len(scopes['strict303_postOct8'])==303
  summary={}
  for scope,sr in scopes.items():
   item={'all':agg(sr),'unknown':agg([x for x in sr if x['unknown']]),'flags':{}}
   for flag in flags:
    current=[x for x in sr if x['divergence'][flag]['current']]
    past=[x for x in sr if x['divergence'][flag]['ever_in_current_I_episode']]
    restored=[x for x in sr if x['role']=='mobile' and x['divergence'][flag]['fresh_CP1_after_prior_divergence']]
    item['flags'][flag]=dict(current=agg(current),ever_in_current_I_episode=agg(past),fresh_mobile_after_prior_divergence=agg(restored),
     confirmed_fresh_mobile_after_prior_divergence=agg([x for x in restored if x['pool_at_fill']=='confirmed']),
     current_by_action={a:agg([x for x in current if x['action']==a]) for a in sorted({x['action'] for x in sr})})
   summary[scope]=item
  controls=read(M/(ref+'_ORIGINAL_FIXED_TAIL_COVERAGE.json'));ct=[]
  bylayer={x['layer']:x for x in rr}
  for e,c in zip(tails[ref],controls):
   assert e['budget_order']==c['original']['budget_order'];x=enrich(e);x['matched_No60_layers']=c['matched_No60_layers'];x['matched_No60_money']=agg([bylayer[k] for k in c['matched_No60_layers']]);ct.append(x)
  alltails[ref]=ct
  fixed={'all':agg(ct),'matched_original_members':sum(bool(x['matched_No60_layers']) for x in ct),'flags':{}}
  for flag in flags:
   fixed['flags'][flag]={level:agg([x for x in ct if x['divergence'][flag][level]]) for level in ['current','ever_in_current_I_episode','fresh_CP1_after_prior_divergence']}
  out[ref]=dict(scopes=summary,fixed_original_tails=fixed)
  save(ref+'_ROWS.json',rr);save(ref+'_FIXED_ORIGINAL_TAILS.json',ct)
  print(ref,'done',len(CACHE),'stocks',flush=True)
 cases=['002969.SZ','688146.SH','601595.SH','301319.SZ','000620.SZ']
 case_data={}
 for sid in cases:
  selected=[x for rr in allrows.values() for x in rr if x['sid']==sid]
  if not selected:continue
  z=frame(sid);case_data[sid]=selected
  lo=min(x['decision_at'][:10] for x in selected);hi=max((x['closed'] or x['opened'])[:10] for x in selected)
  z.loc[lo:hi].to_csv(O/(sid+'_DAILY.csv'))
 save('FIXED_CASE_ENTRY_ROWS.json',case_data);save('RESULTS.json',out)
 save('SOURCE_MANIFEST.json',dict(sources=SRC,script_sha256=sha(__file__),stocks=len(CACHE),new_accounts=0,new_signals=0,
  limitations=['all historical development with current survivors/current sectors','divergence flags are associations, no deleted-PnL or policy counterfactual','daily down versus positive smoother is ordinary inertia even without amount','I episode history may be long and all-past flag is not a timing classifier','PVR and ACT have different transforms/scales; do not mix their r/level','original fixed tails include open marks and unpaid dividends; unmatched remain explicit']))
 print('COMPLETE',flush=True)
if __name__=='__main__':main()
