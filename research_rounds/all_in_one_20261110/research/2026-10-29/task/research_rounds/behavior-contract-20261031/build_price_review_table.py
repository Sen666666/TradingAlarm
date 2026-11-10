"""Market-only descriptive review roster; never reads trades or account PnL."""
from pathlib import Path
import json,time,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O.parent;RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
def main():
 start=time.monotonic();p=W/'market-mainline-measurement-20261031/FEATURE_MATRIX_90.parquet';m=pd.read_parquet(p);meta=json.loads((RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json').read_text());names={v['sector_id']:v['industry'] for v in meta.values()};gids=sorted(m.sector.unique());fx={g:pd.read_parquet(W/'mainline-absolute-Q4-20261031/industry-facts'/f'{g}.parquet',columns=['close']) for g in gids};rows=[];blocks=[];selected=[]
 for quarter in ['2025Q3','2025Q4','2026Q1']:
  ds=pd.DatetimeIndex(sorted(m[m.quarter==quarter].day.unique()));base={g:float(f.loc[f.index<ds[0]].close.iloc[-1]) for g,f in fx.items()};values=np.column_stack([fx[g].reindex(ds).close.to_numpy()/base[g]-1 for g in gids]);rr=[]
  for j,g in enumerate(gids):
   complete=bool(np.isfinite(values[:,j]).all());peak=int(values[:,j].argmax()) if complete else None;r=dict(review_id=f'{g}|{quarter}',quarter=quarter,sector=g,industry=names[g],start=str(ds[0].date()),end=str(ds[-1].date()),market_observations=len(ds),price_complete=complete,end_return=float(values[-1,j]) if complete else None,closeMFE=float(values[:,j].max()) if complete else None,closeMAE=float(values[:,j].min()) if complete else None,peak_observation=peak+1 if complete else None,peak_day=str(ds[peak].date()) if complete else None,R21_positive_fraction=float((m[(m.quarter==quarter)&(m.sector==g)].R21>0).mean()),human_market_label='pending_review',account_behavior='not_joined');rows.append(r);rr.append(r)
  continuous=sorted([r for r in rr if r['price_complete'] and r['end_return']>0],key=lambda r:(-r['end_return'],r['sector']));bounce=sorted([r for r in rr if r['price_complete'] and r['closeMFE']>0 and r['end_return']<=0 and r['peak_observation']<=21],key=lambda r:(-r['closeMFE'],r['sector']))
  if continuous:selected.append(dict(continuous[0],selection='positive_quarter_endpoint_rank1_candidate',eligible_count=len(continuous)))
  if bounce:selected.append(dict(bounce[0],selection='early_peak_then_nonpositive_endpoint_candidate',eligible_count=len(bounce)))
  for a in range(0,len(ds)-20,21):
   xx=ds[a:a+21];b={g:float(f.loc[f.index<xx[0]].close.iloc[-1]) for g,f in fx.items()};r=np.array([float(fx[g].loc[xx[-1]].close)/b[g]-1 for g in gids]);blocks.append(dict(review_id=f'ALL90|{xx[0].date()}|{xx[-1].date()}',quarter=quarter,start=str(xx[0].date()),end=str(xx[-1].date()),median90_return=float(np.median(r)),positive_industries=int((r>0).sum()),top_industry=names[gids[r.argmax()]],top_return=float(r.max()),human_market_label='weak_or_divergent_candidate_only_not_no_mainline',account_behavior='not_joined'))
  bb=[r for r in blocks if r['quarter']==quarter];selected.append(dict(sorted(bb,key=lambda r:(abs(r['median90_return']),r['start']))[0],selection='weakest_absolute_median_nonoverlap21_block_candidate',eligible_count=len(bb)))
 for name,data in [('ALL_270_INDUSTRY_QUARTERS',rows),('ALL_NONOVERLAP21_MARKET_BLOCKS',blocks),('CANDIDATES_PENDING_REVIEW',selected)]:
  (O/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');pd.DataFrame(data).to_csv(O/(name+'.csv'),index=False)
 result=dict(market_only=True,no_trades_or_account_performance_read=True,all_industry_quarters=len(rows),market_blocks=len(blocks),candidates=len(selected),incomplete_price_quarters=sum(not r['price_complete'] for r in rows),baseline='quarter/block previous close; highest/lowest closing price only',not_ground_truth_mainline=True,all_history_already_consumed=True,sha256={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in [Path(__file__),p]},seconds=time.monotonic()-start);(O/'ROSTER_BUILD.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(result)
if __name__=='__main__':main()
