from drug_common import *
from TradingAlarm.desk.refresh import compute_recovery

def components():
 z=dict(np.load(SNAP/'h1.npz'));dates=pd.DatetimeIndex(z['dates']);cols={str(s):j for j,s in enumerate(z['symbols'])};records={r['series_id']:r for r in read(SNAP/'manifest.json')['series']};meta=read(C.OLD/'inputs-v2/metadata.json');ids=sorted(s for s,r in records.items() if r['kind']=='stock');returns={};mom={};hashes={}
 for i,sid in enumerate(ids):
  rec=records[sid];path=Path(rec['raw']['path']);assert sha(path)==rec['raw']['sha256'];raw=C.read_raw(path,rec);j=cols[sid];index=dates[np.isfinite(z['close'][:,j])];f=raw.reindex(index);f=f[(f.observed_bar.fillna(False)) & f.price_eligible.fillna(False) & ~f.synthetic_event_bar.fillna(True)]
  f=f.assign(close=pd.Series(z['close'][:,j],index=dates).reindex(f.index),segment_id=pd.Series(z['segment'][:,j],index=dates).reindex(f.index));rs=[];ms=[]
  for _,g in f.groupby('segment_id',sort=False):
   r=np.log(g.close).diff();q=g.amount/g.amount.shift().rolling(21,min_periods=21).median();u=r*np.minimum(1,np.sqrt(q));m=u.ewm(span=21,adjust=False).mean();ready=np.arange(len(g))>=64;rs.append(r.where(ready));m.iloc[:64]=np.nan;ms.append(m)
  returns[sid]=pd.concat(rs).sort_index();mom[sid]=pd.concat(ms).sort_index();hashes[sid]=rec['raw']['sha256']
  if (i+1)%200==0:print('market components',i+1,flush=True)
 r=pd.DataFrame(returns);m=pd.DataFrame(mom);r.to_parquet(O/'market-returns.parquet');m.to_parquet(O/'market-momentum.parquet');save(O/'market-source-hashes.json',hashes)
 return r,m,meta

def calculate(r,m,roster):
 sr=[];sb=[]
 for sec,g in roster.groupby('sector_id'):
  ids=g.symbol.tolist();sr.append(r[ids].mean(axis=1));v=m[ids];n=v.notna().sum(axis=1);sb.append((v.gt(0).sum(axis=1)/n).where(n>=5))
 rr=pd.concat(sr,axis=1).mean(axis=1);price=np.exp(rr.fillna(0)).cumprod();b=pd.concat(sb,axis=1);breadth=b.mean(axis=1).where(b.notna().sum(axis=1)>=8);out=pd.DataFrame(dict(market=price,prior_high63=price.shift().rolling(63,min_periods=63).max(),breadth=breadth));out['breakout']=(out.market>out.prior_high63)&(out.market.diff()>0)&(out.breadth>.6);out['fast_on']=out.breadth.gt(.6)
 return out

def main():
 r,m,meta=components();roster=pd.DataFrame([dict(symbol=s,sector_id=meta[s]['sector_id']) for s in r.columns]);broad=calculate(r,m,roster);broad.to_csv(PREP/'recovery.csv')
 # This adapter must reconstruct the old tech environment on the existing pool.
 tech=pd.read_csv(C.DESIGN/'proposed-pool.csv');t=calculate(r,m,tech);old=pd.read_csv(SNAP/'recovery.csv',index_col=0,parse_dates=True);ix=old.loc['2024':].index.intersection(t.index)
 np.testing.assert_allclose(t.loc[ix,'breadth'],old.loc[ix,'breadth'],rtol=0,atol=1e-12,equal_nan=True);np.testing.assert_array_equal(t.loc[ix,'breakout'],old.loc[ix,'breakout'])
 ratio=t.loc[ix,'market']/old.loc[ix,'market'];np.testing.assert_allclose(ratio,ratio.iloc[0],rtol=1e-12,atol=1e-12)
 for cut in ['2024-12-31','2026-06-30']:
  q=calculate(r.loc[:cut],m.loc[:cut],roster);pd.testing.assert_frame_equal(q,broad.loc[:cut],check_exact=True)
 save(O/'market-validation.json',{'passed':True,'reference_stocks':len(roster),'reference_sectors':roster.sector_id.nunique(),'tech_reconstruction_rows':len(ix),'physical_prefixes':2,'interpretation':'Same frozen environment formula, broad 1709-stock/90-industry reference; candidate pool remains 48. Coverage remains >=5 per sector and >=8 available sectors.','normalization_origin':str(r.index.min().date()),'h1_matrix_sha256':sha(SNAP/'h1.npz')})
if __name__=='__main__':main()
