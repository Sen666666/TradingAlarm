"""New10/40 production kernel physical-prefix, future mutation and UNKNOWN tests."""
from pathlib import Path
import ast,copy,json,hashlib,sys
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;F=O.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
t=ast.parse((F/'prepare_context_variants.py').read_text());main=next(x for x in t.body if isinstance(x,ast.FunctionDef) and x.name=='main');stock=next(x for x in main.body if isinstance(x,ast.For) and ast.unparse(x.target)=='(ix, m)');loop=next(x for x in stock.body if isinstance(x,ast.For) and ast.unparse(x.target)=='n');assign=[x for x in main.body if isinstance(x,ast.Assign) and ast.unparse(x.targets[0]) in ['anchors','mr']];code=compile(ast.fix_missing_locations(ast.Module(body=assign+[loop],type_ignores=[])),'PRODUCTION_VARIANT_KERNEL','exec')
dates=pd.bdate_range('2021-01-04',periods=140);f0=pd.DataFrame(dict(close=100+np.arange(140)*.2,segment_id=0.),index=dates);g0=pd.DataFrame(dict(close=100+np.arange(140)*.1,segment_id=0.),index=dates);m0=pd.DataFrame(dict(close=300+np.arange(140)*.05),index=dates)
def fixture(f=f0,g=g0,m=m0,valid=None):return dict(f=f.copy(),g=g.copy(),market=m.copy(),valid=pd.Series(True,index=f.index) if valid is None else valid.copy())
def kernel(x):
 f=x['f'];keep=np.asarray(f.index>=dates[20]);env=dict(np=np,pd=pd,f=f,g=x['g'],market=x['market'],valid=x['valid'],dates=f.index[keep],keep=keep,z={'observed_valid':x['valid'].to_numpy()[keep]});exec(code,env);return env['z'],f.index[keep]
cases=[('ordinary',fixture())]
f=f0.drop(dates[20]);cases.append(('missing_exact40_anchor_not_own40',fixture(f=f)))
f=f0.copy();f.loc[:dates[24],'segment_id']=1;cases.append(('stock_segment_boundary',fixture(f=f)))
g=g0.copy();g.loc[:dates[24],'segment_id']=1;cases.append(('industry_segment_boundary',fixture(g=g)))
v=pd.Series(True,index=f0.index);v.loc[dates[60]]=False;cases.append(('invalid_current_observation',fixture(valid=v)))
v=pd.Series(True,index=f0.index);v.loc[dates[:35]]=False;cases.append(('EMA40_warmup_different_from10',fixture(valid=v)))
f=f0.copy();f.loc[dates[20],'close']=0;cases.append(('zero_stock40_anchor',fixture(f=f)))
g=g0.copy();g.loc[dates[20],'close']=-1;cases.append(('negative_industry40_anchor',fixture(g=g)))
cases.append(('empty_symbol',fixture(f=f0.iloc[:0])))
v=pd.Series(True,index=f0.index);v.loc[dates[30:40]]=False;cases.append(('skip_invalid_observations_not_zero',fixture(valid=v)))
res=[];count=0
for name,x in cases:
 full,ds=kernel(x);cut=dates[70];crop=copy.deepcopy(x)
 for k in ['f','g','market']:crop[k]=crop[k].loc[:cut]
 crop['valid']=crop['valid'].loc[:cut];prefix,pds=kernel(crop);mut=copy.deepcopy(x)
 for k in ['f','g','market']:mut[k].loc[mut[k].index>cut,'close']*=1000000
 changed,_=kernel(mut);mask=np.asarray(ds<=cut)
 for k,a in prefix.items():
  assert np.allclose(a,full[k][mask],equal_nan=True,rtol=0,atol=0),(name,k,'physical');assert np.allclose(a,changed[k][mask],equal_nan=True,rtol=0,atol=0),(name,k,'future');count+=2
 if len(ds):
  j=int(ds.searchsorted(dates[60]));r10=bool(full['ready_R10'][j]);r40=bool(full['ready_R40'][j])
  if name in ['missing_exact40_anchor_not_own40','stock_segment_boundary','industry_segment_boundary','zero_stock40_anchor','negative_industry40_anchor']:assert r10 and not r40
  if name=='invalid_current_observation':assert not r10 and not r40 and not full['ready_P10'][j] and not full['ready_P40'][j]
  if name=='EMA40_warmup_different_from10':assert full['ready_P10'][j] and not full['ready_P40'][j]
 res.append(dict(case=name,physical_prefix_exact=True,future_mutation_exact=True))
sys.path.insert(0,str(F));from variant_provider import VariantProvider
for r,e in [(10,10),(40,40),(10,40),(40,10),(20,60)]:
 try:VariantProvider(r,e)
 except AssertionError:pass
 else:raise AssertionError(('unfrozen combo accepted',r,e))
result=dict(status='PASS_NEW_KERNEL_PREFIX_FUTURE_UNKNOWN_AND_NO_COMBO_SCAN',cases=res,array_prefix_comparisons=count,rejected_unfrozen_parameter_pairs=5,source_sha256={str(F/'prepare_context_variants.py'):sha(F/'prepare_context_variants.py'),str(F/'variant_provider.py'):sha(F/'variant_provider.py'),str(F/'ROBUSTNESS_FREEZE.json'):sha(F/'ROBUSTNESS_FREEZE.json')},script_sha256=sha(__file__),new_accounts=0)
(O/'VARIANT_CONTEXT_PREFIX_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
