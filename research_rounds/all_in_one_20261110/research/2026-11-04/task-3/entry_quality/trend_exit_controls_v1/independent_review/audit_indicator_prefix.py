"""Small production-formula AST extraction versus independent iterative oracle."""
from pathlib import Path
from decimal import Decimal
from collections import Counter
import ast,json,hashlib,gzip,pickle,importlib.util,tempfile,math
import numpy as np
import pandas as pd
P=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;C=Counter();S={}
for name in ['PROTOCOL.txt','prepare_indicators.py','indicator_provider.py']:S[name]=hashlib.sha256((P/name).read_bytes()).hexdigest()
tree=ast.parse((P/'prepare_indicators.py').read_text());main=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='main');outer=next(x for x in main.body if isinstance(x,ast.For));body=outer.body
start=next(i for i,x in enumerate(body) if isinstance(x,ast.Assign) and isinstance(x.targets[0],ast.Subscript) and ast.unparse(x.targets[0])=="f['close']")
end=next(i for i,x in enumerate(body) if isinstance(x,ast.Assign) and isinstance(x.targets[0],ast.Name) and x.targets[0].id=='keep')
formula=compile(ast.fix_missing_locations(ast.Module(body=body[start:end],type_ignores=[])),'production_formula_slice','exec')
def actual(f,raw):
 d=dict(f=f.copy(),raw=raw.copy(),np=np,pd=pd);exec(formula,d);return d['vals'],d['nobs'],d['ok'].to_numpy(bool)
def oracle(f,raw):
 vals=np.full((len(f),5),np.nan);counts=np.zeros(len(f),dtype=np.uint32);valid=np.zeros(len(f),bool);prices=[];lastseg=None;ema={20:None,60:None}
 for j,(day,row) in enumerate(f.iterrows()):
  rr=raw.loc[day];price=float(row.close);vals[j,0]=price;seg=row.segment_id
  if j==0 or pd.isna(seg) or pd.isna(lastseg) or seg!=lastseg:prices=[];ema={20:None,60:None}
  lastseg=seg
  good=all([rr.price_eligible==True,rr.observed_bar==True,rr.source_invalid==False,rr.synthetic_event_bar==False,math.isfinite(price),price>0,not pd.isna(seg),rr.segment_id==seg,math.isclose(float(rr.close),price,rel_tol=1e-10,abs_tol=1e-10)])
  valid[j]=good
  if not good:continue
  prices.append(price);counts[j]=len(prices)
  for col,n in [(1,20),(2,60)]:
   alpha=2/(n+1);ema[n]=price if ema[n] is None else alpha*price+(1-alpha)*ema[n]
   if len(prices)>=n:vals[j,col]=ema[n]
  if len(prices)>=20:
   last=prices[-20:];mean=sum(last)/20;std=math.sqrt(sum((p-mean)**2 for p in last)/20);vals[j,3:]=[mean,mean-2*std]
 return vals,counts,valid
def same(a,b,label):
 for x,y in zip(a,b):assert np.allclose(x,y,equal_nan=True,rtol=1e-10,atol=1e-10),(label,x,y)
 C[label]+=1
def base(n=145):
 ix=pd.date_range('2022-01-01',periods=n);v=100+np.arange(n)*.1+5*np.sin(np.arange(n)/3);f=pd.DataFrame(dict(close=v,segment_id=np.zeros(n)),index=ix);raw=f.copy();raw['price_eligible']=True;raw['observed_bar']=True;raw['source_invalid']=False;raw['synthetic_event_bar']=False;return f,raw
cases=[]
cases.append(('ordinary',*base()));f,r=base();f.loc[f.index[70:],'segment_id']=1;r.segment_id=f.segment_id;cases.append(('source_reset',f,r))
f,r=base();r.loc[r.index[[5,19,60,61,90]],'observed_bar']=False;cases.append(('missing_observed_skip',f,r))
f,r=base();r.loc[r.index[[4,21]],'source_invalid']=True;r.loc[r.index[[6,22]],'synthetic_event_bar']=True;r.loc[r.index[[7,23]],'price_eligible']=False;cases.append(('invalid_flags',f,r))
f,r=base();f.loc[f.index[20],'close']=np.nan;r.loc[r.index[20],'close']=np.nan;f.loc[f.index[21],'close']=-1;r.loc[r.index[21],'close']=-1;r.loc[r.index[22],'close']=999;r.loc[r.index[23],'segment_id']=7;cases.append(('bad_price_domain',f,r))
f,r=base();f.loc[f.index[55:65],'segment_id']=np.nan;r.segment_id=f.segment_id;cases.append(('unknown_segment',f,r))
f,r=base(80);f.close=f.close.map(lambda x:Decimal(str(x)));r.close=r.close.map(lambda x:Decimal(str(x)));cases.append(('Decimal_input',f,r))
cases.append(('empty',*base(0)));f,r=base(80);f.close=100.;r.close=100.;cases.append(('constant_equal_line',f,r))
for name,f,r in cases:
 full=actual(f,r);same(full,oracle(f,r),'independent_formula_case')
 for length in [0,1,19,20,59,60,70,91,len(f)]:
  if length>len(f):continue
  cut=actual(f.iloc[:length],r.iloc[:length]);same(tuple(v[:length] for v in full),cut,'physical_prefix')
 # Different future input must leave all past outputs unchanged.
 if len(f)>80:
  ff=f.copy();rr=r.copy();ff.loc[ff.index[80:],'close']=1234567.;rr.loc[rr.index[80:],'close']=1234567.
  changed=actual(ff,rr);same(tuple(v[:80] for v in full),tuple(v[:80] for v in changed),'future_mutation_prefix')
spec=importlib.util.spec_from_file_location('provider_audited',P/'indicator_provider.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
with tempfile.TemporaryDirectory(dir=O) as td:
 root=Path(td);data={}
 for name,f,r in cases:
  v,n,ok=actual(f,r);data[name]=dict(days=f.index.to_numpy('datetime64[D]').astype(np.int32),values=v,segments=f.segment_id.to_numpy(float),observed_valid=ok,valid_observations_in_source=n)
 file=root/'data.gz'
 with gzip.open(file,'wb') as z:pickle.dump(data,z)
 (root/'MANIFEST.json').write_text(json.dumps(dict(data_file=str(file),data_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),columns=['causal_close','EMA20','EMA60','BOLL20_MID','BOLL20_LOWER'])))
 provider=module.IndicatorProvider(root)
 for name,f,r in cases:
  v,n,ok=actual(f,r)
  for j,day in enumerate(f.index):
   for col,indicator in enumerate(['EMA20','EMA60','BOLL20_MID','BOLL20_LOWER'],1):
    x=provider.at(name,str(day.date()),indicator);ready=ok[j] and math.isfinite(v[j,col]);assert (x['status']=='READY')==ready
    if ready:assert x['causal_close']==float(f.iloc[j].close) and x['line']==v[j,col] and x['source_max_day']==str(day.date()) and x['source_segment']==float(f.iloc[j].segment_id)
    else:assert x['line'] is None
    C['provider_current_day']+=1
  for day in ['2021-12-31','2027-01-01']:assert provider.at(name,day,'EMA20')['status']=='UNKNOWN';C['provider_no_quote']+=1
 assert provider.at('MISSING','2022-01-01','EMA20')['unknown_reason']=='symbol_missing';C['provider_missing_sid']+=1
 # Equality belongs to no breach: comparison is deliberately a consuming-adapter duty.
 for indicator in ['EMA20','EMA60','BOLL20_MID','BOLL20_LOWER']:
  x=provider.at('constant_equal_line','2022-03-21',indicator);assert x['status']=='READY' and not(x['causal_close']<x['line']);C['equality_no_strict_breach']+=1
out=dict(status='PASS_PREFIX_AND_FORMULA_ONLY',cases=[x[0] for x in cases],checks=dict(C),source_sha256=S,method='Execute only the parsed production validity/formula block against synthetic small frames; compare with an independent iterative EMA/ringbuffer population-variance oracle. Actual Provider queried for all cases/days. No production data generated or accounts run.',limits=['Data artifact source/hash/real-row numerical audit awaits immutable MANIFEST.','Consumer early-exit/grace state machine not audited by provider-only test.','Explicit definition: invalid current quote is UNKNOWN; later valid quotes in same original source resume prior valid-observation state; genuine source segment changes restart readiness.','Non-numeric malformed strings are not silently accepted by astype(float); original source manifest construction must fail rather than coerce them into valid observations.'])
(O/'INDICATOR_PREFIX_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False,indent=2))
