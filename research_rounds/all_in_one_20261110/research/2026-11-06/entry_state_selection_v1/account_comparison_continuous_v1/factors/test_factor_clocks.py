"""Synthetic action-clock cases against exact original prepare_signal AST."""
from pathlib import Path
import ast,json,hashlib
from decimal import Decimal,localcontext,ROUND_HALF_EVEN
import pandas as pd,numpy as np
from continuous_factors import OpenFactorTimeline,FactorSource
O=Path(__file__).resolve().parent
S=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/current_pool_bridge.py')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/data_utils.py')
env=dict(pd=pd,np=np,Decimal=Decimal,localcontext=localcontext,ROUND_HALF_EVEN=ROUND_HALF_EVEN,OHLC=('open','high','low','close'))
for p,names in [(B,{'boolean_column'}),(S,{'decimal','prepare_signal'})]:
 nodes=[n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in names]
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),env)
def frame(days,closes):
 return pd.DataFrame(dict(open=closes,high=closes,low=closes,close=closes,volume=[100.]*len(days)),index=pd.DatetimeIndex(days))
def event(day,cash,split):
 return dict(effective_date=day,cash_per_old_share=str(cash),split_ratio=str(split))
cases=[
 ('observed_action',frame(['2024-01-01','2024-01-02','2024-01-04'],[10.,12.,11.]),[event('2024-01-02',.2,1.3)]),
 ('consecutive_missing_actions',frame(['2024-01-01','2024-01-05'],[10.,8.]),[event('2024-01-02',.2,1.3),event('2024-01-03',.1,1.1)]),
 ('invalid_close_before_action',frame(['2024-01-01','2024-01-02','2024-01-05'],[10.,np.nan,8.]),[event('2024-01-03',.2,1.3)]),
 ('signal_terms_differ',frame(['2024-01-01','2024-01-02'],[10.,7.]),[dict(event('2024-01-02',0,1),signal_cash_per_old_share='.5',signal_split_ratio='1.2')])]
out=[]
for name,raw,events in cases:
 original=env['prepare_signal'](raw,{'adjustment':{'method':'theoretical_ex_price'}},events)
 t=OpenFactorTimeline(raw,events)
 assert np.array_equal(t.at_dates(original.index).to_numpy(),original.adjustment_factor.to_numpy())
 for day in original.index:
  # Truncate observations after query; close on query is poisoned.
  cut=raw.loc[:day].copy()
  if day in cut.index:cut.loc[day,'close']=999999.
  short=OpenFactorTimeline(cut,events,end=day)
  assert short.factor(day)==t.factor(day)
 assert FactorSource({'X':t}).factor_at('X',raw.index[-1])==t.factor(raw.index[-1])
 out.append(dict(case=name,exact_original_AST_factor=True,all_query_prefix_current_close_poison_invariant=True,rows=len(original)))
p=O/'SYNTHETIC_TESTS.json'
with p.open('x') as f:json.dump(dict(passed=True,cases=out,account_runs=0,original_source_sha256=hashlib.sha256(S.read_bytes()).hexdigest(),helper_sha256=hashlib.sha256(B.read_bytes()).hexdigest(),test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),f,indent=2)
print('SYNTHETIC_PASS',len(out))
