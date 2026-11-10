"""Fixed 5/20/60 stock/real-index RS diagnostics, no account or CP recompute."""
from pathlib import Path
import hashlib,json,math,time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent;WORK=O.parents[1]
BASE=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
INPUT=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2')
SNAP=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/audit-snapshot')
BROAD=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018')
CASES=[('300085.SZ','银之杰','URFI881272','软件开发','2024-09-01','2024-11-30'),
       ('601019.SH','山东出版','URFI881164','文化传媒','2023-01-01','2023-12-31')]
HORIZONS=(5,20,60);HASH={}
CANONICAL={
 '300085.SZ':Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/MANIFEST.json'),
 '601019.SH':Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/recovery-2023-readiness-20261101/inputs/MANIFEST.json')}

def bind(p,expected=None):
 p=Path(p).resolve();h=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected is not None:assert h==expected,(str(p),'SHA mismatch')
 HASH[str(p)]=h;return p
def read(p):return json.loads(bind(p).read_text())
def clean(v):
 if v is pd.NA or v is pd.NaT:return None
 if isinstance(v,pd.Timestamp):return str(v.date())
 if isinstance(v,dict):return {str(k):clean(x)for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x)for x in v]
 if hasattr(v,'item'):return clean(v.item())
 if isinstance(v,float)and not math.isfinite(v):return None
 return v
def save(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def parquet(path,expected):
 f=pd.read_parquet(bind(path,expected))
 if 'trade_date'in f.columns:f=f.set_index('trade_date')
 f.index=pd.DatetimeIndex(f.index).as_unit('ns')
 assert f.index.is_unique and f.index.is_monotonic_increasing
 return f

def calculate(f,industry,market,stock_observed,industry_observed):
 # Use the same real broad-market calendar for all legs. No inner/dropna calendar.
 calendar=market.index
 x=pd.DataFrame(index=calendar)
 x['stock_CLOSE_a']=f.close.reindex(calendar)
 x['stock_raw_CLOSE']=f.raw_close.reindex(calendar)
 x['stock_factor']=f.factor.reindex(calendar)
 x['stock_segment']=f.segment_id.reindex(calendar)
 x['industry_CLOSE']=industry.close.reindex(calendar)
 x['industry_segment']=industry.segment_id.reindex(calendar)
 x['market_CLOSE']=market.close
 x['stock_observed']=stock_observed.reindex(calendar).fillna(False).astype(bool)
 x['industry_observed']=industry_observed.reindex(calendar).fillna(False).astype(bool)
 x['e0_target']=f.e0_target.reindex(calendar);x['i_target']=f.i_target.reindex(calendar)
 for h in HORIZONS:
  x['lag'+str(h)+'_date']=pd.Series(calendar,index=calendar).shift(h).dt.strftime('%Y-%m-%d')
  sv=x.stock_CLOSE_a.gt(0)&np.isfinite(x.stock_CLOSE_a)&x.stock_observed&x.stock_segment.notna()
  iv=x.industry_CLOSE.gt(0)&np.isfinite(x.industry_CLOSE)&x.industry_observed&x.industry_segment.notna()
  mv=x.market_CLOSE.gt(0)&np.isfinite(x.market_CLOSE)
  same_stock=x.stock_segment.rolling(h+1,min_periods=h+1).max().eq(x.stock_segment.rolling(h+1,min_periods=h+1).min())
  same_industry=x.industry_segment.rolling(h+1,min_periods=h+1).max().eq(x.industry_segment.rolling(h+1,min_periods=h+1).min())
  sk=sv.rolling(h+1,min_periods=h+1).sum().eq(h+1)&same_stock
  ik=iv.rolling(h+1,min_periods=h+1).sum().eq(h+1)&same_industry
  mk=mv.rolling(h+1,min_periods=h+1).sum().eq(h+1)
  sr=np.log(x.stock_CLOSE_a/x.stock_CLOSE_a.shift(h)).where(sk)
  ir=np.log(x.industry_CLOSE/x.industry_CLOSE.shift(h)).where(ik)
  mr=np.log(x.market_CLOSE/x.market_CLOSE.shift(h)).where(mk)
  x['stock_signal_return'+str(h)+'_pct']=np.expm1(sr)*100
  x['industry_price_return'+str(h)+'_pct']=np.expm1(ir)*100
  x['market_price_return'+str(h)+'_pct']=np.expm1(mr)*100
  a=sr-ir;b=ir-mr
  x['stock_vs_designated_industry_RS'+str(h)+'_logpct']=a*100
  x['stock_vs_designated_industry_RS'+str(h)+'_relativegrosspct']=np.expm1(a)*100
  x['industry_vs_market_RS'+str(h)+'_logpct']=b*100
  x['industry_vs_market_RS'+str(h)+'_relativegrosspct']=np.expm1(b)*100
  x['stock_industry_RS'+str(h)+'_numeric_known']=sk&ik
  x['industry_market_RS'+str(h)+'_numeric_known']=ik&mk
  # Historical stock-industry membership was not authenticated in the source.
  x['PIT_stock_industry_RS'+str(h)+'_logpct']=np.nan
  # Not total return. Mark exactly which windows contain stock adjustment changes.
  x['stock_adjustment_factor_changed'+str(h)]=x.stock_factor.rolling(h+1,min_periods=h+1).max().ne(x.stock_factor.rolling(h+1,min_periods=h+1).min()).where(sk)
  raw=np.log(x.stock_raw_CLOSE/x.stock_raw_CLOSE.shift(h)).where(sk)
  x['stock_raw_price_vs_industry_RS'+str(h)+'_logpct']=(raw-ir)*100
 return x

def main():
 start=time.monotonic();bind(__file__)
 sm={r['symbol']:r for r in read(BASE/'STOCK_MANIFEST.json')}
 im={r['series']:r for r in read(BASE/'INDUSTRY_MANIFEST.json')}
 source_input=read(INPUT/'input-manifest.json');records={r['series_id']:r for r in source_input['series']}
 metadata=read(INPUT/'metadata.json')
 bridge=pd.read_csv(bind(SNAP/'a-industry-index-bridge.csv'))
 bind('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/code/current_fixed_pool.py')
 market_protocol=read(BROAD/'protocol.json');market_checkpoint=read(BROAD/'checkpoints/USHI1B0300.json')
 market_integrity=read(BROAD/'integrity.json');names=read(BROAD/'server-names.json')
 target=next(x for x in market_integrity['symbols']if x['symbol']=='USHI1B0300')
 assert target['server_name']=='沪深300'and target['duplicate_dates']==0 and target['raw_page_hashes_verified']
 market_path=bind(BROAD/'canonical/USHI1B0300.csv',market_checkpoint['canonical_sha256'])
 market=pd.read_csv(market_path,parse_dates=['date']).set_index('date')
 market.index=market.index.as_unit('ns');assert market.index.is_unique and market.index.is_monotonic_increasing
 sector_protocol=read(Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-9603-20261018/protocol.json'))
 outputs=[];summary={};availability=[];prefix=[]
 for sid,name,sec,secname,lo,hi in CASES:
  s=sm[sid];r=im[sec]
  f=parquet(s['refs']['facts'],s['output_sha256'][s['refs']['facts']]).loc[:hi]
  cp=parquet(s['refs']['CP1'],s['output_sha256'][s['refs']['CP1']]).loc[:hi]
  g=parquet(r['refs']['CP1_input'],r['output_sha256'][r['refs']['CP1_input']]).loc[:hi]
  stockraw=parquet(records[sid]['raw']['path'],records[sid]['raw']['sha256']).loc[:hi]
  sectorraw=parquet(records[sec]['raw']['path'],records[sec]['raw']['sha256']).loc[:hi]
  actions=read(bind(records[sid]['adjustment']['actions']['path'],records[sid]['adjustment']['actions']['sha256']))
  assert records[sid]['adjustment']['method']=='theoretical_ex_price'
  assert records[sec]['adjustment']['method']=='unadjusted_index'
  common=f.index.intersection(stockraw.index)
  assert np.array_equal(f.loc[common,'raw_close'],stockraw.loc[common,'close'])
  common=g.index.intersection(sectorraw.index)
  assert np.array_equal(g.loc[common,'close'],sectorraw.loc[common,'close'])
  assert metadata[sid]['sector_id']==sec and metadata[sid]['industry']==secname
  obs=stockraw.observed_bar.eq(True)&stockraw.price_eligible.eq(True)&stockraw.synthetic_event_bar.ne(True)
  iobs=sectorraw.observed_bar.eq(True)&sectorraw.price_eligible.eq(True)
  mk=market.loc[:hi];full=calculate(f,g,mk,obs,iobs)
  for cut in [lo,str(full.loc[lo:hi].index[len(full.loc[lo:hi])//2].date()),hi]:
   small=calculate(f.loc[:cut],g.loc[:cut],mk.loc[:cut],obs.loc[:cut],iobs.loc[:cut])
   pd.testing.assert_frame_equal(small,full.loc[small.index],check_exact=True)
   prefix.append(dict(sid=sid,cut=cut,exact=True))
  cm=next(x for x in read(CANONICAL[sid])if x['sid']==sid)
  assert cm['refs']['CP1']==s['refs']['CP1']
  rr=read(bind(cm['output_path'],cm['output_sha256']));receipts={x['confirmed_day']:x for x in rr}
  z=full.loc[lo:hi].copy();z.index.name='date'
  z['sid']=sid;z['name']=name;z['designated_industry_id']=sec;z['designated_industry_name']=secname
  z['market_id']='USHI1B0300';z['market_name']='沪深300';z['PIT_membership_known']=False
  z['membership_unknown_reason']='Only 2026-10-22 current industry snapshot; no historical effective-dated assignment authenticated.'
  z['original_CP_receipt']=cp.receipt.reindex(z.index)
  z['original_CP_new_frontier']=cp.delta_frontier.reindex(z.index).gt(0)
  z['original_CP_reset_reason']=cp.reset_reason.reindex(z.index)
  z['original_CP_candidate_a']=cp.candidate.reindex(z.index)
  z['original_canonical_receipt_id']=[receipts.get(str(d.date()),{}).get('receipt_id')for d in z.index]
  assert z.original_CP_receipt.fillna(False).eq(z.original_canonical_receipt_id.notna()).all()
  z.to_csv(O/(sid+'_ALL_DAILY_RS.csv'))
  save(sid+'_ALL_DAILY_RS.json',z.reset_index().to_dict('records'))
  z.loc[z.original_CP_receipt.eq(True)].to_csv(O/(sid+'_ALL_ORIGINAL_CP_RS.csv'))
  outputs.append(z)
  summary[sid]=dict(name=name,window=[lo,hi],stock_CLOSEs=len(z),original_CP_receipts=int(z.original_CP_receipt.eq(True).sum()),
      designated_industry=secname,designated_industry_id=sec,PIT_membership_known=False,
      windows={str(h):dict(stock_industry_numeric_known=int(z['stock_industry_RS'+str(h)+'_numeric_known'].sum()),
          industry_market_numeric_known=int(z['industry_market_RS'+str(h)+'_numeric_known'].sum()),
          CP_stock_designated_industry_RS_positive=int((z.original_CP_receipt.eq(True)&z['stock_vs_designated_industry_RS'+str(h)+'_logpct'].gt(0)).sum()),
          CP_industry_market_RS_positive=int((z.original_CP_receipt.eq(True)&z['industry_vs_market_RS'+str(h)+'_logpct'].gt(0)).sum()),
          CP_both_RS_positive=int((z.original_CP_receipt.eq(True)&z['stock_vs_designated_industry_RS'+str(h)+'_logpct'].gt(0)&z['industry_vs_market_RS'+str(h)+'_logpct'].gt(0)).sum()),
          stock_factor_change_windows=int(z['stock_adjustment_factor_changed'+str(h)].eq(True).sum()))for h in HORIZONS})
  b=bridge.loc[bridge.index_symbol.eq(sec)].to_dict('records');assert len(b)==1
  availability.append(dict(sid=sid,name=name,original_static_metadata=metadata[sid],bridge=b[0],PIT_membership_known=False,
      industry_source=r['refs']['CP1_input'],industry_price_adjustment=records[sec]['adjustment'],
      stock_signal_adjustment=records[sid]['adjustment'],stock_actions_in_selected_year=[x for x in actions['events']if lo[:4]<=x['effective_date'][:4]<=hi[:4]],
      stock_is_not_total_return=True,industry_is_price_index=True,market_is_price_index=True))
 allrows=pd.concat(outputs)
 wanted={'300085.SZ':['2024-09-23','2024-09-24','2024-10-10','2024-10-14','2024-10-16','2024-10-28'],
         '601019.SH':['2023-04-06','2023-04-11','2023-04-12','2023-04-14','2023-04-18','2023-04-19']}
 keys=pd.concat([z.loc[z.index.isin(pd.to_datetime(wanted[z.sid.iloc[0]]))]for z in outputs])
 keys.to_csv(O/'KEY_ROWS.csv');save('KEY_ROWS.json',keys.reset_index().to_dict('records'))
 save('SUMMARY.json',summary)
 save('SOURCE_AVAILABILITY.json',dict(stocks=availability,market=dict(vendor_symbol='USHI1B0300',server_name='沪深300',
      published_index_code_in_local_protocol='000300',source=str(market_path),source_sha256=HASH[str(market_path)],
      price_adjustment='price index raw; no total-return series loaded',historical_members_not_needed_for_supplied_index=True,
      data_integrity=target,publication_metadata_in_local_protocol_unverified=True),
      membership='No historical membership reconstructed. Static metadata is an explicitly chosen reference, not proof of 2023/2024 membership.',
      source_search_scope='Original universe industry manifest; original input-manifest; current snapshot bridge/current_fixed_pool; original THS market-index canonical/checkpoint/integrity/protocol.',
      no_custom_industry_index=True))
 save('SCOPE_AND_FORMULAS.json',dict(horizons=list(HORIZONS),main_horizon=20,parameters_fitted=False,
      RS='100*[ln(A_t/A_t-h)-ln(B_t/B_t-h)] in log percentage points; relativegrosspct=100*[exp(RS/100)-1] also saved.',
      calendar='One real CSI300 trading-date grid. Both legs use identical t and t-h. No each-series dropna, forward fill, or compressed gap windows.',
      known='All h+1 observations must be positive/finite/observed and same original source segment, not only endpoints.',
      price_basis='Stock original theoretical-ex-price continuous technical signal; industry and market raw price indices. No total-return interpretation; raw-stock-price sensitivity and adjustment-factor-change flags saved.',
      PIT='PIT stock-industry RS remains null. Numeric stock-vs-designated-index RS is available but does not prove historical classification.',
      sample='Parent-selected two stocks, all 2024SepNov/2023 original stock CLOSEs and CP receipts retained without winner/forward-return screening.',
      original_models_recomputed=False,new_accounts=0,new_CP_FSM=0,new_backtests=0,future_price_labels_calculated=False,
      physical_prefix_checks=prefix,seconds=time.monotonic()-start))
 save('SOURCE_SHA256.json',HASH)
 print(json.dumps(clean(summary),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
