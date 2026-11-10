"""Limited, frozen one-factor perturbations; no account or market-model changes."""
from pathlib import Path
import gzip,hashlib,json,pickle,sys,time
import numpy as np
import pandas as pd

F=Path(__file__).resolve().parent;D=F.parent;T=D.parent/'trend_exit_controls_v1'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
sys.path.insert(0,str(D));from context_provider import ContextProvider
sys.path.insert(0,str(T));from indicator_provider import IndicatorProvider
SOURCES={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p,expected=None):
 p=Path(p);h=sha(p)
 if expected is not None:assert h==expected,(p,h,expected)
 SOURCES[str(p)]=h;return p
def read(p):return json.loads(bind(p).read_text())

def main():
 started=time.monotonic();freeze=read(F/'ROBUSTNESS_FREEZE.json');assert len(freeze['parameter_variants'])==4
 target=F/'contexts';assert not target.exists();target.mkdir()
 sm=read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
 im={x['series']:x for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
 meta=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
 ip=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USZI399300.csv')
 ck=read(ip.parent.parent/'checkpoints/USZI399300.json');bind(ip,ck['canonical_sha256'])
 market=pd.read_csv(ip,index_col=0,parse_dates=True);assert market.index.is_unique and market.index.is_monotonic_increasing
 anchors={n:pd.Series(market.index,index=market.index).shift(n) for n in (10,40)}
 mr={n:market.close/market.close.shift(n)-1 for n in (10,40)}
 original=ContextProvider();indicators=IndicatorProvider()
 bind(D/'relative_context/MANIFEST.json');bind(T/'indicators/MANIFEST.json')
 bind(D/'context_provider.py');bind(T/'indicator_provider.py');bind(Path(__file__))
 output={};counts={};industry={};old20_rows=0
 for ix,m in enumerate(sm):
  sid=m['symbol'];sector=meta[sid]['sector_id'];p=Path(m['refs']['facts']);bind(p,m['output_sha256'][str(p)])
  f=pd.read_parquet(p,columns=['close','segment_id']);f['close']=f.close.astype(float)
  rawp=Path(next(q for q in m['source_sha256'] if q.endswith('/signal.parquet')));bind(rawp,m['source_sha256'][str(rawp)])
  raw=pd.read_parquet(rawp,columns=['close','segment_id','price_eligible','observed_bar','source_invalid','synthetic_event_bar']).reindex(f.index)
  raw['close']=raw.close.astype(float)
  valid=(raw.price_eligible.eq(True)&raw.observed_bar.eq(True)&raw.source_invalid.eq(False)&raw.synthetic_event_bar.eq(False)&np.isfinite(f.close)&f.close.gt(0)&raw.segment_id.eq(f.segment_id)&np.isclose(raw.close,f.close,rtol=1e-10,atol=1e-10))
  keep=(f.index>=pd.Timestamp('2022-01-01'))&(f.index<=pd.Timestamp('2026-06-30'));dates=f.index[keep]
  old=original.data[sid];oldi=indicators.data[sid]
  days=f.index.to_numpy('datetime64[D]').astype(np.int32)[keep]
  assert np.array_equal(days,old['days']) and np.array_equal(valid.to_numpy(bool)[keep],oldi['observed_valid'])
  assert np.allclose(f.close.to_numpy(float)[keep],old['close'],equal_nan=True,rtol=1e-12,atol=1e-12)
  z=dict(days=days,close=old['close'],source_segment=old['source_segment'],sector=sector,observed_valid=oldi['observed_valid'])
  for name in ('RS20','EMA20','stock_return20','industry_return20','market_return20'):
   z[name]=old[name]
  z['anchor_days20']=old['anchor_days'];z['ready_R20']=old['ready_R'];z['ready_P20']=old['ready_P']
  if sector not in industry:
   ir=im[sector];gp=Path(next(q for q in ir['source_sha256'] if '/industry-facts/' in q));bind(gp,ir['source_sha256'][str(gp)])
   g=pd.read_parquet(gp,columns=['close','segment_id']);g['close']=g.close.astype(float);industry[sector]=g
  g=industry[sector]
  for n in (10,40):
   aa=pd.DatetimeIndex(anchors[n].reindex(dates).to_numpy());s0=f.reindex(aa);s1=f.reindex(dates);g0=g.reindex(aa);g1=g.reindex(dates)
   sc=s1.close.to_numpy(float);sp=s0.close.to_numpy(float);ic=g1.close.to_numpy(float);iprev=g0.close.to_numpy(float);market_return=mr[n].reindex(dates).to_numpy(float)
   good=(z['observed_valid']&np.isfinite(sc)&np.isfinite(sp)&np.isfinite(ic)&np.isfinite(iprev)&np.isfinite(market_return)&(sc>0)&(sp>0)&(ic>0)&(iprev>0)&(s1.segment_id.to_numpy(float)==s0.segment_id.to_numpy(float))&(g1.segment_id.to_numpy(float)==g0.segment_id.to_numpy(float)))
   sr=np.full(len(dates),np.nan);ir=sr.copy();rs=sr.copy();sr[good]=sc[good]/sp[good]-1;ir[good]=ic[good]/iprev[good]-1;rs[good]=sr[good]-np.maximum(ir[good],market_return[good])
   z['RS'+str(n)]=rs;z['stock_return'+str(n)]=sr;z['industry_return'+str(n)]=ir;z['market_return'+str(n)]=market_return;z['anchor_days'+str(n)]=aa.to_numpy('datetime64[D]').astype(np.int32);z['ready_R'+str(n)]=good
   line=np.full(len(f),np.nan);runs=f.segment_id.ne(f.segment_id.shift()).cumsum()
   for _,rr in f.groupby(runs,sort=False):
    jj=f.index.get_indexer(rr.index[valid.loc[rr.index]])
    if len(jj):line[jj]=f.close.iloc[jj].ewm(span=n,adjust=False,min_periods=n).mean().to_numpy(float)
   z['EMA'+str(n)]=line[keep];z['ready_P'+str(n)]=z['observed_valid']&np.isfinite(z['EMA'+str(n)])
  output[sid]=z;old20_rows+=len(days)
  counts[sid]={'rows':len(days),'R':{str(n):int(z['ready_R'+str(n)].sum()) for n in (10,20,40)},'P':{str(n):int(z['ready_P'+str(n)].sum()) for n in (10,20,40)}}
  if (ix+1)%400==0:print('ROBUST_CONTEXT',ix+1,flush=True)
 data=target/'CONTEXT_VARIANTS.pkl.gz'
 with gzip.open(data,'xb',compresslevel=3) as f:pickle.dump(output,f,protocol=5)
 manifest={'symbols':len(output),'rows':old20_rows,'data_file':str(data),'data_sha256':sha(data),'sources':SOURCES,'counts':counts,'relative_windows':[10,20,40],'EMA_spans':[10,20,40],'original20_reused_exact':True,'one_factor_variants_only':freeze['parameter_variants'],'legacy_adapter_slots':'RS20/EMA20 are compatibility slots at query time; actual values always accompanied by RS_window/EMA_span and RS_value/EMA_value. No provider is relabelled as original20 in provenance.','seconds':time.monotonic()-started,'new_accounts':0}
 with (target/'MANIFEST.json').open('x') as f:json.dump(manifest,f,ensure_ascii=False,indent=2);f.write('\n')
 print('ROBUST_CONTEXT_COMPLETE',len(output),old20_rows,round(manifest['seconds'],2),flush=True)
if __name__=='__main__':main()
