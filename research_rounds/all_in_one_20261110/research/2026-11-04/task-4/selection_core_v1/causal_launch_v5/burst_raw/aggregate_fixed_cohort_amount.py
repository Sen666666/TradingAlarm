"""Same-T U cohort CNY sums, fixed case dates. Reuses frozen pure U kernel."""
from pathlib import Path
import hashlib,importlib.util,json,time
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;SELECTION=O.parents[1]
BASE=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
META=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
CSI=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USHI1B0300.csv')
SOURCES={}
def bind(p,expected=None):
 p=Path(p).resolve();h=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected:assert h==expected,(str(p),'SHA mismatch')
 SOURCES[str(p)]=h;return p
def dump(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 begun=time.monotonic();bind(__file__);bind(O.parent/'EXTRACTION_CONTRACT.txt')
 spec=importlib.util.spec_from_file_location('frozen_aggregate_kernel',bind(SELECTION/'industry_selection/channels_v2/compute_opportunities.py'))
 kernel=importlib.util.module_from_spec(spec);spec.loader.exec_module(kernel)
 sm=json.loads(bind(BASE/'STOCK_MANIFEST.json').read_text());meta=json.loads(bind(META).read_text())
 keys=pd.read_csv(bind(O/'FIXED_UNIQUE_KEYS.csv'));dates=pd.DatetimeIndex(sorted(pd.to_datetime(keys.date.unique()))).as_unit('ns')
 market=pd.read_csv(bind(CSI),parse_dates=['date']).set_index('date');cal=pd.DatetimeIndex(market.index).as_unit('ns')
 # Reproduce the saved v2 kernel's original common-calendar prefix exactly.
 # pandas rolling arithmetic at mathematical ties can depend on the prefix.
 first_original_study=cal[(cal>='2022-01-01')&(cal<='2026-06-30')][0]
 start=cal.get_loc(first_original_study)-29;end=cal.get_loc(dates[-1]);grid=cal[start:end+1]
 loc=grid.get_indexer(dates);assert (loc>=24).all();offsets=np.arange(-21,1);amount_indices=loc[:,None]+offsets
 sectors=sorted({meta[r['symbol']]['sector_id']for r in sm});si={s:i for i,s in enumerate(sectors)};n=len(dates)
 counts=np.zeros((len(sectors),n),dtype=int);up=np.zeros_like(counts);up5=np.zeros_like(counts)
 sums=np.zeros((len(sectors),n,22),dtype=float);flow20=np.zeros((len(sectors),n),dtype=float);masks=[]
 for i,r in enumerate(sm):
  sid=r['symbol'];sector=meta[sid]['sector_id'];j=si[sector]
  paths=[p for p in r['source_sha256']if '/prepared'in p and p.endswith('/signal.parquet')];assert len(paths)==1
  s=pd.read_parquet(bind(paths[0],r['source_sha256'][paths[0]]),columns=kernel.COLS)
  s.index=pd.DatetimeIndex(s.index).as_unit('ns');assert s.index.is_unique and s.index.is_monotonic_increasing
  x=kernel.stock_state(s,grid);u=x['U'].reindex(dates).to_numpy(dtype=bool)
  above=x['above'].reindex(dates).to_numpy(dtype=bool);above5=x['above5'].reindex(dates).to_numpy(dtype=bool)
  counts[j]+=u.astype(int);up[j]+=(u&above).astype(int);up5[j]+=(u&above5).astype(int)
  a=pd.to_numeric(s.amount.reindex(grid),errors='coerce').to_numpy(dtype=float)[amount_indices]
  assert np.isfinite(a[u]).all()and (a[u]>0).all(),(sid,'qualified U lacks daily CNY amount')
  sums[j]+=np.where(u[:,None],a,0.)
  flow20[j]+=x['flow20'].reindex(dates).to_numpy(dtype=float)
  masks.append(pd.DataFrame({'date':dates.strftime('%Y-%m-%d'),'sid':sid,'sector_id_static':sector,'qualified_U_t':u,'above20_T_if_U':pd.array([bool(v)if q else None for q,v in zip(u,above)],dtype='boolean'),'above20_Tminus5_if_U':pd.array([bool(v)if q else None for q,v in zip(u,above5)],dtype='boolean')}))
  if(i+1)%200==0:
   p=dict(status='RUNNING',stocks=i+1,total=len(sm),seconds=time.monotonic()-begun);dump('AMOUNT_PROGRESS.json',p);print(json.dumps(p),flush=True)
 old=pd.read_parquet(bind(SELECTION/'industry_selection/channels_v2/INDUSTRY_OPPORTUNITIES_DAILY.parquet')).set_index(['date','sector_id_static'])
 pool=sums.sum(axis=0);pooln=counts.sum(axis=0);poolup=up.sum(axis=0);poolf20=flow20.sum(axis=0)
 rows=[];maxshare=0.
 for sector,j in si.items():
  for k,d in enumerate(dates):
   day=str(d.date());was=old.loc[(day,sector)];assert int(was.N_U_t)==counts[j,k],(day,sector,'U mismatch')
   assert int(was.N_above20_t)==up[j,k]and int(was.N_above20_tminus5)==up5[j,k],(day,sector,'breadth mismatch')
   current=sums[j,k,-1];median=float(np.median(sums[j,k,:-1]));pm=float(np.median(pool[k,:-1]))
   share5=sums[j,k,-5:].sum()/pool[k,-5:].sum();share20=flow20[j,k]/poolf20[k]
   if pd.notna(was.share5):maxshare=max(maxshare,abs(float(was.share5)-share5),abs(float(was.share20)-share20))
   rows.append(dict(date=day,sector_id_static=sector,N_U_t=int(counts[j,k]),N_above20_t=int(up[j,k]),N_above20_tminus5=int(up5[j,k]),pool_N_U_t=int(pooln[k]),pool_N_above20_t=int(poolup[k]),sector_amount_CNY_T_sameTcohort=float(current),sector_prior21_daily_aggregate_median_CNY_sameTcohort=median,sector_amount_ratio21_sameTcohort=float(current/median)if median>0 else None,pool_amount_CNY_T_sameTcohort=float(pool[k,-1]),pool_prior21_daily_aggregate_median_CNY_sameTcohort=pm,pool_amount_ratio21_sameTcohort=float(pool[k,-1]/pm)if pm>0 else None,reconstructed_share5=share5,reconstructed_share20=share20,membership_PIT_verified=False))
 assert maxshare<1e-12,maxshare
 agg=pd.DataFrame(rows);agg.to_parquet(O/'ALL90_FIXED_DATE_COHORT_AMOUNTS.parquet',index=False);agg.to_csv(O/'ALL90_FIXED_DATE_COHORT_AMOUNTS.csv',index=False)
 mask=pd.concat(masks,ignore_index=True);assert not mask.duplicated(['date','sid']).any();mask.to_parquet(O/'U_T_MASK_ALL_FIXED_DATES.parquet',index=False)
 existing=pd.read_parquet(bind(O/'EXISTING_RAW_PATHS.parquet'));out=existing.merge(agg,on=['date','sector_id_static'],how='left',validate='many_to_one',suffixes=('','_amountaudit'))
 assert len(out)==168 and out.sector_amount_ratio21_sameTcohort.notna().all()
 out.to_parquet(O/'RAW_PATHS_WITH_COHORT_AMOUNTS.parquet',index=False);out.to_csv(O/'RAW_PATHS_WITH_COHORT_AMOUNTS.csv',index=False)
 out.loc[out.relative_session.eq(0)].to_csv(O/'ANCHOR_RAW_WITH_AMOUNTS.csv',index=False)
 dump('AMOUNT_SOURCE_SHA256.json',SOURCES)
 dump('AMOUNT_STATUS.json',dict(status='COMPLETE',stocks=len(sm),unique_dates=n,all90_date_rows=len(agg),mask_rows=len(mask),case_rows=len(out),all_U_counts_exact=True,all_current_and_lag5_Nup_exact=True,max_abs_old_share_reconstruction_difference=maxshare,seconds=time.monotonic()-begun,accounts=0,new_qualification_rules=0,definition='At each T, use frozen U_T member set over T-21..T; median of 21 aggregate daily amounts, not sum of stock medians.',units='Original stock amount_unit==CNY, positive and observed under original U; no industry-index amount is summed.',timing='All daily T inputs only known at T close; no OPEN fills implied.'))
 print(out.loc[out.relative_session.eq(0),['case_id','N_U_t','sector_amount_CNY_T_sameTcohort','sector_prior21_daily_aggregate_median_CNY_sameTcohort','sector_amount_ratio21_sameTcohort','pool_amount_ratio21_sameTcohort']].to_string(index=False));print('AMOUNT_COMPLETE',len(out),'rows',time.monotonic()-begun,'seconds')
if __name__=='__main__':main()
