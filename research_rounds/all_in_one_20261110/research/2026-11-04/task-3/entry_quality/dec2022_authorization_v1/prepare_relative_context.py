"""Original-price relative context, prepared for all possible native stock queries."""
from pathlib import Path
import hashlib,json,pickle,gzip,sys,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent/'trend_exit_controls_v1';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');P=O/'relative_context';P.mkdir(exist_ok=True)
sys.path.insert(0,str(R));from indicator_provider import IndicatorProvider
SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p)]=sha(p);return json.loads(p.read_text())
def main():
 start=time.monotonic();sm=read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json');im={x['series']:x for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')};meta=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
 ip=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USZI399300.csv');ck=read(ip.parent.parent/'checkpoints/USZI399300.json');assert sha(ip)==ck['canonical_sha256'];SRC[str(ip)]=sha(ip);idx=pd.read_csv(ip,index_col=0,parse_dates=True);assert idx.index.is_unique and idx.index.is_monotonic_increasing
 anchor=pd.Series(idx.index,index=idx.index).shift(20);mret=idx.close/idx.close.shift(20)-1
 provider=IndicatorProvider();SRC[str(R/'indicators/MANIFEST.json')]=provider.manifest_sha256;SRC[str(R/'indicator_provider.py')]=sha(R/'indicator_provider.py')
 inds={};out={};counts={}
 for j,m in enumerate(sm):
  sid=m['symbol'];sector=meta[sid]['sector_id'];fp=Path(m['refs']['facts']);assert sha(fp)==m['output_sha256'][str(fp)];SRC[str(fp)]=sha(fp);f=pd.read_parquet(fp,columns=['close','segment_id']);f['close']=f.close.astype(float)
  if sector not in inds:
   r=im[sector];gp=Path(next(q for q in r['source_sha256'] if '/industry-facts/' in q));assert sha(gp)==r['source_sha256'][str(gp)];SRC[str(gp)]=sha(gp);g=pd.read_parquet(gp,columns=['close','segment_id']);g['close']=g.close.astype(float);inds[sector]=g
  g=inds[sector];old=provider.data[sid];days=old['days'];dates=pd.DatetimeIndex(days.astype('datetime64[D]'));assert dates.is_unique and dates.is_monotonic_increasing
  aa=pd.DatetimeIndex(anchor.reindex(dates).to_numpy());s0=f.reindex(aa);s1=f.reindex(dates);i0=g.reindex(aa);i1=g.reindex(dates)
  sc=s1.close.to_numpy(float);sp=s0.close.to_numpy(float);ic=i1.close.to_numpy(float);iprev=i0.close.to_numpy(float);mr=mret.reindex(dates).to_numpy(float)
  good=(old['observed_valid']&np.isfinite(sc)&np.isfinite(sp)&np.isfinite(ic)&np.isfinite(iprev)&np.isfinite(mr)&(sc>0)&(sp>0)&(ic>0)&(iprev>0)&(s1.segment_id.to_numpy(float)==s0.segment_id.to_numpy(float))&(i1.segment_id.to_numpy(float)==i0.segment_id.to_numpy(float)))
  sr=np.full(len(dates),np.nan);ir=sr.copy();rs=sr.copy();sr[good]=sc[good]/sp[good]-1;ir[good]=ic[good]/iprev[good]-1;rs[good]=sr[good]-np.maximum(ir[good],mr[good])
  assert np.allclose(sc,old['values'][:,0],equal_nan=True,rtol=1e-12,atol=1e-12)
  out[sid]=dict(days=days,anchor_days=aa.to_numpy('datetime64[D]').astype(np.int32),close=sc,EMA20=old['values'][:,1],RS20=rs,stock_return20=sr,industry_return20=ir,market_return20=mr,source_segment=s1.segment_id.to_numpy(float),sector=sector,ready_R=good,ready_P=old['observed_valid']&np.isfinite(old['values'][:,1]))
  counts[sid]=dict(rows=len(days),ready_R=int(good.sum()),ready_P=int(out[sid]['ready_P'].sum()),ready_joint=int((good&out[sid]['ready_P']).sum()),double_weak=int((good&out[sid]['ready_P']&(rs<=0)&(sc<out[sid]['EMA20'])).sum()))
  if (j+1)%400==0:print('RELATIVE_CONTEXT',j+1,flush=True)
 target=P/'CONTEXT.pkl.gz'
 with gzip.open(target,'xb',compresslevel=3) as f:pickle.dump(out,f,protocol=5)
 manifest=dict(symbols=len(out),rows=sum(v['rows'] for v in counts.values()),columns=list(next(iter(out.values()))),counts=counts,sources=SRC,data_file=str(target),data_sha256=sha(target),script_sha256=sha(Path(__file__)),diagnostic_freeze_sha256=sha(O/'DIAGNOSTIC_FREEZE.json'),definition='TrueHS300 common t,t-20 calendar endpoints, same-source stock and industry; original valid-price EMA20 reused; UNKNOWN explicit',seconds=time.monotonic()-start,new_accounts=0,new_market_models=0)
 with (P/'MANIFEST.json').open('x') as f:json.dump(manifest,f,ensure_ascii=False,indent=2);f.write('\n')
 print('RELATIVE_CONTEXT_DONE',manifest['symbols'],manifest['rows'],round(manifest['seconds'],2),flush=True)
if __name__=='__main__':main()
