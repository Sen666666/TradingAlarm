"""Descriptive structural continuation only: no cash, no executable-return claims."""
from study import *
snap=Path(read(O/'input.json')['snapshot']);ev=pd.read_csv(O/'additional-events.csv');out=[]
cache={}
for e in ev.itertuples():
 if e.symbol not in cache:cache[e.symbol]=pd.read_parquet(snap/'facts'/f'{e.symbol}.parquet')
 g=cache[e.symbol];t=pd.Timestamp(e.date);stop=float(e.floor);f0=float(g.loc[t,'e0_floor']);hand=None;exitday=None;reason='unresolved_at_end';last=None
 for day,r in g.loc[g.index>t].iterrows():
  if bool(r.e0_target) and np.isfinite(r.e0_floor):stop=max(stop,float(r.e0_floor))
  last=day
  if not bool(r.e0_target):exitday=day;reason='E0_structure_failed';break
  if r.close<=stop:exitday=day;reason='local_close_failed';break
  if hand is None and r.e0_floor>f0 and r.e0_floor>=e.floor:hand=day
 out.append(dict(symbol=e.symbol,version=e.version,event=e.date,local_floor=e.floor,handoff=str(hand.date()) if hand is not None else '',end=str(exitday.date()) if exitday is not None else '',reason=reason,observations=int(((g.index>t)&(g.index<=last)).sum()) if last is not None else 0))
pd.DataFrame(out).to_csv(O/'structural-trajectories.csv',index=False)
print(pd.DataFrame(out).groupby(['version','reason']).size().to_string());print('descriptive_handoffs',sum(bool(r['handoff']) for r in out))
