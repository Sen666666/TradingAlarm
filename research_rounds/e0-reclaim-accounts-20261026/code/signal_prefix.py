from prepare import *
from grade import classify
if __name__=='__main__':
 sel=pd.read_csv(Q/'selected.csv').drop_duplicates(['symbol','date']);checks=[]
 for row in sel.itertuples():
  for end in [row.date,'2024-12-31']:
   sid=row.symbol;f=eligible_prices(pd.read_parquet(P/'signals'/f'{sid}.parquet').loc[:end])[['open','high','low','close','volume','segment_id']].copy();f['valid_price_observation']=True;f['valid_strength_observation']=np.isfinite(f.volume)&f.volume.gt(0)
   z=run_b5(f);e=z['evidence'];g,_=classify(e);e['decline_candidate']=False;b,_=e0_policy(e);ip=project(e,b,g,'G1_I');saved=pd.read_parquet(O/'prepared/facts'/f'{sid}.parquet').loc[:end]
   for x,y in [(b.target,'e0_target'),(b.floor,'e0_floor'),(ip.target,'i_target'),(ip.floor,'i_floor'),(ip.buy_event,'i_buy')]:np.testing.assert_allclose(x.astype(float),saved[y].astype(float),rtol=0,atol=0,equal_nan=True)
   checks.append(dict(symbol=sid,end=end,rows=len(f),passed=True))
 (O/'signal-prefix.json').write_text(json.dumps(checks,indent=2)+'\n');print(checks)
