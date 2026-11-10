"""Three frozen static H* snapshots. No account, new model, CP or labels."""
from pathlib import Path
from collections import Counter
import hashlib,json,time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent;ROOT=O.parent
B=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
META=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
MARKET=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018')
DATES=['2024-09-24','2026-01-15','2022-01-24'];SOURCES={}
COLS=['open','high','low','close','volume','amount','segment_id','observed_bar','price_eligible',
      'synthetic_event_bar','source_invalid','amount_unit','raw_open','raw_high','raw_low','raw_close']
RAW=['rs_ind20','rs_ind5','breadth20','share_change'];PCOLS=['p_rs20','p_rs5','p_breadth20','p_share_change']
def bind(p,expected=None):
 p=Path(p).resolve();h=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected is not None:assert h==expected,(str(p),'source SHA mismatch')
 SOURCES[str(p)]=h;return p
def read(p):return json.loads(bind(p).read_text())
def clean(v):
 if v is pd.NA or v is pd.NaT:return None
 if isinstance(v,pd.Timestamp):return str(v.date())
 if isinstance(v,dict):return {str(k):clean(x)for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x)for x in v]
 if hasattr(v,'item'):return clean(v.item())
 if isinstance(v,float)and not np.isfinite(v):return None
 return v
def save(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def pq(p,h,columns):
 f=pd.read_parquet(bind(p,h),columns=columns);f.index=pd.DatetimeIndex(f.index).as_unit('ns')
 assert f.index.is_unique and f.index.is_monotonic_increasing;return f
def yes(s):return s.eq(True).fillna(False).to_numpy(dtype=bool)
def no(s):return s.eq(False).fillna(False).to_numpy(dtype=bool)
def pos(a):return np.isfinite(a)&(a>0)

def stock_row(signal,dates,sid,sec,name):
 w=signal.reindex(dates);v={k:pd.to_numeric(w[k],errors='coerce').to_numpy(float)for k in ['open','high','low','close','volume','amount','segment_id']}
 o,h,l,c,vol,a,seg=[v[k]for k in ['open','high','low','close','volume','amount','segment_id']]
 observed=yes(w.observed_bar);eligible=yes(w.price_eligible);nonsynthetic=no(w.synthetic_event_bar);notinvalid=no(w.source_invalid)
 ohlc=pos(o)&pos(h)&pos(l)&pos(c)&(l<=o)&(l<=c)&(h>=o)&(h>=c)&(h>=l)
 price=observed&eligible&nonsynthetic&notinvalid&ohlc
 currency=w.amount_unit.eq('CNY').fillna(False).to_numpy(dtype=bool)
 amount=observed&nonsynthetic&notinvalid&currency&pos(a)
 full=price&pos(vol)&amount&np.isfinite(seg)
 one_seg=np.isfinite(seg).all()and len(set(seg))==1
 valid25=bool(full.all()and one_seg)
 def same(part):return np.isfinite(seg[part]).all()and len(set(seg[part]))==1
 med=float(np.median(a[3:24]))if amount[3:24].all()and same(slice(3,24))else np.nan
 mean=float(np.mean(a[19:24]))if amount[19:24].all()and same(slice(19,24))else np.nan
 liquid=bool(np.isfinite(med)and med>=20000000 and np.isfinite(mean)and mean>=10000000)
 U=valid25 and liquid
 reasons=[]
 for label,mask in [('missing_or_unobserved25',observed),('price_ineligible25',eligible),('synthetic_or_unknown25',nonsynthetic),
    ('source_invalid_or_unknown25',notinvalid),('nonpositive_or_bad_OHLC25',ohlc),('nonpositive_volume25',pos(vol)),
    ('nonpositive_or_bad_amount25',amount),('segment_unknown25',np.isfinite(seg))]:
  if not mask.all():reasons.append(label)
 if not one_seg:reasons.append('not_single_known_segment25')
 if not np.isfinite(med):reasons.append('prior21median_amount_unknown')
 elif med<20000000:reasons.append('prior21median_amount_below20m')
 if not np.isfinite(mean):reasons.append('prior5mean_amount_unknown')
 elif mean<10000000:reasons.append('prior5mean_amount_below10m')
 sma=float(np.mean(c[5:25]))if price[5:25].all()and same(slice(5,25))else np.nan
 above=bool(c[-1]>sma)if np.isfinite(sma)else None
 return20=float(np.log(c[-1]/c[4]))if price[4:25].all()and same(slice(4,25))else np.nan
 high20=float(np.max(h[4:24]))if price[4:25].all()and same(slice(4,25))else np.nan
 dd=min(0.,float(np.log(c[-1]/high20)))if np.isfinite(high20)else np.nan
 amchange=float(np.log(a[-1]/med))if amount[-1]and np.isfinite(med)and med>0 and same(slice(3,25))else np.nan
 raw=[pd.to_numeric(w[k],errors='coerce').to_numpy(float)[-1]for k in ['raw_open','raw_high','raw_low','raw_close']]
 oneprice=None
 if pos(np.array(raw)).all()and price[-2:].all()and same(slice(23,25)):
  oneprice=bool(raw[0]==raw[1]==raw[2]==raw[3]and np.log(c[-1]/c[-2])>0)
 row=dict(sid=sid,date=str(dates[-1].date()),sector_id_static=sec,industry_static=name,
  segment=seg[-1],source_row_present_T=dates[-1]in signal.index,observed_T=bool(observed[-1]),price_observed_T=bool(price[-1]),
  N25valid=valid25,liquidity_history_pass=liquid,qualified_U_t=U,eligibility_reasons=';'.join(reasons),
  valid25_observations=int(full.sum()),single_segment25=bool(one_seg),prior21median_amount_CNY=med,prior5mean_amount_CNY=mean,
  signal_close_T=c[-1],signal_sma20_T=sma,above_sma20_T=above,stock_return20_log=return20,
  drawdown20_prior_high=dd,amount_change=amchange,one_price_up_T=oneprice,execution_status='UNKNOWN',
  membership_PIT_verified=False,common_window_begin=str(dates[0].date()),share_recent5_begin=str(dates[20].date()),
  share_prior20_end=str(dates[19].date()))
 return row,a.copy()if U else None

def main():
 begun=time.monotonic();bind(__file__);bind(ROOT/'FROZEN_STATIC_DIAGNOSTIC.txt')
 sm=read(B/'STOCK_MANIFEST.json');im=read(B/'INDUSTRY_MANIFEST.json');meta=read(META)
 assert len(sm)==1709 and len(im)==90
 checkpoint=read(MARKET/'checkpoints/USHI1B0300.json')
 market=pd.read_csv(bind(MARKET/'canonical/USHI1B0300.csv',checkpoint['canonical_sha256']),parse_dates=['date']).set_index('date')
 market.index=market.index.as_unit('ns');assert market.index.is_unique and market.index.is_monotonic_increasing
 windows={}
 for day in DATES:
  i=market.index.get_loc(pd.Timestamp(day));windows[day]=market.index[i-24:i+1];assert len(windows[day])==25
 industries={};returns={};Nstatic=Counter(meta[r['symbol']]['sector_id']for r in sm)
 for r in im:
  sec=r['series'];f=pq(r['refs']['CP1_input'],r['output_sha256'][r['refs']['CP1_input']],['close','segment_id']);industries[sec]=f
  for day,dates in windows.items():
   x=f.reindex(dates);c=x.close.to_numpy(float);seg=x.segment_id.to_numpy(float);m=market.loc[dates,'close'].to_numpy(float)
   vals={}
   for h in(5,20):
    part=slice(24-h,25);known=pos(c[part]).all()and pos(m[part]).all()and np.isfinite(seg[part]).all()and len(set(seg[part]))==1
    vals['rs_ind'+str(h)]=float(np.log(c[-1]/c[24-h])-np.log(m[-1]/m[24-h]))if known else np.nan
    vals['industry_return'+str(h)+'_log']=float(np.log(c[-1]/c[24-h]))if known else np.nan
    vals['market_return'+str(h)+'_log']=float(np.log(m[-1]/m[24-h]))if known else np.nan
   returns[day,sec]=vals
 amounts={d:{sec:np.zeros(25)for sec in Nstatic}for d in DATES};pool={d:np.zeros(25)for d in DATES}
 rows=[];prefix=[];coordinate_checks=0;coordinate_missing=[]
 samples={0,len(sm)//4,len(sm)//2,3*len(sm)//4,len(sm)-1}
 for position,r in enumerate(sm):
  sid=r['symbol'];sec=meta[sid]['sector_id'];name=meta[sid]['industry']
  paths=[p for p in r['source_sha256']if '/prepared'in p and p.endswith('/signal.parquet')];assert len(paths)==1
  signal=pq(paths[0],r['source_sha256'][paths[0]],COLS)
  facts=pq(r['refs']['facts'],r['output_sha256'][r['refs']['facts']],['close','segment_id'])
  cpinput=pq(r['refs']['CP1_input'],r['output_sha256'][r['refs']['CP1_input']],['close','segment_id'])
  for day,dates in windows.items():
   row,a=stock_row(signal,dates,sid,sec,name)
   row['RS_stock20']=row['stock_return20_log']-returns[day,sec]['industry_return20_log']
   row['source_close_segment_verified']=False
   d=dates[-1]
   if d in signal.index and d in facts.index and d in cpinput.index:
    for f in(facts,cpinput):
     for col in('close','segment_id'):assert signal.loc[d,col]==f.loc[d,col],(sid,day,col,'original coordinate mismatch')
    row['source_close_segment_verified']=True;coordinate_checks+=1
   elif row['source_row_present_T']:coordinate_missing.append(dict(sid=sid,date=day))
   rows.append(row)
   if a is not None:amounts[day][sec]+=a;pool[day]+=a
   if position in samples:
    small,_=stock_row(signal.loc[:day],dates,sid,sec,name)
    compare={k:v for k,v in row.items()if k not in('RS_stock20','source_close_segment_verified')}
    pd.testing.assert_series_equal(pd.Series(compare),pd.Series(small),check_exact=True)
    prefix.append(dict(sid=sid,date=day,exact=True))
  if(position+1)%200==0:
   status=dict(stocks_completed=position+1,stocks_required=len(sm),stockdate_rows=len(rows),seconds=time.monotonic()-begun)
   save('PROGRESS.json',status);print(json.dumps(status),flush=True)
 stocks=pd.DataFrame(rows);assert len(stocks)==5127 and not stocks.duplicated(['sid','date']).any()
 stocks.to_parquet(O/'U_T_STOCK_ELIGIBILITY.parquet',index=False);stocks.to_csv(O/'U_T_STOCK_ELIGIBILITY.csv',index=False)
 panels=[];closures=[];tops={}
 for day in DATES:
  subset=stocks.loc[stocks.date.eq(day)];nr=float(np.sum(pool[day][20:25]));nb=float(np.sum(pool[day][0:20]));daily=np.sum(np.stack(list(amounts[day].values())),axis=0)
  assert np.allclose(daily,pool[day],rtol=1e-12,atol=1e-5)
  closures.append(dict(date=day,U_t=int(subset.qualified_U_t.sum()),N25valid=int(subset.N25valid.sum()),pool_recent5_CNY=nr,pool_prior20_CNY=nb,max_daily_industrysum_pool_gap=float(np.max(np.abs(daily-pool[day])))))
  for sec in sorted(Nstatic):
   q=subset.loc[subset.sector_id_static.eq(sec)];u=q.loc[q.qualified_U_t];n=len(u);a=amounts[day][sec]
   n5=float(np.sum(a[20:25]))if n else np.nan;n20=float(np.sum(a[0:20]))if n else np.nan
   s5=n5/nr if n and nr>0 else np.nan;s20=n20/nb if n and nb>0 else np.nan
   b=float(u.above_sma20_T.eq(True).sum()/n)if n else np.nan
   change=s5/s20-1 if n and np.isfinite(s20)and s20>0 else np.nan
   panels.append(dict(date=day,sector_id_static=sec,industry_static=q.industry_static.iloc[0],**returns[day,sec],
      breadth20=b,share5=s5,share20=s20,share_change=change,Nstatic=Nstatic[sec],Nobserved=int(q.price_observed_T.sum()),
      N25valid=int(q.N25valid.sum()),Nliquid=n,N_U_pool=int(subset.qualified_U_t.sum()),industry_recent5_CNY=n5,industry_prior20_CNY=n20,
      pool_recent5_CNY=nr,pool_prior20_CNY=nb,Hstar_formal_PIT=np.nan,formal_PIT_known=False,
      formal_unknown_reason='historical_full_industry_membership_and_full_market_pool_not_verified',
      static_proxy=True,common_window_begin=str(windows[day][0].date()),share_recent5_begin=str(windows[day][20].date()),share_prior20_end=str(windows[day][19].date())))
  panel=pd.DataFrame([p for p in panels if p['date']==day]);known=panel[RAW].notna().all(axis=1);N=int(known.sum())
  for raw,pcol in zip(RAW,PCOLS):panel[pcol]=np.nan;panel.loc[known,pcol]=(panel.loc[known,raw].rank(method='average')-.5)/N if N else np.nan
  panel['Hstar_static']=panel[PCOLS].mean(axis=1).where(known)
  panel['N_industries_common_known']=N;panel['rank_Hstar_static']=panel.Hstar_static.rank(method='min',ascending=False)
  panel['Hstar_missing_features']=panel[RAW].apply(lambda r:'|'.join(r.index[r.isna()]),axis=1)
  panel=panel.sort_values(['Hstar_static','sector_id_static'],ascending=[False,True],na_position='last').reset_index(drop=True)
  panel['display_order']=np.arange(1,len(panel)+1);panel.to_csv(O/(day+'_HSTAR_STATIC.csv'),index=False)
  top=panel.loc[panel.Hstar_static.notna()].head(10).to_dict('records');tops[day]=top
  print(json.dumps(clean(dict(date=day,N_industries_common_known=N,U_t=int(subset.qualified_U_t.sum()),top10=[{k:r[k]for k in ['rank_Hstar_static','industry_static','Hstar_static','rs_ind20','rs_ind5','breadth20','share_change','Nliquid']}for r in top])),ensure_ascii=False),flush=True)
  save(day+'_TOP10.json',top)
 allpanels=pd.concat([pd.read_csv(O/(d+'_HSTAR_STATIC.csv'))for d in DATES],ignore_index=True)
 allpanels.to_parquet(O/'HSTAR_STATIC_PANEL.parquet',index=False);allpanels.to_csv(O/'HSTAR_STATIC_PANEL.csv',index=False)
 save('TOP10_ALL_DATES.json',tops)
 save('SUMMARY.json',dict(complete=True,dates=DATES,static_stocks=1709,stockdate_rows=5127,industry_rows=len(allpanels),
   closures=closures,source_coordinate_checks=coordinate_checks,source_coordinate_missing=coordinate_missing,
   physical_stock_prefix_checks=prefix,raw_amount_source='Only same U_t original stock CNY amount sums. No URFI amount or CSI300 amount used.',
   Nobserved_definition='Current observed, priceeligible, nonsynthetic, noninvalid positive internally consistent OHLC; independent of volume/amount.',
   N25valid_definition='All25 common sessions positive OHLC/volume/CNYamount and observed/eligible/nonsynthetic/noninvalid, single known segment.',
   Nliquid_definition='N25valid and prior21median>=20m and prior5mean>=10m; both exclude T.',
   shared_percentile='Same four-raw-known industry set each day; p=(average_rank-.5)/N; unknown unranked; Hstar=.25sum p.',
   full_formal_PIT_unknown=True,new_accounts=0,new_CP_FSM=0,new_backtests=0,seconds=time.monotonic()-begun))
 save('SOURCE_SHA256.json',SOURCES)
 paths=[O/'U_T_STOCK_ELIGIBILITY.parquet',O/'U_T_STOCK_ELIGIBILITY.csv',O/'HSTAR_STATIC_PANEL.parquet',O/'HSTAR_STATIC_PANEL.csv',O/'SUMMARY.json',O/'SOURCE_SHA256.json',O/'TOP10_ALL_DATES.json',Path(__file__),ROOT/'FROZEN_STATIC_DIAGNOSTIC.txt']
 save('OUTPUT_SHA256.json',{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths})
 save('PROGRESS.json',dict(status='COMPLETE',stockdate_rows=5127,industry_rows=270,seconds=time.monotonic()-begun))

if __name__=='__main__':main()
