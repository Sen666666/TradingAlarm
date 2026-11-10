"""Future price labels on all saved IX events; no orders or account simulation."""
from common import *
import pandas as pd

def environment():
 cal=pd.DatetimeIndex(sorted(set(x[:10] for x in read(OLD/'inputs-v2/market-rules.json')['calendars']['A'] if x[:10]<=END)))
 z=np.load(OLD/'h1/matrix.npz');dates=pd.DatetimeIndex(z['dates']);cols={str(s):j for j,s in enumerate(z['symbols'])};positions=dates.get_indexer(cal)
 assert (positions>=0).all();score=z['score'][positions];h=z['h'][positions]
 rec={x['series_id']:x for x in read(OLD/'prepared-v2/manifest.json')['series']};sectors=read(OLD/'inputs-v2/input-manifest.json')['sector_series'];up={};rank={}
 for sec,sid in sectors.items():
  f=pd.read_parquet(OLD/'prepared-v2'/rec[sid]['files']['states']['path'],columns=['ready','target']);q=f.reindex(cal)
  up[sec]=q.ready.fillna(False).astype(bool)&q.target.eq(1)
 ranked=pd.DataFrame({s:score[:,cols[s]] for s in sectors},index=cal).where(pd.DataFrame(up,index=cal))
 # Rank only observed/up/finite sector facts, exactly by score and stable ID.
 ranks=pd.DataFrame(index=cal,columns=sorted(sectors),dtype=float)
 for dt,row in ranked.iterrows():
  ids=sorted(row.dropna().index,key=lambda s:(-row[s],s))
  if ids:ranks.loc[dt,ids]=np.arange(1,len(ids)+1)
 return cal,score,h,cols,pd.DataFrame(up,index=cal),ranks

def main():
 out=HERE/'cohort-v1';out.mkdir(exist_ok=False);cal,score,h,cols,up,ranks=environment();meta=read(OLD/'inputs-v2/metadata.json');selected={x['security_id'] for x in read(OLD/'inputs-v2/selection.json')['lines'] if (x.get('company_cap_cny') or 0)>1e10};rows=[]
 assert len(selected)==1709
 for n,sid in enumerate(sorted(selected)):
  p=SRC/'signals'/f'{sid}.parquet';verify_source(p)
  f=pd.read_parquet(p,columns=['open','high','low','close','volume','IX','W23','W2H','C3','grade','previous_grade','ix_entered','e0_age_observations','z21']).reindex(cal)
  ok=f.IX.fillna(False).astype(bool)&(cal<=pd.Timestamp(END));ix=np.flatnonzero(ok.to_numpy());sec=meta[sid]['sector_id'];data=f.loc[ok,['grade','previous_grade','W23','W2H','C3','ix_entered','e0_age_observations','z21']].copy();data['symbol']=sid;data['year']=data.index.year;data['date']=data.index.strftime('%Y-%m-%d');data['IX']=True;data['rs_h1']=score[ix,cols[sid]];data['h']=h[ix,cols[sid]];data['sector_rs']=score[ix,cols[sec]];data['sector_up']=up.loc[data.index,sec].to_numpy();data['sector_rank_up']=ranks.loc[data.index,sec].to_numpy()
  opening=f.open.shift(-1);data['next_open']=opening.loc[ok];data['next_liquid_bar']=(f.volume.shift(-1).gt(0)&f.high.shift(-1).gt(f.low.shift(-1))).loc[ok]
  for horizon in [21,63]:data[f'ret{horizon}']=(f.close.shift(-horizon)/opening-1).loc[ok]
  rows.append(data.reset_index(drop=True))
  if (n+1)%300==0:print(dict(stocks=n+1,events=sum(len(x) for x in rows)),flush=True)
 df=pd.concat(rows,ignore_index=True);assert len(df)==481305;df.to_parquet(out/'all-event-labels.parquet',index=False)
 df['age_group']=np.select([df.e0_age_observations.le(21),df.e0_age_observations.le(63)],['0–21','22–63'],default='64+')
 df['rs_group']=pd.cut(df.rs_h1,[-.001,25,50,75,100.001],labels=['0–25','25–50','50–75','75–100']).astype(str)
 df['current_push']=np.where(df.z21.gt(0),'positive','nonpositive');df['kind']=np.where(df.ix_entered.eq(1),'new_or_restored_IX','continuing_IX')
 summaries=[]
 for scope,start in [('full','2015-01-01'),('recent','2023-01-01')]:
  a=df.loc[df.date.ge(start)]
  groupings=[('scheme',mode,a.loc[a[mode].fillna(False)]) for mode in MODES]
  # HotFresh is an evidence subset description, not an implemented strategy.
  groupings += [('evidence_subset','hot_fresh_all_events',a.loc[a.grade.ge(3)]),('evidence_subset','hot_fresh_continuations',a.loc[a.grade.ge(3)&a.ix_entered.eq(0)])]
  for field in ['grade','previous_grade','age_group','rs_group','sector_up','kind','current_push']:
   groupings += [(field,str(key),g) for key,g in a.groupby(field,observed=True,dropna=False)]
  for field,key,g in groupings:
   for horizon in [21,63]:
    col=f'ret{horizon}';vals=g[col].dropna();means=g.dropna(subset=[col]).groupby(['symbol','year'])[col].mean()
    summaries.append(dict(scope=scope,group_field=field,group=key,horizon=horizon,events=len(g),complete_labels=len(vals),missing_labels=int(g[col].isna().sum()),mean=vals.mean(),median=vals.median(),p10=vals.quantile(.1),p90=vals.quantile(.9),positive_fraction=vals.gt(0).mean(),stock_year_equal_mean=means.mean(),stock_year_groups=len(means)))
 pd.DataFrame(summaries).to_csv(out/'summary.csv',index=False);write(out/'summary.json',summaries)
 write(out/'receipt.json',dict(recorded_at=now(),passed=True,qualified_sources=len(selected),all_IX_events=len(df),recent_events=int(df.date.ge('2023-01-01').sum()),new_accounts=0,interpretation='overlapping future price labels, not tradable returns or independent samples',endpoint_missing_not_filled=True))
 print(pd.DataFrame(summaries).query("scope=='recent' and group_field in ['scheme','evidence_subset']").to_string(index=False),flush=True)
if __name__=='__main__':main()
