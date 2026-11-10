"""Full new10/40 arrays independently reconstructed; old20 reused byte-values."""
from pathlib import Path
from collections import Counter
import json,gzip,pickle,hashlib,sys,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;F=O.parent;D=F.parent;T=D.parent/'trend_exit_controls_v1';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');C=Counter();start=time.monotonic()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def load(p):
 with gzip.open(p,'rb') as f:return pickle.load(f)
def di(x):return np.asarray(x).astype('datetime64[D]').astype('int64')
def exact(f,days,col):
 fd=di(f.index);ii=np.searchsorted(fd,days);ok=ii<len(fd);ok[ok]&=fd[ii[ok]]==days[ok];out=np.full(len(days),np.nan);out[ok]=f[col].to_numpy(float)[ii[ok]];return out
def eq(a,b):assert np.allclose(a,b,equal_nan=True,rtol=1e-12,atol=1e-11)
manifest=read(F/'contexts/MANIFEST.json');assert sha(manifest['data_file'])==manifest['data_sha256'];data=load(manifest['data_file']);oldm=read(D/'relative_context/MANIFEST.json');old=load(oldm['data_file']);im=read(T/'indicators/MANIFEST.json');ind=load(im['data_file']);freeze=read(F/'ROBUSTNESS_FREEZE.json');assert sha(F/'ROBUSTNESS_FREEZE.json')=='c1daaeb7a13f2835ba9e727a0fdce2ea8c7fe4b37ad32e5cd674094885c58713'
for p,h in manifest['sources'].items():assert sha(p)==h,(p,h);C['source_SHA']+=1
assert manifest['one_factor_variants_only']==freeze['parameter_variants'];assert manifest['relative_windows']==manifest['EMA_spans']==[10,20,40]
sm={r['symbol']:r for r in read(W/'STOCK_MANIFEST.json')};ims={r['series']:r for r in read(W/'INDUSTRY_MANIFEST.json')};meta=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json');market=pd.read_csv('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USZI399300.csv',index_col=0,parse_dates=True);md=di(market.index);mc=market.close.to_numpy(float);assert np.all(np.isfinite(mc)&(mc>0));industry={};maxdiff={10:0.,40:0.};warm=0
for sid,z in data.items():
 m=sm[sid];f=pd.read_parquet(m['refs']['facts'],columns=['close','segment_id']);rp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));raw=pd.read_parquet(rp,columns=['close','segment_id','price_eligible','observed_bar','source_invalid','synthetic_event_bar']).reindex(f.index);fc=f.close.to_numpy(float);fs=f.segment_id.to_numpy(float)
 valid=raw.price_eligible.eq(True).to_numpy()&raw.observed_bar.eq(True).to_numpy()&raw.source_invalid.eq(False).to_numpy()&raw.synthetic_event_bar.eq(False).to_numpy()&np.isfinite(fc)&(fc>0)&(raw.segment_id.to_numpy(float)==fs)&np.isclose(raw.close.to_numpy(float),fc,rtol=1e-10,atol=1e-10)
 keep=(f.index>=pd.Timestamp('2022-01-01'))&(f.index<=pd.Timestamp('2026-06-30'));days=di(f.index)[keep];eq(days,z['days']);eq(valid[keep],z['observed_valid']);eq(z['observed_valid'],ind[sid]['observed_valid']);sector=meta[sid]['sector_id'];assert sector==z['sector'];warm+=len(f)
 for k,ok in [('close','close'),('source_segment','source_segment'),('RS20','RS20'),('EMA20','EMA20'),('stock_return20','stock_return20'),('industry_return20','industry_return20'),('market_return20','market_return20'),('anchor_days20','anchor_days'),('ready_R20','ready_R'),('ready_P20','ready_P')]:assert np.array_equal(z[k],old[sid][ok],equal_nan=True);C['old20_array_exact']+=1
 if sector not in industry:industry[sector]=pd.read_parquet(next(p for p in ims[sector]['source_sha256'] if '/industry-facts/' in p),columns=['close','segment_id'])
 g=industry[sector];mi=np.searchsorted(md,days);marketexact=mi<len(md);marketexact[marketexact]&=md[mi[marketexact]]==days[marketexact]
 for n in [10,40]:
  known=marketexact&(mi>=n);anchor=np.full(len(days),np.iinfo('int32').min,dtype='int64');anchor[known]=md[mi[known]-n];sr=np.full(len(days),np.nan);ir=sr.copy();mr=sr.copy();rs=sr.copy();mr[known]=mc[mi[known]]/mc[mi[known]-n]-1;sc=exact(f,days,'close');sp=exact(f,anchor,'close');ic=exact(g,days,'close');ip=exact(g,anchor,'close');good=valid[keep]&known&np.isfinite(sc)&np.isfinite(sp)&np.isfinite(ic)&np.isfinite(ip)&(sc>0)&(sp>0)&(ic>0)&(ip>0)&(exact(f,days,'segment_id')==exact(f,anchor,'segment_id'))&(exact(g,days,'segment_id')==exact(g,anchor,'segment_id'));sr[good]=sc[good]/sp[good]-1;ir[good]=ic[good]/ip[good]-1;rs[good]=sr[good]-np.maximum(ir[good],mr[good])
  for name,v in [('RS',rs),('stock_return',sr),('industry_return',ir),('market_return',mr),('anchor_days',anchor),('ready_R',good)]:eq(z[name+str(n)],v);C['new_R_arrays']+=1
  line=np.full(len(f),np.nan);state=None;count=0;prev=None;alpha=2/(n+1)
  for j,(price,segment,isvalid) in enumerate(zip(fc,fs,valid)):
   if j==0 or segment!=prev:state=None;count=0
   prev=segment
   if not isvalid:continue
   state=price if state is None else state*(1-alpha)+price*alpha;count+=1
   if count>=n:line[j]=state
  expected=line[keep];eq(z['EMA'+str(n)],expected);eq(z['ready_P'+str(n)],valid[keep]&np.isfinite(expected));finite=np.isfinite(expected);maxdiff[n]=max(maxdiff[n],float(np.max(np.abs(expected[finite]-z['EMA'+str(n)][finite]))) if finite.any() else 0.)
  assert manifest['counts'][sid]['R'][str(n)]==int(good.sum()) and manifest['counts'][sid]['P'][str(n)]==int((valid[keep]&np.isfinite(expected)).sum());C['new_EMA_arrays']+=1;C['new_R_ready_'+str(n)]+=int(good.sum());C['new_EMA_ready_'+str(n)]+=int((valid[keep]&np.isfinite(expected)).sum())
 C['symbols']+=1;C['rows']+=len(days)
 if C['symbols']%400==0:print('INDEPENDENT_VARIANTS',C['symbols'],flush=True)
assert C['symbols']==manifest['symbols']==1709 and C['rows']==manifest['rows']==1731880
sys.path.insert(0,str(F));from variant_provider import VariantProvider
providers={};params=[(10,20),(40,20),(20,10),(20,40),(20,20)]
for nr,ne in params:
 q=VariantProvider.__new__(VariantProvider);q.relative=nr;q.ema=ne;q.data=data;providers[nr,ne]=q
 for sid in sorted(data)[::79]:
  z=data[sid]
  for j in range(0,len(z['days']),97):
   day=str(np.datetime64(int(z['days'][j]),'D'));r=q.at(sid,day);assert r['RS_window']==nr and r['EMA_span']==ne;assert r['ready_R']==bool(z['ready_R'+str(nr)][j]) and r['ready_P']==bool(z['ready_P'+str(ne)][j]);assert r['RS20']==r['RS_value'] and r['EMA20']==r['EMA_value'];assert r['source_max_day']==day
   if r['ready_R']:eq(r['RS20'],z['RS'+str(nr)][j]);assert r['anchor_day']<day
   if r['ready_P']:eq(r['EMA20'],z['EMA'+str(ne)][j])
   C['provider_queries']+=1
 assert q.at('MISSING','2022-01-04')['unknown_reason']=='symbol_missing';assert not q.at(next(iter(data)),'2021-01-01')['ready_R'];C['provider_missing_cases']+=2
assert len({hashlib.sha256((sha(F/'contexts/MANIFEST.json')+'|RS'+str(nr)+'|EMA'+str(ne)).encode()).hexdigest() for nr,ne in params})==5
result=dict(status='PASS_ALL_NEW_PARAMETER_ARRAYS_PROVIDER_WITH_LIMITS',checks=dict(C),warm_source_rows=warm,independent_EMA_max_abs_rounding_difference=maxdiff,source_sha256={str(F/'ROBUSTNESS_FREEZE.json'):sha(F/'ROBUSTNESS_FREEZE.json'),str(F/'contexts/MANIFEST.json'):sha(F/'contexts/MANIFEST.json'),str(F/'prepare_context_variants.py'):sha(F/'prepare_context_variants.py'),str(F/'variant_provider.py'):sha(F/'variant_provider.py')},script_sha256=sha(__file__),seconds=time.monotonic()-start,new_accounts=0,limits=['All10/40 relative arrays and independent one-pass fullwarm EMA recurrences checked; old20 arrays exact-reused, no sealed recomputation.','Provider deterministic sample of retained symbol-days; source arrays checked in full. Exact missing lookup/mode readiness checked.','Original source snapshot/PIT and price-coordinate caveats remain; account implementation/physical prefix gate separate.'])
(O/'VARIANT_CONTEXT_FULL_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
