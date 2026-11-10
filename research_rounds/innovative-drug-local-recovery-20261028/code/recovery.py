from drug_common import *
MIN_SECTORS=3;MIN_STOCKS=5

def calculate(r,m,roster,min_sectors=MIN_SECTORS):
 sr=[];sb=[];coverage=[]
 for sector,g in roster.groupby('sector_id'):
  ids=g.symbol.tolist();sr.append(r[ids].mean(axis=1));v=m[ids];n=v.notna().sum(axis=1);coverage.append(n.rename(sector));sb.append((v.gt(0).sum(axis=1)/n).where(n>=MIN_STOCKS))
 rr=pd.concat(sr,axis=1).mean(axis=1);price=np.exp(rr.fillna(0)).cumprod();b=pd.concat(sb,axis=1);valid=b.notna().sum(axis=1);breadth=b.mean(axis=1).where(valid>=min_sectors)
 out=pd.DataFrame(dict(market=price,prior_high63=price.shift().rolling(63,min_periods=63).max(),breadth=breadth));out['breakout']=(out.market>out.prior_high63)&(out.market.diff()>0)&(out.breadth>.6);out['fast_on']=out.breadth.gt(.6)
 counts=pd.concat(coverage,axis=1);counts['valid_sectors']=valid
 return out,counts

def main():
 roster=pd.read_csv(PARENT/'pool.csv');r=pd.read_parquet(PARENT/'market-returns.parquet');m=pd.read_parquet(PARENT/'market-momentum.parquet');ids=roster.symbol.tolist();r=r[ids];m=m[ids]
 out,cov=calculate(r,m,roster);out.to_csv(O/'recovery.csv');cov.to_csv(O/'coverage.csv')
 for cut in ['2024-12-31','2026-06-30']:
  q,_=calculate(r.loc[:cut],m.loc[:cut],roster);pd.testing.assert_frame_equal(q,out.loc[:cut],check_exact=True)
 # With the old eight-sector requirement the same 4-industry pool is unavailable.
 impossible,_=calculate(r,m,roster,8);assert not impossible.breadth.notna().any() and not impossible.breakout.any()
 # The generic old broad calculation must still be identical under threshold=8.
 meta=read(C.OLD/'inputs-v2/metadata.json');all_r=pd.read_parquet(PARENT/'market-returns.parquet');all_m=pd.read_parquet(PARENT/'market-momentum.parquet');broad_roster=pd.DataFrame([dict(symbol=s,sector_id=meta[s]['sector_id']) for s in all_r.columns]);broad,_=calculate(all_r,all_m,broad_roster,8);old=pd.read_csv(PREP/'recovery.csv',index_col=0,parse_dates=True);pd.testing.assert_frame_equal(broad,old,check_exact=False,rtol=1e-14,atol=1e-14,check_freq=False)
 changes=pd.DataFrame({'local_breakout':out.breakout,'broad_breakout':old.breakout});changes['different']=changes.local_breakout.ne(changes.broad_breakout);changes.loc['2024':].to_csv(O/'recovery-date-comparison.csv')
 save(O/'market-validation.json',{'passed':True,'reference_stocks':48,'reference_sectors':4,'min_valid_stocks_per_sector':MIN_STOCKS,'min_valid_sectors':MIN_SECTORS,'coverage_basis':'ceil((8/11)*4)=3, fixed before economic results; original tech coverage ratio adapted to actual four industries','physical_prefixes':2,'broad_reconstruction_exact_tolerance':1e-14,'different_breakout_days_2024':int(changes.loc['2024':,'different'].sum()),'local_breakout_days_2024':int(out.loc['2024':,'breakout'].sum()),'broad_breakout_days_2024':int(old.loc['2024':,'breakout'].sum()),'valid_sector_counts_2024':{str(k):int(v) for k,v in cov.loc['2024':,'valid_sectors'].value_counts().items()},'source_sha256':{str(PARENT/'market-returns.parquet'):sha(PARENT/'market-returns.parquet'),str(PARENT/'market-momentum.parquet'):sha(PARENT/'market-momentum.parquet'),str(PARENT/'pool.csv'):sha(PARENT/'pool.csv')}})
if __name__=='__main__':main()
