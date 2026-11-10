"""Fixed v5 windows: literal old aggregates and CP cache; no signals/accounts."""
from pathlib import Path
import hashlib,json,time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent
ROOT=O.parents[1]
BASE=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
CSI=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USHI1B0300.csv')
SOURCES={}
def bind(p,expected=None):
 p=Path(p).resolve();h=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected:assert h==expected,(str(p),h,expected)
 SOURCES[str(p)]=h;return p
def save_json(name,v):
 (O/name).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 O.mkdir(parents=True,exist_ok=True);bind(__file__);bind(O.parent/'EXTRACTION_CONTRACT.txt')
 market=pd.read_csv(bind(CSI),parse_dates=['date']).set_index('date');cal=pd.DatetimeIndex(market.index).as_unit('ns')
 old=pd.read_parquet(bind(ROOT/'industry_selection/channels_v2/INDUSTRY_OPPORTUNITIES_DAILY.parquet'))
 warm=pd.read_parquet(bind(ROOT/'separated_momentum_v4/ranking/WARMUP_BREADTH_2021.parquet'))
 full=pd.concat([warm,old],ignore_index=True);full['date']=pd.to_datetime(full.date);full=full.sort_values(['sector_id_static','date'])
 assert not full.duplicated(['date','sector_id_static']).any()
 group=full.groupby('sector_id_static',sort=False)
 full['B_own_lag5_raw']=group.B_now.shift(5);full['B_own_lag10_raw']=group.B_now.shift(10)
 full['own_change5_raw']=full.B_now-full.B_own_lag5_raw
 full['a_own_raw']=full.B_now-2*full.B_own_lag5_raw+full.B_own_lag10_raw
 full['dB5_paired_lag5_raw']=group.dB5_paired.shift(5)
 full['a_pair_raw']=full.dB5_paired-full.dB5_paired_lag5_raw
 full['share5_over_share20_minus1_raw']=full.share5/full.share20-1
 full['log_share5_over_share20_raw']=np.log(full.share5/full.share20).where(full.share5.gt(0)&full.share20.gt(0))
 g=full.groupby('date');pool=g[['N_above20_t','N_U_t']].sum();pool.columns=['pool_N_above20','pool_N_U']
 pool['pool_sector_rows']=g.size();pool['pool_sectors_B_known']=g.B_now.count()
 pool['Bmarket_subpool']=pool.pool_N_above20/pool.pool_N_U
 pool['Bmarket_lag5']=pool.Bmarket_subpool.shift(5);pool['Bmarket_lag10']=pool.Bmarket_subpool.shift(10)
 pool['Bmarket_change5']=pool.Bmarket_subpool-pool.Bmarket_lag5
 pool['Bmarket_a_own']=pool.Bmarket_subpool-2*pool.Bmarket_lag5+pool.Bmarket_lag10
 assert pool.pool_sector_rows.eq(90).all()
 full=full.merge(pool,left_on='date',right_index=True,how='left',validate='many_to_one')
 full=full.set_index(['date','sector_id_static'])
 cases=[('main_semis_924','MAIN','2024-09-24','URFI881121'),('main_software_924','MAIN','2024-09-24','URFI881272'),('main_comms_924','MAIN','2024-09-24','URFI881129'),('main_semis_2026jan5','MAIN','2026-01-05','URFI881121'),('aux_semis_2026jan15','AUXILIARY','2026-01-15','URFI881121'),('counter_realestate_2022jan24','COUNTER','2022-01-24','URFI881153'),('counter_software_2024oct8','COUNTER','2024-10-08','URFI881272'),('counter_multifinance_2024oct8','COUNTER','2024-10-08','URFI881283')]
 im=json.loads(bind(BASE/'INDUSTRY_MANIFEST.json').read_text());recs={r['series']:r for r in im};cp={}
 for sec in sorted({x[3]for x in cases}):
  r=recs[sec];p=r['refs']['CP1'];x=pd.read_parquet(bind(p,r['output_sha256'][p]));x.index=pd.DatetimeIndex(x.index).as_unit('ns');cp[sec]=x
 rows=[]
 for cid,role,day,sec in cases:
  k=cal.get_loc(pd.Timestamp(day));dates=cal[k-5:k+16];assert len(dates)==21
  for rel,d in zip(range(-5,16),dates):
   row=full.loc[(d,sec)].to_dict();row.update(case_id=cid,case_role=role,event_anchor=day,relative_session=rel,date=str(d.date()),sector_id_static=sec)
   original=cp[sec].loc[d];row.update({'cp_original_'+str(c):v for c,v in original.items()})
   row['cp_cached_r_over_prior63_s']=float(original.r/original.s)if pd.notna(original.s)and original.s>0 else np.nan
   row['row_information_clock']='daily close T; post-anchor rows are not known at anchor T0'
   row['membership_PIT_verified']=False;row['breadth_scope']='current-static 1709 selected-stock liquid U_t subpool; not all-A'
   row['index_amount_unit']='original index source amount unit; never used for cross-index sums'
   rows.append(row)
 out=pd.DataFrame(rows);assert len(out)==168 and not out.duplicated(['case_id','date']).any()
 out.to_parquet(O/'EXISTING_RAW_PATHS.parquet',index=False);out.to_csv(O/'EXISTING_RAW_PATHS.csv',index=False)
 out.loc[out.relative_session.eq(0)].to_csv(O/'ANCHOR_EXISTING_RAW.csv',index=False)
 keys=out[['date','sector_id_static']].drop_duplicates().sort_values(['date','sector_id_static']);keys.to_csv(O/'FIXED_UNIQUE_KEYS.csv',index=False)
 save_json('EXISTING_RAW_STATUS.json',dict(status='COMPLETE_EXISTING_RAW',rows=len(out),unique_date_sector=len(keys),unique_dates=int(out.date.nunique()),main=int(out.case_role.eq('MAIN').sum()),aux=int(out.case_role.eq('AUXILIARY').sum()),counter=int(out.case_role.eq('COUNTER').sum()),accounts_run=0,new_gates=0,unknown_policy='NA retained; no zero filling',cp_scale_definition='s=1.4826*median(previous63 abs(log close return)),shift1,min63,lowerclip1e-8; old z=max(s,log1p(.001)); frozen scale is separate',a_own_scope='Each B uses its own U at that date; composition changes retained.',a_pair_scope='Difference of two same-T paired dB5 values; cohorts across the two intervals can differ.'))
 save_json('EXISTING_RAW_SOURCE_SHA256.json',SOURCES)
 print(out.loc[out.relative_session.eq(0),['case_id','Nstatic','N_U_t','N_above20_t','N_above20_tminus5','B_now','a_own_raw','a_pair_raw','Bmarket_subpool','log_share5_over_share20_raw','cp_original_r','cp_original_s','cp_cached_r_over_prior63_s']].to_string(index=False))
 print('EXISTING_RAW_COMPLETE',len(out),'rows')
if __name__=='__main__':main()
