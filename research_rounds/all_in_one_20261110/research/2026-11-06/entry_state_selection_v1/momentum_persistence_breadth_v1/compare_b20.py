from pathlib import Path
import pandas as pd,numpy as np,json
O=Path(__file__).resolve().parent
hp=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
h=np.load(hp,allow_pickle=False);dates=pd.DatetimeIndex(h['dates']);symbols=list(h['symbols']);C=pd.DataFrame(h['close'],index=dates,columns=symbols);S=pd.DataFrame(h['segment'],index=dates,columns=symbols);C=C.where(np.isfinite(C)&C.gt(0));ma=C.rolling(20,min_periods=20).mean().where(S.eq(S.shift(19)));K=C.notna()&ma.notna();R=C.gt(ma)&K
roster=pd.read_csv(O/'FIXED_ROSTER.csv');out=[]
for sec,g in roster.groupby('sector_id'):
 k=K[g.symbol];r=R[g.symbol];pair=k&k.shift(5,fill_value=False);df=pd.DataFrame(dict(sector=sec,B20_K=k.sum(axis=1),B20_n=r.sum(axis=1),B20=r.sum(axis=1)/k.sum(axis=1).replace(0,np.nan),B20_common5_K=pair.sum(axis=1),B20_delta5=((r.astype(int)-r.shift(5,fill_value=False).astype(int))*pair).sum(axis=1)/pair.sum(axis=1).replace(0,np.nan)));df.index.name='day';out.append(df.reset_index())
b=pd.concat(out);z=pd.read_parquet(O/'SECTOR_DAILY.parquet');b=b.merge(z,on=['day','sector'],how='inner');b.to_parquet(O/'OLD_B20_COMPARISON.parquet',index=False);b[b.day.dt.strftime('%Y-%m-%d').isin(json.load(open(O/'PROTOCOL.json'))['fixed_cases'])].to_csv(O/'FIXED_DATE_B20_COMPARISON.csv',index=False)
print(b[(b.sector=='URFI881121')&b.day.isin(pd.to_datetime(['2024-09-24','2024-09-26','2026-01-15','2026-04-08','2026-04-17','2026-06-11','2026-06-16']))][['day','B20_K','B20_n','B20','B20_delta5','K','n','right_known','delta3','sector_stage']].to_string(index=False))
