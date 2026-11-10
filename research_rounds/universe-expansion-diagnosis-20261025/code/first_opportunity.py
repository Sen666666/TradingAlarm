"""Causal first fully eligible event per IX episode; full-universe diagnostic."""
from common import *
import gzip,collections

def main():
 out=HERE/'first-opportunity';out.mkdir(exist_ok=False);events=collections.defaultdict(list)
 with gzip.open(ABCD/'technical/A-controls/decisions.jsonl.gz','rt') as f:
  for line in f:
   r=json.loads(line)
   if r['account']!='A__S0_base':continue
   for e in r['event_eligibility']:
    if e['q'] is True:events[e['symbol']].append(r['at'][:10])
 modes={'FIRST':collections.defaultdict(list)};rows=[];ordinary=[]
 for sid,days in events.items():
  f=pd.read_parquet(IX/'signals'/f'{sid}.parquet',columns=['open','close','ix_target','ix_floor','IX']);target=f.ix_target.to_numpy(bool);ep=np.cumsum(target&~np.r_[False,target[:-1]]);idx={str(d.date()):i for i,d in enumerate(f.index)};first={}
  for day in days:
   i=idx.get(day)
   if i is not None and target[i]:first.setdefault(ep[i],i)
  selected=set(first.values());modes['FIRST'][sid]=[str(f.index[i].date()) for i in sorted(selected)];ends={}
  for e in first:
   positions=np.flatnonzero((ep==e)&target);last=positions[-1];k=last+2;ends[e]=k
  cutoff=f.index.searchsorted(END,side='right')-1
  for day in days:
   i=idx.get(day)
   if i is None or not START<=day<=END or i+1>cutoff:continue
   k=ends.get(ep[i],len(f));terminal=k>cutoff;k=min(k,cutoff);exitpx=float(f.close.iloc[k]) if terminal else float(f.open.iloc[k]);entry=float(f.open.iloc[i+1]);ret=exitpx/entry*(1-.0005)/(1+.0005)*(1-.0005)/(1+.0005)-1
   ordinary.append(ret)
   if i in selected:rows.append(dict(symbol=sid,event_day=day,entry_day=str(f.index[i+1].date()),exit_day=str(f.index[k].date()),net_return=ret,terminal=terminal,old_gap_guard_would_cancel=bool(entry<=f.ix_floor.iloc[i])))
 a=pd.DataFrame(rows);a.to_csv(out/'all-first-events.csv',index=False);write(out/'events.json',modes['FIRST']);write(out/'summary.json',dict(recorded_at=now(),mechanism='first full original S0 eligibility in each IX active episode; resets only on next IX episode; no grade crossing threshold',first_events=len(a),mean_first_return=float(a.net_return.mean()),median_first_return=float(a.net_return.median()),positive_first_fraction=float(a.net_return.gt(0).mean()),all_daily_eligible_events=len(ordinary),mean_daily_event_return=float(np.mean(ordinary)),terminal_first=int(a.terminal.sum()),source_new_daily_checks_preserved=True,forward_statistics_are_overlapping_unit_diagnostics=True));print(read(out/'summary.json'),flush=True)
if __name__=='__main__':main()
