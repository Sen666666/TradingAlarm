from run import *
if __name__=='__main__':
 selected=pd.read_csv(OUT/'selected.csv');checks=[]
 for r in selected.itertuples():
  path=SRC/'signals'/f'{r.symbol}.parquet';f=eligible_prices(pd.read_parquet(path).loc[:r.date])[['open','high','low','close','volume','segment_id']].copy();f['valid_price_observation']=True;f['valid_strength_observation']=np.isfinite(f.volume)&f.volume.gt(0)
  z=run_b5(f);ev=z['evidence'].copy();ev['decline_candidate']=False;b,_=e0_policy(ev);saved=pd.read_parquet(OUT/'states'/path.name).loc[:r.date]
  for actual,col in [(z['state'].target,'a'),(b.target,'b'),(z['state'].floor,'floor_a'),(b.floor,'floor_b')]:np.testing.assert_allclose(actual.astype(float),saved[col].astype(float),rtol=0,atol=0,equal_nan=True)
  checks.append(dict(symbol=r.symbol,end=r.date,rows=len(f),passed=True))
 (OUT/'prefix.json').write_text(json.dumps(checks,indent=2)+'\n');print(checks)
