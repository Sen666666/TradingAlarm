from common import *
import gzip,collections

def main():
 out=HERE/'entry-attribution';out.mkdir(exist_ok=False);cams=pd.read_csv(ABCD/'analysis/campaigns.csv');cams=cams[cams.account.eq('A__S0_base')];obj=read(ABCD/'technical/A-controls/A__S0_base.json');res={r['order_id']:r['decision_at'][:10] for r in obj['audit_log'] if r['kind']=='reserve'};first={};fills=[]
 for r in obj['audit_log']:
  if r['kind']=='fill' and r['receipt']['side']=='buy':
   first.setdefault((r['receipt']['security_id'],r['receipt']['at']),res[r['order_id']]);fills.append((r,res[r['order_id']]))
 eligible=collections.defaultdict(list);counts=[]
 with gzip.open(ABCD/'technical/A-controls/decisions.jsonl.gz','rt') as f:
  for line in f:
   r=json.loads(line);day=r['at'][:10]
   if r['account']!='A__S0_base' or not START<=day<=END:continue
   counts.append(dict(date=day,eligible=len(r['eligible']),positions=sum(o['has_position'] for o in r['occupancy'])))
   for e in r['event_eligibility']:
    if e['q'] is True:eligible[e['symbol']].append(day)
 result=[];bridge=[];gaps=[]
 for sid,g in cams.groupby('symbol'):
  f=pd.read_parquet(IX/'signals'/f'{sid}.parquet',columns=['open','close','ix_target','ix_floor','IX','grade']);target=f.ix_target.to_numpy(bool);ep=np.cumsum(target&~np.r_[False,target[:-1]]);ixindex={str(t.date()):i for i,t in enumerate(f.index)};eq={}
  for day in eligible[sid]:
   i=ixindex.get(day)
   if i is not None and target[i]:eq.setdefault(ep[i],i)
  for _,c in g.iterrows():
   entry=c.entry_at[:10];decision=first[sid,c.entry_at];i=ixindex.get(entry);j=ixindex.get(decision);exit=c.exit_at[:10] if isinstance(c.exit_at,str) else None;k=ixindex.get(exit)
   if i is not None and j is not None:
    rawopen=float(f.open.iloc[i]);floor=float(f.ix_floor.iloc[j]);bad=math.isfinite(floor) and rawopen<=floor
    if bad:gaps.append(dict(symbol=sid,entry=entry,decision=decision,signal_open=rawopen,signal_floor=floor,net_pnl=float(c.net_pnl),net_return=float(c.net_return)))
   if i is not None and k is not None and c.buy_fills==1 and c.sell_fills==1:
    normalized=f.open.iloc[k]/f.open.iloc[i]*(1-.0005)/(1+.0005)*(1-.0005)/(1+.0005)-1;bridge.append(dict(symbol=sid,entry=entry,exit=exit,actual_net_return=c.net_return,normalized_same_entry_exit=float(normalized),difference=float(normalized-c.net_return)))
   if not START<=entry<=END or k is None or exit>END or i is None or j is None or ep[j] not in eq:continue
   q=eq[ep[j]];early=q+1
   # Earliest q here is an already eligible SAME-EPISODE opportunity, not a
   # hindsight winner/low. Check next observed open and the old protection.
   while early<i and early<len(f) and float(f.open.iloc[early])<=float(f.ix_floor.iloc[early-1]):
    candidates=[a for a in range(early,len(f)) if ep[a]==ep[j] and target[a] and f.IX.iloc[a]]
    if not candidates:break
    early=candidates[0]+1
   if early>i or early>=len(f):continue
   p0=float(f.open.iloc[early]);p1=float(f.open.iloc[i]);end=float(f.open.iloc[k]);cost=(1-.0005)/(1+.0005)*(1-.0005)/(1+.0005)
   result.append(dict(symbol=sid,entry=entry,exit=exit,first_eligible=str(f.index[q].date()),reference_entry=str(f.index[early].date()),lag_observations=int(i-early),already_risen=p1/p0-1,early_same_exit_return=end/p0*cost-1,actual_time_same_exit_return=end/p1*cost-1,actual_account_return=float(c.net_return),actual_account_pnl=float(c.net_pnl),episode_start_before_window=bool(f.index[np.flatnonzero(ep==ep[j])[0]]<pd.Timestamp(START))))
 a=pd.DataFrame(result);b=pd.DataFrame(bridge);pd.DataFrame(gaps).to_csv(out/'gap-floor-buys.csv',index=False);a.to_csv(out/'same-episode-entry-pairs.csv',index=False);b.to_csv(out/'price-bridge.csv',index=False);pd.DataFrame(counts).to_csv(out/'daily-candidates.csv',index=False)
 s=dict(recorded_at=now(),pairs=len(a),median_entry_lag=float(a.lag_observations.median()),mean_entry_lag=float(a.lag_observations.mean()),mean_already_risen=float(a.already_risen.mean()),median_already_risen=float(a.already_risen.median()),early_reference_mean_return=float(a.early_same_exit_return.mean()),actual_time_mean_return=float(a.actual_time_same_exit_return.mean()),early_win_actual_loss=int(((a.early_same_exit_return>0)&(a.actual_time_same_exit_return<0)).sum()),gap_guard_violating_campaigns=len(gaps),gap_campaign_pnl=sum(g['net_pnl'] for g in gaps),bridge_single_fill_pairs=len(b),bridge_median_abs_difference=float(b.difference.abs().median()),bridge_abs_difference_over_10pct=int(b.difference.abs().gt(.1).sum()),mean_daily_eligible=float(pd.DataFrame(counts).eligible.mean()),median_daily_eligible=float(pd.DataFrame(counts).eligible.median()),not_additive_portfolio_counterfactual=True)
 write(out/'summary.json',s);print(s,flush=True)
if __name__=='__main__':main()
