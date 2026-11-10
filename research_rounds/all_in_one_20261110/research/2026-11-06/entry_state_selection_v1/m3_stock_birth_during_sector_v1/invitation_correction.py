from pathlib import Path
import pandas as pd
R=Path.cwd();O=R/'m3_stock_birth_during_sector_v1'
e=pd.read_csv(O/'SEALED_ALL_BIRTH_EVENTS.csv',dtype={'window':str},parse_dates=['day','sector_run_start'])
old=pd.read_csv(R/'breadth_trade_contract_v1/ALL_CANDIDATES.csv',dtype={'window':str},parse_dates=['day'])
old=old[old.arm.eq('M3')]
keys=set(map(tuple,old[['window','day','sid']].to_numpy()))
b=e[e.event_type.eq('B_STOCK_BIRTH_DURING_SECTOR')].copy()
b['invited_at_original_sector_start_any_type']=[(w,d,s) in keys for w,d,s in zip(b.window,b.sector_run_start,b.sid)]
print('CORRECTED',b.groupby(['window','invited_at_original_sector_start_any_type']).agg(events=('sid','size'),I_and_PVR_known=('I_and_PVR_known','sum')).to_string())
pool=e[e.I_and_PVR_known&e.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])].sort_values(['PVR_score','sid'],ascending=[False,True]).copy()
pool['descriptive_birth_PVR_rank']=pool.groupby(['window','day','sector']).cumcount()+1
p=pd.read_csv(O/'PRICE_ANATOMY.csv',dtype={'window':str},parse_dates=['day'])
p=p.merge(pool[['event_id','descriptive_birth_PVR_rank']],on='event_id',how='left',validate='one_to_one')
examples=pd.read_csv(O/'TRANSPARENT_POSITIVE_NEGATIVE_EXAMPLES.csv').event_id
names=['300085.SZ','002583.SZ','603061.SH','300623.SZ','688498.SH','300666.SZ','301611.SZ']
show=p[p.event_id.isin(examples)|(p.sid.isin(names)&p.event_type.eq('B_STOCK_BIRTH_DURING_SECTOR'))]
print(show[['window','day','sid','name','PVR_score','descriptive_birth_PVR_rank','ret20','path20_status']].to_string(index=False))
b.to_csv(O/'ORIGINAL_INVITATION_CORRECTION.csv',index=False)
p.to_csv(O/'DESCRIPTIVE_PVR_BIRTH_RANK.csv',index=False)
