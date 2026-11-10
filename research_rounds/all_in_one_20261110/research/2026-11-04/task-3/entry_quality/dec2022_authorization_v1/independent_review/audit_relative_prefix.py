"""Execute production vector-kernel AST on independent physical prefix fixtures."""
from pathlib import Path
from types import SimpleNamespace
import ast,copy,json,hashlib,sys,importlib.util
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;sys.path.insert(0,str(P));from context_provider import ContextProvider
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
tree=ast.parse((P/'prepare_relative_context.py').read_text());main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main');loop=next(n for n in main.body if isinstance(n,ast.For) and ast.unparse(n.target)=='(j, m)');body=loop.body;start=next(i for i,n in enumerate(body) if isinstance(n,ast.Assign) and ast.unparse(n.targets[0])=='old');end=next(i for i,n in enumerate(body) if isinstance(n,ast.Assign) and ast.unparse(n.targets[0]).startswith('counts['));calendar=[n for n in main.body if isinstance(n,ast.Assign) and ast.unparse(n.targets[0]) in {'anchor','mret'}];code=compile(ast.fix_missing_locations(ast.Module(body=calendar+body[start:end+1],type_ignores=[])),'PRODUCTION_KERNEL_AST','exec')
dates=pd.bdate_range('2021-01-04',periods=84);base=pd.DataFrame({'close':100+np.arange(84)*.2,'segment_id':0.},index=dates);industry=pd.DataFrame({'close':100+np.arange(84)*.1,'segment_id':0.},index=dates);idx=pd.DataFrame({'close':300+np.arange(84)*.05},index=dates)
def fixture(f=base,g=industry,mi=idx,valid=None,ema=None):
 ds=f.index;obs=np.ones(len(ds),bool) if valid is None else valid;ee=f.close.to_numpy(float)*1.01 if ema is None else ema
 old=dict(days=ds.to_numpy('datetime64[D]').astype('int32'),observed_valid=obs,values=np.column_stack([f.close.to_numpy(float),ee]));return dict(f=f.copy(),g=g.copy(),idx=mi.copy(),old=old)
def kernel(x):
 env=dict(np=np,pd=pd,provider=SimpleNamespace(data={'X':x['old']}),sid='X',sector='S',out={},counts={},f=x['f'],g=x['g'],idx=x['idx']);exec(code,env);return env['out']['X']
cases=[]
cases.append(('ordinary',fixture(),True))
f=base.drop(dates[10]);cases.append(('missing_exact_anchor_not_own_20',fixture(f=f),False))
f=base.copy();f.loc[dates[:15],'segment_id']=1;cases.append(('stock_source_transition',fixture(f=f),False))
g=industry.copy();g.loc[dates[:15],'segment_id']=1;cases.append(('industry_source_transition',fixture(g=g),False))
v=np.ones(84,bool);v[30]=False;cases.append(('invalid_current_observation',fixture(valid=v),False))
e=base.close.to_numpy(float)*1.01;e[30]=np.nan;cases.append(('EMA_unknown_R_remains_known',fixture(ema=e),True))
f=base.copy();f.loc[dates[10],'close']=0;cases.append(('zero_stock_anchor_unknown',fixture(f=f),False))
g=industry.copy();g.loc[dates[10],'close']=-1;cases.append(('negative_industry_anchor_unknown',fixture(g=g),False))
f=base.iloc[:0].copy();cases.append(('empty_symbol',fixture(f=f),None))
cases.append(('equality_price_not_weak',fixture(ema=base.close.to_numpy(float)),True))
results=[];checks=0
for name,x,expected in cases:
 full=kernel(x);cut=dates[40];prefix=copy.deepcopy(x)
 for k in ['f','g','idx']:prefix[k]=prefix[k].loc[:cut]
 keep=x['old']['days']<=int(cut.to_numpy().astype('datetime64[D]').astype('int64'))
 prefix['old']={k:v[keep] for k,v in x['old'].items()}
 cropped=kernel(prefix);mut=copy.deepcopy(x)
 for k in ['f','g','idx']:mut[k].loc[mut[k].index>cut,'close']*=1000000
 future=x['old']['days']>int(cut.to_numpy().astype('datetime64[D]').astype('int64'));mut['old']['values'][future]*=1000000;changed=kernel(mut)
 for k,v in cropped.items():
  if isinstance(v,np.ndarray):
   assert np.allclose(v,full[k][keep],equal_nan=True,rtol=0,atol=0),(name,k,'physical crop');assert np.allclose(v,changed[k][keep],equal_nan=True,rtol=0,atol=0),(name,k,'future mutation');checks+=2
 j=int(np.searchsorted(full['days'],int(dates[30].to_numpy().astype('datetime64[D]').astype('int64'))))
 if expected is not None:assert bool(full['ready_R'][j])==expected,(name,full['ready_R'][j])
 if name=='EMA_unknown_R_remains_known':assert not full['ready_P'][j]
 if name=='equality_price_not_weak':assert full['close'][j]==full['EMA20'][j]
 results.append(dict(case=name,physical_prefix_equal=True,future_mutation_equal=True,ready_R_at_probe=None if expected is None else bool(full['ready_R'][j])))
# Actual provider queries are exact-date only and factor-specific.
p=ContextProvider.__new__(ContextProvider);z=kernel(fixture());p.data={'X':z}
assert not p.at('MISSING',dates[30])['ready_R'];assert not p.at('X','2021-01-03')['ready_P'];assert not p.at('X','2021-01-09')['ready_R'];assert not p.at('X','2022-01-01')['ready_P']
spec=importlib.util.spec_from_file_location('I_H2_independent_pure',P/'native_adapter/mobile_authorization_adapter.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
qq=dict(day='2021-02-15',ready_R=False,ready_P=True,close=100.,EMA20=101.,RS20=None,sector='S',source_segment=0.,source_max_day='2021-02-15',anchor_day=None,unknown_reason='R unavailable')
assert m.predicate(qq,'P_ONLY')['denies_mobile'];assert not m.predicate(qq,'R_ONLY')['denies_mobile'];assert not m.predicate(qq,'JOINT')['denies_mobile']
qq.update(ready_R=True,RS20=0.,anchor_day='2021-01-18',EMA20=100.);assert m.predicate(qq,'R_ONLY')['denies_mobile'];assert not m.predicate(qq,'P_ONLY')['denies_mobile'];assert not m.predicate(qq,'JOINT')['denies_mobile']
at=pd.Timestamp('2021-02-15 15:10:00+08:00');row=SimpleNamespace(close=100.,segment_id=0.)
class Q:
 def __init__(self,q):self.q=q
 def at(self,*args):return self.q
assert m.provider_value(Q(qq),'X',at,row,'S')==qq
rejections=[]
for key,bad in [('day','2021-02-16'),('source_max_day','2021-02-16'),('sector','OTHER'),('source_segment',1.),('close',200.),('anchor_day','2021-02-15')]:
 q=copy.deepcopy(qq);q[key]=bad
 try:m.provider_value(Q(q),'X',at,row,'S')
 except AssertionError:rejections.append(key)
 else:raise AssertionError(('missing adapter identity rejection',key))
out=dict(status='PASS_PRODUCTION_AST_PHYSICAL_PREFIX_AND_DOMAIN',cases=results,exact_array_prefix_checks=checks,exact_lookup_missing_cases=4,adapter_identity_rejections=rejections,mode_specific_ready_and_equality=True,source_sha256={str(P/'prepare_relative_context.py'):sha(P/'prepare_relative_context.py'),str(P/'context_provider.py'):sha(P/'context_provider.py'),str(P/'native_adapter/mobile_authorization_adapter.py'):sha(P/'native_adapter/mobile_authorization_adapter.py'),str(Path(__file__)):sha(__file__)},limits=['Production relative kernel exercised, immutable EMA arrays supplied causally; all-source EMA prefix audit reused.','Common-market clock not own-stock valid20; missing endpoint stays unknown.','Immutable input HS300 positive price domain verified by full data audit; preparer does not itself enforce positivity of HS300 current endpoint. No actual invalid HS300 input.'])
(O/'RELATIVE_CONTEXT_PREFIX_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False,indent=2))
