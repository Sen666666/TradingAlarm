"""Frozen 17-feature original CP event batch. No labels/model/account imports."""
from pathlib import Path
from collections import Counter
import hashlib,json,time,traceback
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent;ROOT=O.parent
BASE=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
INPUT=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2')
MARKET=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018')
FEATURES=['sm5','sm20','im5','im20','d5_sm5','d5_sm20','d5_im5','d5_im20',
          'channel20','ema20_slope5','ema60_slope5','dd20','ln_amount_ratio21',
          'up_frac5','down_frac5','up_amount_frac5','down_amount_frac5']
GROUPS={'G1':FEATURES[:8],'G2':FEATURES[8:12],'G3':FEATURES[12:]}
EVENT_COLUMNS=['sid','date','canonical_receipt_id','original_CP_flag','sector_static','industry_static','segment']
SOURCES={};LIMIT=600.;START='2022-01-01';END='2026-06-30'

def bind(p,expected=None):
 p=Path(p).resolve();h=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected is not None:assert h==expected,(str(p),'source SHA mismatch')
 SOURCES[str(p)]=h;return p
def read(p):return json.loads(bind(p).read_text())
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def parquet(p,expected,columns=None):
 f=pd.read_parquet(bind(p,expected),columns=columns)
 f.index=pd.DatetimeIndex(f.index).as_unit('ns');assert f.index.is_unique and f.index.is_monotonic_increasing
 return f
def true(s):return s.eq(True).fillna(False).astype(bool)
def false(s):return s.eq(False).fillna(False).astype(bool)
def positive(s):return s.gt(0)&np.isfinite(s)
def complete(valid,segment,n):
 return valid.rolling(n,min_periods=n).sum().eq(n)&segment.rolling(n,min_periods=n).max().eq(segment.rolling(n,min_periods=n).min())
def common_price(frame,index,signal=False):
 x=frame.reindex(index)
 c=pd.to_numeric(x.close,errors='coerce').astype(float);seg=pd.to_numeric(x.segment_id,errors='coerce')
 valid=positive(c)&seg.notna()
 if signal:
  valid &= true(x.observed_bar)&false(x.synthetic_event_bar)&true(x.price_eligible)&false(x.source_invalid)
 return c.where(valid),seg,valid
def logret(c,seg,valid,h):return np.log(c/c.shift(h)).where(complete(valid,seg,h+1))

def calculate(signal,industry,market):
 """Only trailing expressions; EMA state follows valid stock observations."""
 idx=market.index[(market.index>=signal.index.min())&(market.index<=pd.Timestamp(END))]
 s=signal.reindex(idx);C,seg,cv=common_price(signal,idx,True)
 M=market.close.reindex(idx);mv=positive(M)
 mseg=pd.Series(0.,index=idx)
 if industry is None:
  I=pd.Series(np.nan,index=idx);iseg=I.copy();iv=pd.Series(False,index=idx)
 else:I,iseg,iv=common_price(industry,idx)
 out=pd.DataFrame(index=idx)
 for h in(5,20):
  sm=logret(C,seg,cv,h)-logret(M,mseg,mv,h)
  im=logret(I,iseg,iv,h)-logret(M,mseg,mv,h)
  out['sm'+str(h)]=sm;out['im'+str(h)]=im
  out['d5_sm'+str(h)]=(sm-sm.shift(5)).where(complete(cv&mv,seg,h+6))
  out['d5_im'+str(h)]=(im-im.shift(5)).where(complete(iv&mv,iseg,h+6))
 # EMA updates on this stock's actual valid closes, not missing union sessions.
 known=signal.loc[true(signal.observed_bar)&false(signal.synthetic_event_bar)&true(signal.price_eligible)&false(signal.source_invalid)].copy()
 known=known.loc[positive(pd.to_numeric(known.close,errors='coerce'))&known.segment_id.notna()]
 run=known.segment_id.ne(known.segment_id.shift()).cumsum()
 full65=complete(cv,seg,65)
 for n in(20,60):
  ema=known.close.astype(float).groupby(run,sort=False).transform(lambda v:v.ewm(span=n,adjust=False,min_periods=n).mean()).reindex(idx)
  out['ema'+str(n)+'_slope5']=(np.log(ema/ema.shift(5))/5).where(full65)
 H=pd.to_numeric(s.high,errors='coerce');L=pd.to_numeric(s.low,errors='coerce')
 hv=cv&positive(H)&positive(L)&H.ge(L)&H.ge(C)&L.le(C)
 hi=H.where(hv).shift(1).rolling(20,min_periods=20).max()
 lo=L.where(hv).shift(1).rolling(20,min_periods=20).min()
 width=hi-lo
 out['channel20']=((C-lo)/width).where(width.gt(0)&complete(cv,seg,21))
 out['dd20']=np.log(C.rolling(20,min_periods=20).max()/C).where(complete(cv,seg,20))
 # Own amount validity; missing share-volume is not an amount-invalid proxy.
 A=pd.to_numeric(s.amount,errors='coerce').astype(float)
 av=(positive(A)&true(s.observed_bar)&false(s.synthetic_event_bar)&false(s.source_invalid)
     &s.amount_unit.eq('CNY').fillna(False)&seg.notna())
 A=A.where(av)
 median=A.shift(1).rolling(21,min_periods=21).median()
 out['ln_amount_ratio21']=np.log(A/median).where(complete(av,seg,22)&median.gt(0))
 previous=C.shift(1);direction=C.notna()&previous.notna()
 up=C.gt(previous).astype(float).where(direction);down=C.lt(previous).astype(float).where(direction)
 six=complete(cv,seg,6)
 out['up_frac5']=(up.rolling(5,min_periods=5).sum()/5).where(six)
 out['down_frac5']=(down.rolling(5,min_periods=5).sum()/5).where(six)
 total=A.rolling(5,min_periods=5).sum();both=six&complete(av,seg,5)
 out['up_amount_frac5']=((A*up).rolling(5,min_periods=5).sum()/total).where(both)
 out['down_amount_frac5']=((A*down).rolling(5,min_periods=5).sum()/total).where(both)
 out=out[FEATURES].replace([np.inf,-np.inf],np.nan)
 return out,dict(close=C,segment=seg,price_valid=cv,amount_valid=av,channel_width=width,recent65=full65,
                 market20_log=logret(M,mseg,mv,20))

def missing_description(row,width,industry_present):
 names=[k for k in FEATURES if pd.isna(row[k])]
 reasons=[]
 for k in names:
  if k.startswith(('sm','d5_sm')):why='stock_market_common_window_or_segment'
  elif k.startswith(('im','d5_im')):why='industry_market_common_window_or_segment'if industry_present else'missing_designated_industry_index'
  elif k=='channel20':why='flat_prior20_channel'if pd.notna(width)and width==0 else'prior20_HL_or_current_close_or_segment'
  elif k.startswith('ema'):why='recent65_common_sessions_or_EMA_warm'
  elif k=='dd20':why='close20_window_or_segment'
  elif k=='ln_amount_ratio21':why='amount22_window_units_or_segment'
  elif k in('up_frac5','down_frac5'):why='close6_window_or_segment'
  else:why='close6_or_amount5_window_units_or_segment'
  reasons.append(k+':'+why)
 return '|'.join(names),';'.join(reasons)

def main():
 begun=time.monotonic();bind(__file__);bind(ROOT/'FROZEN_DESIGN.txt')
 sm={r['symbol']:r for r in read(BASE/'STOCK_MANIFEST.json')}
 im={r['series']:r for r in read(BASE/'INDUSTRY_MANIFEST.json')}
 meta=read(INPUT/'metadata.json')
 events=pd.read_csv(bind(ROOT/'universe_audit/CP_EVENT_INDEX_2022_2026H1.csv'),usecols=EVENT_COLUMNS,dtype={'sid':str,'date':str,'canonical_receipt_id':'string'})
 assert len(events)==99031 and not events.duplicated(['sid','date']).any()and events.original_CP_flag.eq(True).all()
 assert events.date.between(START,END).all()
 cp=read(MARKET/'checkpoints/USHI1B0300.json')
 market=pd.read_csv(bind(MARKET/'canonical/USHI1B0300.csv',cp['canonical_sha256']),parse_dates=['date']).set_index('date').loc[:END]
 market.index=market.index.as_unit('ns');assert market.index.is_unique and market.index.is_monotonic_increasing
 industries={};industry_errors=[]
 for sec in sorted(set(events.sector_static)):
  if sec not in im:industries[sec]=None;industry_errors.append(sec);continue
  r=im[sec];industries[sec]=parquet(r['refs']['CP1_input'],r['output_sha256'][r['refs']['CP1_input']],['close','segment_id']).loc[:END]
 grouped={sid:g for sid,g in events.groupby('sid',sort=True)};stocks=sorted(grouped)
 samples={stocks[i]for i in(0,len(stocks)//4,len(stocks)//2,3*len(stocks)//4,len(stocks)-1)}
 result=[];prefix=[];errors=[];source_signal_rows=0;event_coordinate_checks=0
 for position,sid in enumerate(stocks):
  if time.monotonic()-begun>LIMIT:raise TimeoutError('Feature-only time cap exceeded; partial retained')
  r=sm[sid];es=grouped[sid].copy();dates=pd.to_datetime(es.date)
  paths=[p for p in r['source_sha256']if '/prepared' in p and p.endswith('/signal.parquet')]
  assert len(paths)==1,(sid,'expected unique source signal')
  signal=parquet(paths[0],r['source_sha256'][paths[0]]).loc[:END]
  facts=parquet(r['refs']['facts'],r['output_sha256'][r['refs']['facts']],['close','segment_id']).loc[:END]
  inp=parquet(r['refs']['CP1_input'],r['output_sha256'][r['refs']['CP1_input']],['close','segment_id']).loc[:END]
  original=parquet(r['refs']['CP1'],r['output_sha256'][r['refs']['CP1']],['receipt']).loc[START:END]
  od=original.index[original.receipt.eq(True)]
  assert set(od)==set(dates),(sid,'original CP mother changed')
  assert dates.isin(signal.index).all()and dates.isin(facts.index).all()and dates.isin(inp.index).all(),(sid,'missing original event price source')
  for name,f in [('facts',facts),('CP1_input',inp)]:
   for col in('close','segment_id'):
    assert np.array_equal(signal.loc[dates,col].to_numpy(),f.loc[dates,col].to_numpy()),(sid,name,col,'event coordinate mismatch')
  assert np.array_equal(signal.loc[dates,'segment_id'].to_numpy(),es.segment.to_numpy()),(sid,'event index segment mismatch')
  sec=meta[sid]['sector_id'];assert es.sector_static.eq(sec).all()
  out,q=calculate(signal,industries.get(sec),market)
  if sid in samples:
   for cut in('2023-12-29','2024-09-30','2026-03-31'):
    if cut<str(signal.index.min().date()):continue
    little,_=calculate(signal.loc[:cut],industries[sec].loc[:cut]if industries.get(sec)is not None else None,market.loc[:cut])
    pd.testing.assert_frame_equal(little,out.loc[little.index],check_exact=True)
    prefix.append(dict(sid=sid,cut=cut,exact=True))
  z=out.reindex(dates).copy();z.index=pd.RangeIndex(len(z));es=es.reset_index(drop=True)
  z.insert(0,'date',es.date);z.insert(0,'sid',sid)
  z['segment']=es.segment;z['sector_id_static']=sec;z['industry_static']=meta[sid]['industry'];z['membership_PIT_verified']=False
  z['market20_log']=q['market20_log'].reindex(dates).to_numpy()
  z['event_on_market_calendar']=dates.isin(market.index).to_numpy(dtype=bool)
  z['original_CP_receipt']=True;z['canonical_receipt_id']=es.canonical_receipt_id
  widths=q['channel_width'].reindex(dates).to_numpy()
  miss=[missing_description(row,w,industries.get(sec)is not None)for row,w in zip(z[FEATURES].to_dict('records'),widths)]
  z['missing_features']=[m[0]for m in miss];z['missing_reasons']=[m[1]for m in miss]
  z['missing_feature_count']=z[FEATURES].isna().sum(axis=1)
  for name,cols in GROUPS.items():z[name+'_complete']=z[cols].notna().all(axis=1)
  z['all17_complete']=z[FEATURES].notna().all(axis=1)
  result.append(z);source_signal_rows+=len(signal);event_coordinate_checks+=len(z)
  if(position+1)%100==0 or position+1==len(stocks):
   progress=dict(status='RUNNING',stocks_completed=position+1,stocks_required=len(stocks),events_completed=sum(len(x)for x in result),seconds=time.monotonic()-begun,source_signal_rows=source_signal_rows)
   save('PROGRESS.json',progress);print(json.dumps(progress),flush=True)
  if(position+1)%200==0:pd.concat(result,ignore_index=True).to_parquet(O/'FEATURES.partial.parquet',index=False)
 # Publish feature-only artifacts only after exact mother and coordinate checks.
 full=pd.concat(result,ignore_index=True).sort_values(['sid','date']).reset_index(drop=True)
 assert len(full)==99031 and not full.duplicated(['sid','date']).any()
 assert full.event_on_market_calendar.notna().all()and full.event_on_market_calendar.dtype==bool
 full.to_parquet(O/'FEATURES.parquet',index=False)
 full.to_csv(O/'FEATURES.csv',index=False)
 coverage=[]
 for group,g in full.groupby(full.date.str[:4],sort=True):
  coverage.append(dict(year=group,events=len(g),stocks=int(g.sid.nunique()),
   group_complete={k:int(g[k+'_complete'].sum())for k in GROUPS},all17_complete=int(g.all17_complete.sum()),
   feature_known={k:int(g[k].notna().sum())for k in FEATURES}))
 save('FEATURE_SCHEMA.json',dict(features=FEATURES,groups=GROUPS,keys=['sid','date'],units='Natural log units; EMA slopes per common session; proportions/position dimensionless.',
     metadata_not_predictors=[c for c in full.columns if c not in FEATURES+['sid','date']],event_index_used_columns=EVENT_COLUMNS,
     no_future_event_index_columns_read=True,no_labels_read=True,amount_validity='observed, nonsynthetic, source_invalid false, finite positive CNY amount; not volume_eligible proxy.',
     EMA='Valid stock-price update sequence seeded per source segment; both slopes gated by last65 complete CSI sessions in same segment.',
     frozen_design_SHA256_at_start=SOURCES[str((ROOT/'FROZEN_DESIGN.txt').resolve())]))
 save('FEATURE_COVERAGE.json',dict(complete=True,events=len(full),stocks_with_original_CP_events=len(stocks),static_universe_stocks=len(sm),source_signal_rows=source_signal_rows,
     event_coordinate_checks=event_coordinate_checks,original_CP_mother_exact=True,event_price_segment_exact_signal_facts_CPinput=True,
     missing_industry_indices=industry_errors,events_outside_market_calendar=int((~full.event_on_market_calendar).sum()),coverage_by_year=coverage,all17_complete=int(full.all17_complete.sum()),
     missing_features={k:int(full[k].isna().sum())for k in FEATURES},physical_prefix_checks=prefix,
     new_accounts=0,new_CP_FSM=0,new_labels=0,fitted_parameters=0,seconds=time.monotonic()-begun,limit_seconds=LIMIT))
 save('FEATURE_SOURCE_SHA256.json',SOURCES)
 save('PROGRESS.json',dict(status='COMPLETE',events=len(full),stocks_completed=len(stocks),seconds=time.monotonic()-begun))
 paths=[O/'FEATURES.parquet',O/'FEATURES.csv',O/'FEATURE_SCHEMA.json',O/'FEATURE_COVERAGE.json',O/'FEATURE_SOURCE_SHA256.json',Path(__file__),ROOT/'FROZEN_DESIGN.txt']
 save('FEATURE_OUTPUT_SHA256.json',{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths})
 print(json.dumps(dict(complete=True,events=len(full),all17_complete=int(full.all17_complete.sum()),seconds=time.monotonic()-begun)),flush=True)

if __name__=='__main__':main()
