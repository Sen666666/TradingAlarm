from prepare import *
from model_nr1 import run_e0_nr1
if __name__=='__main__':
 receipts=[]
 for r in pd.read_csv(Q/'selected.csv').drop_duplicates(['symbol','date']).itertuples():
  sid=r.symbol;f=eligible_prices(pd.read_parquet(P/'signals'/f'{sid}.parquet').loc[:r.date])[['open','high','low','close','volume','segment_id']].copy();f['valid_price_observation']=True;f['valid_strength_observation']=np.isfinite(f.volume)&f.volume.gt(0)
  z=run_e0_nr1(f);saved=pd.read_parquet(O/'prepared/facts'/f'{sid}.parquet').loc[:r.date]
  for col in ['target','floor']:np.testing.assert_allclose(z['state'][col].astype(float),saved['e0_'+col].astype(float),rtol=0,atol=0,equal_nan=True)
  assert z['ledger'].empty;assert not z['state'].independent_entry.any();assert z['evidence'].decline_candidate.any()
  receipts.append(dict(symbol=sid,end=r.date,rows=len(f),evidence_retained=True,independent_entries=0,off_identity=True))
 (O/'nr1-contract.json').write_text(json.dumps(receipts,indent=2)+'\n');print(receipts)
