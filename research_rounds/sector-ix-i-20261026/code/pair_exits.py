from sec_common import *
import collections

def main():
 out=HERE/'pairs';out.mkdir(exist_ok=False);scope=read(HERE/'scope.json');q=read(HERE/'pure-q-events.json')['events'];group={s:k for k,ids in scope['groups'].items() for s in ids};calendar=sorted({str(pd.Timestamp(x).date()) for x in read(OLD/'inputs-v2/market-rules.json')['calendars']['A']});nxt=dict(zip(calendar,calendar[1:]));rows=[];skips=collections.Counter();anchors=0
 for sid,k in group.items():
  f=pd.read_parquet(IX/'signals'/f'{sid}.parquet');ii=pd.read_parquet(HERE/'signals'/f'{sid}.parquet');ix=f.ix_target.to_numpy(bool);ep=np.cumsum(ix&~np.r_[False,ix[:-1]]);e0=f.e0_target.to_numpy(bool);ep0=np.cumsum(e0&~np.r_[False,e0[:-1]]);days=[str(x.date()) for x in f.index];index={d:i for i,d in enumerate(days)};last=f.index.searchsorted(END,side='right')-1;first={}
  for day in q.get(sid,[]):
   i=index.get(day)
   if i is not None and ix[i]:first.setdefault(int(ep[i]),i)
  exits={p:np.flatnonzero(~t) for p,t in [('IX',ix),('I',ii.i_target.to_numpy(bool))]}
  for episode,i in first.items():
   anchors+=1;entry=i+1
   if entry>last:skips['no_entry_before_end']+=1;continue
   if days[entry]!=nxt[days[i]] or f.segment_id.iloc[entry]!=f.segment_id.iloc[i]:skips['next_session_source_gap']+=1;continue
   assert f.IX.iloc[i] and ii.i_buy.iloc[i] and ii.i_target.iloc[i]
   record=dict(group=k,symbol=sid,name=scope['meta'][sid]['name'],event_day=days[i],entry_day=days[entry],ix_episode=episode,e0_episode=int(ep0[i]),entry_signal_price=float(f.open.iloc[entry]));bad=False
   for policy in ['IX','I']:
    ex=exits[policy];p=np.searchsorted(ex,i,side='right');signal=int(ex[p]) if p<len(ex) else len(f);closed=signal+1<=last
    if closed:
     sell=signal+1
     if days[sell]!=nxt[days[signal]] or f.segment_id.iloc[sell]!=f.segment_id.iloc[i]:bad=True;break
     price=float(f.open.iloc[sell]);factor=(1-.0005)*(1-.0005)/((1+.0005)*(1+.0005))
    else:sell=last;price=float(f.close.iloc[last]);factor=1/((1+.0005)*(1+.0005))
    ret=price/record['entry_signal_price']*factor-1;path=np.r_[record['entry_signal_price'],f.close.iloc[entry:sell+1].to_numpy(float),price];dd=float(-(path/np.maximum.accumulate(path)-1).min())
    record.update({policy+'_exit_day':days[sell],policy+'_closed':closed,policy+'_return':ret,policy+'_held_observations':sell-entry+1,policy+'_path_drawdown':dd})
   if bad:skips['exit_source_gap']+=1;continue
   record['difference']=record['I_return']-record['IX_return'];record['both_closed']=record['I_closed'] and record['IX_closed'];rows.append(record)
 f=pd.DataFrame(rows);f.to_parquet(out/'events.parquet');f.to_csv(out/'events.csv',index=False);summary=[]
 for k,g in f.groupby('group',sort=False):
  c=g[g.both_closed];r=dict(group=k,anchors=sum(x==k for x in []),pairs=len(g),both_closed=len(c),stocks=g.symbol.nunique(),e0_clusters=g[['symbol','e0_episode']].drop_duplicates().shape[0],mean_difference=float(c.difference.mean()),median_difference=float(c.difference.median()),I_better_fraction=float(c.difference.gt(1e-10).mean()),I_worse_fraction=float(c.difference.lt(-1e-10).mean()),I_tail=int(c.I_return.ge(.3).sum()),IX_tail=int(c.IX_return.ge(.3).sum()),tail_created=int((c.I_return.ge(.3)&c.IX_return.lt(.3)).sum()),tail_lost=int((c.I_return.lt(.3)&c.IX_return.ge(.3)).sum()),IX_win_I_loss=int((c.IX_return.gt(0)&c.I_return.lt(0)).sum()))
  r.pop('anchors')
  for p in ['IX','I']:r.update({p+'_mean_return':float(c[p+'_return'].mean()),p+'_median_return':float(c[p+'_return'].median()),p+'_positive':float(c[p+'_return'].gt(0).mean()),p+'_mean_days':float(c[p+'_held_observations'].mean()),p+'_mean_path_dd':float(c[p+'_path_drawdown'].mean())})
  summary.append(r)
 pd.DataFrame(summary).to_csv(out/'summary.csv',index=False)
 # Equal-weight original E0 episodes reduce the repeated-long-hold weighting.
 f[f.both_closed].groupby(['group','symbol','e0_episode']).agg(difference=('difference','mean'),pairs=('symbol','size'),I_return=('I_return','mean'),IX_return=('IX_return','mean')).reset_index().to_csv(out/'e0-clusters.csv',index=False)
 write(out/'receipt.json',dict(recorded_at=now(),anchors=anchors,retained=len(f),skips=skips,normalization_only=True,overlapping=True,not_account_returns=True,rule_changed=False));print(pd.DataFrame(summary).to_string(index=False),flush=True)
if __name__=='__main__':main()
