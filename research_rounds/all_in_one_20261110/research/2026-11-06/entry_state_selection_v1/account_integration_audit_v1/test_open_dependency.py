"""Bounded dependency proof and candidate causal input kernel. No account run."""
from pathlib import Path
from types import SimpleNamespace as NS
from decimal import Decimal as D
from datetime import datetime
from zoneinfo import ZoneInfo
import ast,json,hashlib,copy
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
SRC=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/temperature-sizing-20261026/code/fast_market.py')
RAW=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/bars')
tree=ast.parse(SRC.read_text());cl=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='FastMarket');node=next(n for n in cl.body if isinstance(n,ast.FunctionDef) and n.name=='window')
def capture(*x):
 return dict(at=str(x[2]),open=str(x[3]),execution_price=str(x[4]),capacity=x[8],buy_allowed=x[10],sell_allowed=x[11],basis=x[15])
class RuleUnavailable(Exception):pass
env=dict(np=np,pd=pd,D=D,RuleUnavailable=RuleUnavailable,market_identity_on=lambda *x:None,ledger=NS(FillWindow=capture))
exec(compile(ast.Module(body=[node],type_ignores=[]),str(SRC),'exec'),env);window=env['window']
def kernel(a,p,side):
 """Data-only causal proxy; no authorization, no order, no certified execution."""
 op=a['open'][p]
 if not np.isfinite(op) or op<=0:return None
 positive=np.flatnonzero(np.isfinite(a['volume'][:p])&(a['volume'][:p]>0))
 if len(positive)<20:return None
 cap=int(a['volume'][positive[-20:]].mean()*.01)
 return dict(open=str(D(str(op))),execution_price=str(D(str(op))*(D('1.0005') if side=='buy' else D('.9995'))),capacity=cap,basis='PROPOSED_PRIOR_VOLUME_OPEN_PROXY_NOT_DEPLOYED',historical_execution_eligibility='UNKNOWN')
tests=[];raw=[]
for sid,day,side in [('000547.SZ','2026-01-16','sell'),('000681.SZ','2026-01-16','buy'),('000029.SZ','2024-09-25','buy')]:
 path=RAW/(sid+'.parquet');f=pd.read_parquet(path).sort_values('trade_date')
 days=pd.to_datetime(f.trade_date).astype('int64').to_numpy()//86400000000000
 p=int(np.flatnonzero(f.trade_date.eq(day))[0]);at=datetime.fromisoformat(day+'T09:30:00').replace(tzinfo=ZoneInfo('Asia/Shanghai'))
 a=dict(days=days,**{k:f[k].to_numpy(float) for k in ['open','high','low','close','volume']})
 a['valid']=f.price_eligible.to_numpy(bool);a['positive']=np.flatnonzero(np.isfinite(a['volume'])&(a['volume']>0))
 raw.append(dict(sid=sid,day=day,path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),row=f.iloc[p].to_dict(),prior20_positive_volume=a['volume'][a['positive'][np.searchsorted(a['positive'],p)-20:np.searchsorted(a['positive'],p)]].tolist()))
 results={}
 for variant in ['observed','force_flat','force_nonflat','zero_volume','tiny_volume','corrupt_close_and_valid']:
  z=copy.deepcopy(a)
  if variant=='force_flat':z['high'][p]=z['low'][p]=z['open'][p]
  elif variant=='force_nonflat':z['high'][p]=z['open'][p]+1;z['low'][p]=z['open'][p]-1
  elif variant=='zero_volume':z['volume'][p]=0
  elif variant=='tiny_volume':z['volume'][p]=100
  elif variant=='corrupt_close_and_valid':z['close'][p]=float('nan');z['valid'][p]=False
  z['positive']=np.flatnonzero(np.isfinite(z['volume'])&(z['volume']>0))
  s=NS(arr={sid:z},_cache=lambda at:None,wc={},lines={sid:NS(market='A')},sessions_set={'A':{at}},source_available=lambda *x:None,rules={},protocol=dict(approved_proxy_ids=[],participation_rate=.01,daily_execution={'A':dict(price_limit_policy='conservative_hl_proxy',reject_flat_day=True,slippage_bps='5',stress_slippage=True)},sellable_lag_sessions={'A':1},settlement_lag_sessions={'A':0}),_version=lambda *x:dict(buy_allowed=True,sell_allowed=True),rate=lambda *x:None,quantity=lambda *x:None,fees=lambda *x:None,lag=lambda *x:None,bundle=NS(series={sid:NS(record=dict(raw=dict(sha256=raw[-1]['sha256'])))}),window_verified={(sid,side,1)})
  results[variant]=dict(native_window=window(s,sid,at,side,1),proposed_kernel=kernel(z,p,side))
 assert len({json.dumps(x['proposed_kernel'],sort_keys=True) for x in results.values()})==1
 assert results['zero_volume']['native_window'] is None
 assert results['force_flat']['native_window']['buy_allowed']==False
 assert results['force_nonflat']['native_window']['buy_allowed']==True
 tests.append(dict(sid=sid,day=day,side=side,results=results,proposed_future_HLVC_valid_invariance='PASS'))
receipt=dict(status='BOUNDED_SOURCE_METHOD_DEPENDENCY_PROOF_AND_UNDEPLOYED_INPUT_KERNEL',native_source_sha256=hashlib.sha256(SRC.read_bytes()).hexdigest(),native_body='exact AST of FastMarket.window; metadata/rules/fees and superclass cross-check stubbed, so not a complete native Market integration test',tests=tests,raw_evidence=raw,scope='No Account, Runner, fills, cash, or new portfolio outcome executed. Native dependency is demonstrated; proposed kernel is not connected to orders, not a certified fill model, and does not repair fixed-future universe or factor-PIT limits.')
(O/'OPEN_DEPENDENCY_TEST.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps({k:receipt[k] for k in ['status','native_source_sha256','scope']},ensure_ascii=False));print('CASES',len(tests),'VARIANTS',sum(len(t['results']) for t in tests))

