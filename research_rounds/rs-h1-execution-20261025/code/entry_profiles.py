"""Known-at-entry structure age and protection distance, descriptive only."""
import numpy as np,pandas as pd
from build_inputs import HERE,read,write,now
OLD=HERE.parent/'a-share-selection-e0-20261024'
def main():
 out=HERE/'entry-profiles';out.mkdir(exist_ok=False)
 pm={x['series_id']:x for x in read(HERE/'prepared-v2/manifest.json')['series']};cache={};profiles=[]
 ranks={(x['account'],x['symbol'],x['first_fill']):x for x in read(HERE/'audit/filled-order-ranks.json')}
 def get(sid):
  if sid not in cache:
   st=pd.read_parquet(HERE/'prepared-v2'/pm[sid]['files']['states']['path'],columns=['ready','target','floor','entered']);sg=pd.read_parquet(HERE/'prepared-v2'/pm[sid]['files']['signal']['path'],columns=['adjustment_factor','raw_close']);cache[sid]=(st,sg,np.flatnonzero(st.entered.eq(1)))
  return cache[sid]
 for c in read(HERE/'analysis-v2/campaigns.json'):
  sid=c['symbol'];p=ranks[c['account'],sid,c['entry_at'][:10]];day=pd.Timestamp(p['decision_date']);st,sg,entered=get(sid);i=st.index.searchsorted(day,side='right')-1;assert st.index[i]==day and st.iloc[i].target
  pos=sg.index.searchsorted(day,side='right')-1;q=float(sg.raw_close.iloc[pos]);floor=float(st.floor.iloc[i])/float(sg.adjustment_factor.iloc[pos]);entry=entered[entered<=i]
  profiles.append(dict(account=c['account'],symbol=sid,name=c['name'],industry=c['industry'],decision_date=p['decision_date'],entry_at=c['entry_at'],closed=c['closed'],net_pnl=float(c['net_pnl']),net_return=c['net_return'],h=p['h'],rs_h1=p['score'],close_to_support_fraction=(q-floor)/q,e0_age_observations=int(i-entry[-1]) if len(entry) else None))
 write(out/'profiles.json',profiles);pd.DataFrame(profiles).to_csv(out/'profiles.csv',index=False,encoding='utf-8-sig');summary=[]
 old=read(OLD/'entry-quality-v2/profiles.json')
 for aid in ['T0_base','T1_base','S0_base','S1_base']:
  a=[x for x in old if x['account']==aid];b=[x for x in profiles if x['account']==aid]
  def quant(rows,key,q):
   v=[x[key] for x in rows if x[key] is not None];return float(np.quantile(v,q)) if v else None
  summary.append(dict(account=aid,old_support_distance_median=quant(a,'close_to_support_fraction',.5),new_support_distance_median=quant(b,'close_to_support_fraction',.5),old_support_distance_p90=quant(a,'close_to_support_fraction',.9),new_support_distance_p90=quant(b,'close_to_support_fraction',.9),old_e0_age_median=quant(a,'observations_since_latest_E0_entry',.5),new_e0_age_median=quant(b,'e0_age_observations',.5),old_e0_age_p90=quant(a,'observations_since_latest_E0_entry',.9),new_e0_age_p90=quant(b,'e0_age_observations',.9)))
 write(out/'summary.json',dict(recorded_at=now(),rows=summary,no_new_accounts=True,notes=['Protection distance is the original E0 support known at reservation, not a guaranteed stop loss. No new risk filter or tighter exit is applied.','Trend age measures bars since the latest original E0 entry event, not age of the one-session cash order. Waiting candidates are evaluated afresh even when the underlying E0 structure is older.']))
 print(summary,flush=True)
if __name__=='__main__':main()
