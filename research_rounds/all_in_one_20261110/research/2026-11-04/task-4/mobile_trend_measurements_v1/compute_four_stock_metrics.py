"""Four specified stocks only: descriptive CLOSE metrics; no strategy/account."""
from pathlib import Path
import hashlib,json,math
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
CASES=[('000620.SZ','盈新','2022-01-04','2022-02-08'),('002583.SZ','海能达','2024-09-23','2024-11-27'),('601019.SH','山东出版','2023-03-20','2023-05-09'),('000547.SZ','航天发展','2025-10-22','2026-01-16')]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def metrics(f,s,e,cp,g=None):
 c=f.close.astype(float);valid=np.isfinite(c)&c.gt(0)&f.segment_id.notna()
 block=(f.segment_id.ne(f.segment_id.shift())|~valid|~valid.shift(fill_value=False)).cumsum()
 out=pd.DataFrame(index=f.index);out.index.name='date'
 out['close_a']=c;out['raw_close']=f.raw_close;out['factor']=f.factor;out['source_segment']=f.segment_id
 out['seed_date']=pd.Series(f.index,index=f.index).where(valid).groupby(block,sort=False).transform('first').dt.strftime('%Y-%m-%d')
 out['observations_from_seed']=valid.astype(int).groupby(block,sort=False).cumsum()
 for n in [20,60]:
  out[f'ema{n}_a']=c.where(valid).groupby(block,sort=False).transform(lambda z:z.ewm(span=n,adjust=False,min_periods=n).mean())
  out[f'ema{n}_raw_current_units']=out[f'ema{n}_a']/f.factor
  out[f'ema{n}_ready']=out[f'ema{n}_a'].notna()
 lag=out.ema20_a.groupby(block,sort=False).shift(5)
 out['ema20_five_observation_change_pct']=100*(out.ema20_a/lag-1)
 out['ema20_five_observation_slope_pct_per_observation']=out.ema20_five_observation_change_pct/5
 out['close_deviation_ema20_pct']=100*(c/out.ema20_a-1)
 for label,lo,hi in [('hl',s.low.reindex(f.index),s.high.reindex(f.index)),('close',c,c)]:
  low=lo.where(valid).groupby(block,sort=False).transform(lambda z:z.shift(1).rolling(20,min_periods=20).min())
  high=hi.where(valid).groupby(block,sort=False).transform(lambda z:z.shift(1).rolling(20,min_periods=20).max())
  out[f'prior20_{label}_low_a']=low;out[f'prior20_{label}_high_a']=high
  out[f'prior20_{label}_position_pct']=100*(c-low)/(high-low).where((high-low)>0)
 # Use original confirmed turning events available no later than this CLOSE.
 peaks=e.loc[e.event.eq(-1)&e.confirmed_pivot_price.notna()].copy()
 peaks=peaks.loc[np.isfinite(peaks.confirmed_pivot_price)&peaks.confirmed_pivot_price.gt(0)]
 for col in ['last_confirmed_peak_a','last_confirmed_peak_pivot_raw_saved']:
  out[col]=np.nan
 out['last_confirmed_peak_confirmation_day']=None;out['last_confirmed_peak_pivot_day']=None
 for seg,ix in f.groupby('segment_id',sort=False).groups.items():
  ps=peaks.loc[peaks.segment_id.eq(seg)];j=0;known=None;items=list(ps.iterrows())
  for day in ix:
   while j<len(items)and items[j][0]<=day:known=items[j];j+=1
   if known is None:continue
   confirm,row=known;pivot=pd.Timestamp(row.confirmed_pivot_date)
   out.at[day,'last_confirmed_peak_a']=float(row.confirmed_pivot_price)
   out.at[day,'last_confirmed_peak_confirmation_day']=str(confirm.date())
   out.at[day,'last_confirmed_peak_pivot_day']=str(pivot.date())
   if pivot in f.index:out.at[day,'last_confirmed_peak_pivot_raw_saved']=float(f.loc[pivot,'raw_close'])
 out['last_confirmed_peak_raw_current_units']=out.last_confirmed_peak_a/f.factor
 out['signed_gap_to_confirmed_peak_pct']=100*(c/out.last_confirmed_peak_a-1)
 out['drawdown_from_confirmed_peak_pct']=(-out.signed_gap_to_confirmed_peak_pct).clip(lower=0)
 for col in ['e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_fresh_up','g_acute_down','g_ready']:
  out[col]=f[col]
 out['CP_market_receipt']=cp.receipt.reindex(f.index)
 out['CP_candidate_a']=cp.candidate.reindex(f.index)
 out['CP_frozen_scale']=cp.scale.reindex(f.index)
 out['CP_reset_reason']=cp.reset_reason.reindex(f.index)
 if g is not None:
  for src,dst in [('up_reasons','G1_up_reasons_saved'),('phase','G1_phase_saved'),('z5','G1_z5_saved'),('z21','G1_z21_saved')]:
   out[dst]=g[src].reindex(f.index)if src in g else None
 return out

def main():
 (OUT/'metrics').mkdir(exist_ok=True)
 records=json.loads(MANIFEST.read_text());metadata=[];all_receipts=[];checks=[]
 for sid,name,start,end in CASES:
  rec=next(r for r in records if r['symbol']==sid)
  paths={'facts':rec['refs']['facts'],'CP':rec['refs']['CP1'],'signal':next(p for p in rec['source_sha256']if p.endswith('/signal.parquet')),'events':next(p for p in rec['source_sha256']if p.endswith('/events.parquet')),'G1_source':next(p for p in rec['source_sha256']if '/ix-a-share-entry-'in p and p.endswith('/'+sid+'.parquet'))}
  frames={};sources={}
  for kind,path in paths.items():
   h=sha(path);expected=rec.get('output_sha256',{}).get(path,rec.get('source_sha256',{}).get(path));assert h==expected,(sid,kind,'source hash')
   frames[kind]=pd.read_parquet(path);frames[kind].index=frames[kind].index.as_unit('ns');assert frames[kind].index.is_unique and frames[kind].index.is_monotonic_increasing
   sources[kind]={'path':path,'sha256':h}
  f,s,e,cp,g=[frames[k]for k in ['facts','signal','events','CP','G1_source']]
  # Never supply a different normalized price series to the old numeric facts.
  shared=f.index.intersection(s.index);assert np.array_equal(f.loc[shared,'close'].to_numpy(),s.loc[shared,'close'].to_numpy()),(sid,'numeric source mismatch')
  common=f.loc[start:end].index.intersection(g.index)
  assert np.array_equal(f.loc[common,'g_grade'].to_numpy(float),g.loc[common,'grade'].to_numpy(float),equal_nan=True)
  assert np.array_equal(f.loc[common,'g_fresh_up'].to_numpy(bool),g.loc[common,'fresh_up'].to_numpy(bool))
  full=metrics(f,s,e,cp,g);selected=full.loc[start:end].copy();selected.insert(0,'name',name);selected.insert(0,'sid',sid)
  selected.to_csv(OUT/'metrics'/f'{sid}.csv')
  mobile=selected.loc[selected.CP_market_receipt.fillna(False).astype(bool)].copy();mobile.to_csv(OUT/'metrics'/f'{sid}_CP_RECEIPTS.csv');all_receipts.append(mobile)
  # Target-window prefix check recomputes only this stock's descriptive metrics.
  for cut in sorted({start,str(selected.index[len(selected)//2].date()),end}):
   prefix=metrics(f.loc[:cut],s.loc[:cut],e.loc[:cut],cp.loc[:cut],g.loc[:cut]);pd.testing.assert_frame_equal(prefix,full.loc[prefix.index],check_exact=True)
   checks.append({'sid':sid,'cut':cut,'exact':True})
  metadata.append({'sid':sid,'name':name,'start':start,'end':end,'rows':len(selected),'CP_receipt_rows':len(mobile),'full_input_first_date':str(f.index[0].date()),'first_selected_seed_date':selected.seed_date.iloc[0],'first_selected_observations_from_seed':int(selected.observations_from_seed.iloc[0]),'all_selected_EMA20_60_ready':bool(selected[['ema20_a','ema60_a']].notna().all().all()),'sources':sources})
 pd.concat(all_receipts).sort_values(['sid','date']).to_csv(OUT/'metrics/ALL_FOUR_CP_RECEIPTS.csv')
 save('METRIC_INPUTS_AND_WARMUP.json',metadata);save('PREFIX_CHECKS.json',checks)
 save('COMPUTE_SCOPE.json',{'stocks':4,'new_descriptive_indicators_only':True,'new_accounts':0,'new_strategy_or_parameter_tests':0,'E0_G1_I_CP_PVR_recomputed':False,'EMA_definition':'Matches original build_price_features.py EMA formula; only4 stocks processed','definitions_sha256':sha(OUT/'FROZEN_DEFINITIONS.txt'),'script_sha256':sha(__file__),'manifest_sha256':sha(MANIFEST),'prefix_checks':len(checks),'only_saved_source_data':True})
 print(json.dumps([{'sid':m['sid'],'rows':m['rows'],'CP':m['CP_receipt_rows'],'seed':m['first_selected_seed_date'],'warm_observations':m['first_selected_observations_from_seed']}for m in metadata],ensure_ascii=False))

if __name__=='__main__':main()
