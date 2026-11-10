"""Descriptive diagnostics only. Never feed future prices into account decisions."""
from study import *
from audit import rows
from collections import Counter,defaultdict

def main():
 snap=Path(read(O/'input.json')['snapshot']);facts={};prices={};episodes={}
 for path in sorted((O/'signals').glob('*.parquet')):
  sid=path.stem;g=pd.read_parquet(snap/'facts'/path.name);facts[sid]=g;episodes[sid]=(g.i_target.ne(g.i_target.shift())|g.segment_id.ne(g.segment_id.shift())).cumsum();prices[sid]=pd.read_parquet(snap/'signals'/path.name).close
 # Actual pairs followed by fixed future observation horizons.
 pairs=pd.read_csv(O/'pairs.csv');forward=[]
 for r in pairs.itertuples():
  t=pd.Timestamp(str(r.signal_at)[:10]);a=prices[r.candidate];b=prices[r.victim];common=a.index.intersection(b.index);j=common.searchsorted(t)
  for horizon in [21,63]:
   item=dict(cohort=r.cohort,account=r.account,pair_id=r.id,candidate=r.candidate,victim=r.victim,signal=str(t.date()),actual_buy=r.actual_buy,horizon=horizon)
   if j>=len(common) or common[j]!=t or j+horizon>=len(common):item.update(status='insufficient_future')
   else:
    end=common[j+horizon];nr=float(a.loc[end]/a.loc[t]-1);vr=float(b.loc[end]/b.loc[t]-1);quad=('new_up' if nr>0 else 'new_not_up')+'_'+('old_up' if vr>0 else 'old_not_up');item.update(status='observed',end=str(end.date()),new_price_return=nr,old_price_return=vr,relative_price_return=nr-vr,quadrant=quad,old_large_move=vr>=.3)
   forward.append(item)
 pd.DataFrame(forward).to_csv(O/'pair-forward-prices.csv',index=False)
 # Only base paths: first denied candidate within each continuous original I
 # structure, resolved by later holding or structure termination; nonfilled stays.
 waiting=[];funnel=[]
 for cohort in STARTS:
  ds=rows(O/cohort/'accounts-v2/daily.jsonl.gz');decs=rows(O/cohort/'accounts-v2/decisions.jsonl.gz')
  for aid in [m+'__S0_base' for m in MODES]:
   dd=[d for d in ds if d['account']==aid];dc={d['at'][:10]:d for d in decs if d['account']==aid};active={};seen=set();n=len(dd)
   for i,d in enumerate(dd):
    day=d['at'][:10];T=pd.Timestamp(day);decision=dc[day];held=set(d['positions'])
    for key,z in list(active.items()):
     sid,ep=key;g=facts[sid];j=g.index.searchsorted(T,side='right')-1;valid=j>=0 and bool(g.iloc[j].i_target) and int(episodes[sid].iloc[j])==ep
     if sid in held:
      waiting.append(dict(**z,status='later_held',resolved=day,wait_observations=i-z['start_index']));del active[key]
     elif not valid:
      waiting.append(dict(**z,status='structure_ended_unheld',resolved=day,wait_observations=i-z['start_index']));del active[key]
    for sid in decision['eligible']:
     if sid in held or sid in decision['accepted'] or sid in d['pending_buys']:continue
     ep=int(episodes[sid].loc[T]);key=(sid,ep)
     if key in seen:continue
     seen.add(key);active[key]=dict(cohort=cohort,account=aid,symbol=sid,episode=ep,first_denied=day,start_index=i)
   for z in active.values():waiting.append(dict(**z,status='still_unheld_at_end',resolved=dd[-1]['at'][:10],wait_observations=n-1-z['start_index']))
 pd.DataFrame(waiting).to_csv(O/'waiting-opportunities.csv',index=False)
 # Summaries explicitly keep unknown forward horizons and unheld cases.
 w=pd.DataFrame(waiting);w['strategy']=w.account.str[:3];w['seed']=w.account.str[3].astype(int)
 out=[]
 for keys,g in w.groupby(['cohort','strategy','seed']):
  held=g[g.status=='later_held'];out.append(dict(cohort=keys[0],strategy=keys[1],seed=keys[2],denied_structure_episodes=len(g),later_held=len(held),later_held_ratio=len(held)/len(g),conditional_median_wait=held.wait_observations.median(),ended_unheld=int((g.status=='structure_ended_unheld').sum()),unresolved=int((g.status=='still_unheld_at_end').sum())))
 pd.DataFrame(out).to_csv(O/'waiting-summary.csv',index=False)
 print('diagnostics complete',len(pairs),'pairs',len(waiting),'waiting episodes')
if __name__=='__main__':main()
