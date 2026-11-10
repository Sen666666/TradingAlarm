"""Frozen raw price diagnostics for two fixed counters; joins shared other legs."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;SELECTION=O.parents[1];PEER=O.parent/'feature_paths'
BASE=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
CSI=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USHI1B0300.csv');SOURCES={}
def bind(p,expected=None):
 p=Path(p).resolve();h=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected:assert h==expected,(str(p),'SHA mismatch')
 SOURCES[str(p)]=h;return p
def dump(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def price(f,cal):
 f=f.reindex(cal);c=f.close;seg=f.segment_id;valid=c.gt(0)&np.isfinite(c)&seg.notna();a=pd.DataFrame(index=cal);a['index_close']=c
 same2=valid.rolling(2,min_periods=2).sum().eq(2)&seg.eq(seg.shift());a['index_r1_log']=np.log(c/c.shift()).where(same2)
 for n in [20,60]:
  pv=valid.shift().rolling(n,min_periods=n).sum().eq(n);mx=seg.shift().rolling(n,min_periods=n).max();mn=seg.shift().rolling(n,min_periods=n).min();known=pv&valid&mx.eq(mn)&seg.eq(mx)
  high=c.shift().rolling(n,min_periods=n).max().where(known);a[f'prior{n}_high_close']=high;a[f'distance_to_prior{n}_high_log']=np.log(c/high).where(known)
  nh=pd.Series(pd.NA,index=cal,dtype='boolean');nh.loc[known]=c.loc[known].gt(high.loc[known]);a[f'newhigh{n}']=nh;a[f'crossup{n}']=nh&~nh.shift()
 a['index_segment_id']=seg;return a
def main():
 bind(__file__);bind(O.parent/'EXTRACTION_CONTRACT.txt');market=pd.read_csv(bind(CSI),parse_dates=['date']).set_index('date');cal=pd.DatetimeIndex(market.index).as_unit('ns')
 manifest=json.loads(bind(BASE/'INDUSTRY_MANIFEST.json').read_text());rows=[];checks=[]
 raw=pd.read_parquet(bind(O/'RAW_PATHS_WITH_COHORT_AMOUNTS.parquet'))
 for sec in ['URFI881153','URFI881283']:
  r=next(r for r in manifest if r['series']==sec);p=r['refs']['CP1_input'];f=pd.read_parquet(bind(p,r['output_sha256'][p]),columns=['close','segment_id']);f.index=pd.DatetimeIndex(f.index).as_unit('ns');z=price(f,cal)
  subset=raw.loc[raw.sector_id_static.eq(sec),['date','case_id','sector_id_static','relative_session']]
  for record in subset.to_dict('records'):
   d=pd.Timestamp(record['date']);record.update(z.loc[d].to_dict());rows.append(record)
  for d in [pd.Timestamp(subset.date.min()),pd.Timestamp(subset.loc[subset.relative_session.eq(0),'date'].iloc[0]),pd.Timestamp(subset.date.max())]:
   prefix=price(f.loc[:d],cal[cal<=d]).loc[d]
   pd.testing.assert_series_equal(prefix,z.loc[d],check_exact=True);checks.append(dict(sector=sec,date=str(d.date()),prefix_exact=True))
 counters=pd.DataFrame(rows);assert len(counters)==42;counters.to_parquet(O/'COUNTER_TWO_INDEX_PRICE_PATHS.parquet',index=False);counters.to_csv(O/'COUNTER_TWO_INDEX_PRICE_PATHS.csv',index=False)
 cols=['date','sector_id_static','index_close','index_r1_log','prior20_high_close','prior60_high_close','distance_to_prior20_high_log','distance_to_prior60_high_log','newhigh20','newhigh60','crossup20','crossup60','index_segment_id']
 pieces=[pd.read_parquet(bind(PEER/'CAUSAL_FEATURE_PATHS.parquet'))[cols],pd.read_parquet(bind(PEER/'COUNTEREXAMPLE_SOFTWARE_PRICE_PATHS.parquet'))[cols],counters[cols]]
 allp=pd.concat(pieces,ignore_index=True)
 for key,g in allp.groupby(['date','sector_id_static']):
  for col in cols[2:]:assert g[col].nunique(dropna=False)==1,(key,col,'shared price disagreement')
 allp=allp.drop_duplicates(['date','sector_id_static']);out=raw.merge(allp,on=['date','sector_id_static'],how='left',validate='many_to_one');assert len(out)==168 and out.index_r1_log.notna().all()
 m5=np.log(market.close/market.close.shift(5));out['market_R5_log']=pd.to_datetime(out.date).map(m5)
 out['index_R5_log']=out.rs_ind5+out.market_R5_log
 out['index_R5_provenance']='literal original rs_ind5 + same CSI300 common-session log return5; no price re-fit'
 assert np.allclose(out.index_r1_log,out.cp_original_r,rtol=0,atol=1e-14)
 out['z1_new_r1_over_cp_prior63_s']=(out.index_r1_log/out.cp_original_s).where(out.cp_original_s.gt(0))
 out['cp_r_vs_common_r1_difference']=out.cp_original_r-out.index_r1_log
 out['next_common_session']=pd.to_datetime(out.date).map(pd.Series(cal[1:].strftime('%Y-%m-%d'),index=cal[:-1]))
 out.to_parquet(O/'RAW_PATHS_COMPLETE.parquet',index=False);out.to_csv(O/'RAW_PATHS_COMPLETE.csv',index=False)
 out.loc[out.relative_session.eq(0)].to_csv(O/'ANCHOR_RAW_COMPLETE.csv',index=False)
 dump('PRICE_SOURCE_SHA256.json',SOURCES);dump('PRICE_PREFIX_CHECKS.json',checks)
 dump('PRICE_AND_RAW_STATUS.json',dict(status='COMPLETE',case_rows=len(out),main=int(out.case_role.eq('MAIN').sum()),aux=int(out.case_role.eq('AUXILIARY').sum()),counter=int(out.case_role.eq('COUNTER').sum()),counter_price_new_read_series=2,shared_price_series=3,prefix_checks=len(checks),cp_r_vs_common_r1_max_abs_difference=float(out.cp_r_vs_common_r1_difference.abs().max()),same_source_segment_required=True,newhigh_excludes_T=True,z1_definition='index common-session r1 / original saved prior63 robust s; old CP.z is scale, not this ratio',accounts=0,new_gates=0,new_rankings=0))
 print(out.loc[out.relative_session.eq(0),['case_id','index_r1_log','index_R5_log','newhigh20','newhigh60','crossup20','crossup60','z1_new_r1_over_cp_prior63_s','sector_amount_ratio21_sameTcohort','pool_amount_ratio21_sameTcohort']].to_string(index=False))
if __name__=='__main__':main()
