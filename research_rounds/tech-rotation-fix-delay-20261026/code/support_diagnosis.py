from study_common import *
import collections
out=[];cache={}
for folder,aid in [(BASE/'accounts-v2','I__S0_base'),(BASE/'accounts-v2','I__S0_delay1'),(HERE/'accounts','IL2__S0_delay1')]:
 obj=read(folder/(aid+'.json'));contracts={r['order_id']:r for r in obj['audit_log'] if r['kind']=='entry_contract'}
 for r in obj['audit_log']:
  if r['kind']!='fill' or r['receipt']['side']!='buy':continue
  f=r['receipt'];sid=f['security_id'];z=contracts[r['order_id']]
  if sid not in cache:cache[sid]=pd.read_parquet(PREP/'facts'/f'{sid}.parquet')
  g=cache[sid];ix=g.index.searchsorted(pd.Timestamp(f['at'][:10]),side='right')-1;floor=float(z['floor_signal'])/float(g.iloc[ix].factor);price=float(r['price']);out.append(dict(account=aid,symbol=sid,order_id=r['order_id'],origin=z['decision_at'],at=f['at'],price=price,floor=floor,initial_distance=1-floor/price))
f=pd.DataFrame(out).drop_duplicates(['account','order_id']);f.to_csv(HERE/'analysis/entry-support-distances.csv',index=False);stats=[]
for aid,z in f.groupby('account'):stats.append(dict(account=aid,count=len(z),median=float(z.initial_distance.median()),p90=float(z.initial_distance.quantile(.9)),max=float(z.initial_distance.max()),above20=int(z.initial_distance.gt(.2).sum())))
write(HERE/'analysis/entry-support-distance-summary.json',stats);print(stats);print(f[f.symbol.isin(['688048.SH','688498.SH'])].to_string(index=False))
