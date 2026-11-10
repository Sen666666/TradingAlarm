from budget_common import *

def main():
 z=np.load(OLD/'h1/matrix.npz');dates=pd.DatetimeIndex(z['dates']);i=dates.get_loc('2020-12-31');ids=[str(s) for s in z['symbols']];meta=read(OLD/'inputs-v2/metadata.json');chosen=[];allrows=[]
 for sector in SECTORS:
  candidates=[]
  for j,sid in enumerate(ids):
   if sid not in meta or meta[sid]['sector_id']!=sector or not math.isfinite(z['score'][i,j]):continue
   f=pd.read_parquet(IX/'signals'/f'{sid}.parquet',columns=['e0_ready','strength_ready']);pos=f.index.searchsorted('2020-12-31',side='right')-1
   if pos<0 or not bool(f.e0_ready.iloc[pos]):continue
   candidates.append(dict(symbol=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],sector=sector,score=float(z['score'][i,j]),strength_ready_at_selection=bool(f.strength_ready.iloc[pos])))
  candidates.sort(key=lambda x:(-round(x['score'],12),x['symbol']));assert len(candidates)>=2;chosen.extend(candidates[:2]);allrows.extend(candidates)
 write(HERE/'scope.json',dict(recorded_at=now(),selection_close='2020-12-31',chosen=chosen,candidates=allrows,current_snapshot_bias=True,rank_source_sha256=sha(OLD/'h1/matrix.npz'),selection_uses_future_returns=False));pd.DataFrame(chosen).to_csv(HERE/'scope.csv',index=False)
 print(pd.DataFrame(chosen).to_string(index=False),flush=True)
if __name__=='__main__':main()
