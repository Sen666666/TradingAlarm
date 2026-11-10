"""Actual missing-cohort input/receipt/sizing fixture; no cash or strategy consumer."""
from pathlib import Path
from decimal import Decimal as D
from types import SimpleNamespace
import ast,sys,json,time,hashlib,resource,collections
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent;J=R/'independent_channel_joint_economic_v1';B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
protocol=json.loads((O/'PROTOCOL.json').read_text());start=time.monotonic()
code={str(p):sha(p) for p in [J/'market_adapter.py',J/'joint_policy.py',J/'gates.py',R/'independent_channel_full1709_preflight_v1/engine.py',R/'independent_channel_full1709_preflight_v1/fast_core.py',Path(__file__)]}
save('FIXTURE_CODE_SHA256_BEFORE.json',code)
sys.path.insert(0,str(J));sys.path.insert(0,str(B/'code'))
from market_adapter import MarketAdapter,open_projection
from joint_policy import PriceSizing,OpenView,industry_gate
from gates import require_economic_authorization
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeSchedule,FeeComponent
# Only three pure fee/sizing definitions; never import legacy top-level runners or engine.
p=R/'m3_stock_birth_during_sector_v1/relative_priority_v1/simulate.py';source=p.read_text();env=dict(D=D,meta={},rules=json.loads((B/'inputs-v2/market-rules.json').read_text()),proxies=json.loads((B/'inputs-v2/economic-protocol.json').read_text())['approved_proxy_ids'],market_identity_on=market_identity_on,version_on=version_on,QuantityRule=QuantityRule,FeeSchedule=FeeSchedule,FeeComponent=FeeComponent,SLIP=D('.0005'))
for n in ast.parse(source).body:
 if isinstance(n,ast.FunctionDef) and n.name in {'getmeta','fee','size'}:exec(compile(ast.Module(body=[n],type_ignores=[]),str(p)+':definition_only','exec'),env)
engine=SimpleNamespace(**{k:env[k] for k in ['getmeta','fee','size']},RuleUnavailable=RuleUnavailable);sizer=PriceSizing(engine)
blocked=[]
for w in ['2023','2024JanAug']:
 try:require_economic_authorization(w);raise AssertionError('unexpectedly authorized')
 except ValueError as e:
  assert str(e)=='ONLY_FIXED_TWO_WINDOWS';blocked.append(dict(window=w,result=str(e),cash_loop_not_called=True))
a=MarketAdapter(native_cache_limit=2);prefix=[];tickets=[];timings=[];knownchecks=[];openchecks=[]
for sid in protocol['fixture_sids']:
 t=time.monotonic();full=a.load_sid(sid);timings.append(dict(sid=sid,stage='full_market_replay',seconds=time.monotonic()-t,deep_mb=float(full.memory_usage(deep=True).sum()/2**20)))
 for w,dd in protocol['fixture_dates'].items():
  dates=pd.DatetimeIndex(dd);cut=dates[-1];t=time.monotonic();short=a.load_sid(sid,cut=cut);pd.testing.assert_frame_equal(full.loc[short.index],short,check_exact=True,check_freq=False)
  prefix.append(dict(sid=sid,window=w,cut=str(cut.date()),all_history_rows=len(short),equal=True,seconds=time.monotonic()-t))
  # True physical source cuts in stock/sector/H1, not merely slicing final results.
  for d in [dates[0],dates[-1]]:
   ff=a.native_industry(sid,d);cc=a.native_industry(sid,d,cut=cut);assert ff==cc
   knownchecks.append(dict(sid=sid,window=w,day=str(d.date()),industry_prefix_exact=True,values=ff))
  t=time.monotonic()
  for day in dates:
   row=short.loc[day].to_dict()
   if not row['receipt']:continue
   qual=a.qualification(sid,day,cut=cut);fact=dict(sid=sid,day=day,**row,**qual);check=sizer.close_check(fact,window=w)
   nd=a._engine.cal[a._engine.cal>day][0];op=a.open(sid,nd);sigline=tuple(str(row[k]) for k in ['source_kind','source_path','segment_id']);oline=tuple(str(op[k]) for k in ['source_kind','source_path','segment_id']);match=sigline==oline and pd.notna(op['adjustment_factor']) and np.isclose(op['adjustment_factor'],row['adjustment_factor'],rtol=1e-11)
   opened={'result':'SOURCE_OR_FACTOR_UNKNOWN_NO_SIZING'}
   if match:opened=sizer.initial_open(sid,nd,OpenView.from_mapping(op),floor=D(str(row['S_new']))/D(str(op['adjustment_factor'])),capacity=row['capacity_shares'])
   tickets.append(dict(sid=sid,window=w,day=str(day.date()),root_id=row['root_id'],receipt_id=row['receipt_id'],born=bool(row['born']),phase=row['phase'],industry=industry_gate(qual),PVR_known=qual['PVR_known'],PVR_score=qual['PVR_score'],close_check=check['close_check'],close_q=check.get('close_q'),next_common_open=str(nd.date()),open_source_factor_match=bool(match),isolated_open_size=opened['result'],open_q=int(opened.get('q',0)),actual_qualification_for_trading='NOT_EVALUATED_AB_OWNERSHIP_AND_FULL_POOL_COMPETITION',label='NOT_ECONOMIC_ROUND'))
  timings.append(dict(sid=sid,window=w,stage='receipt_qualification_and_isolated_size',seconds=time.monotonic()-t))
  # Whitelisted OPEN projection invariant against arbitrary same-day future daily data.
  nd=a._engine.cal[a._engine.cal>cut][0];base=a.open(sid,nd);raw=pd.DataFrame([dict(base,high=1.,low=1.,close=1.,amount=1.,phase='A',S_new=1.)],index=[nd]);v1=open_projection(raw,sid,nd)
  for field in ['high','low','close','amount','S_new']:raw[field]=-999.
  raw['phase']='FUTURE_CHANGED';assert v1==open_projection(raw,sid,nd);openchecks.append(dict(sid=sid,window=w,open_day=str(nd.date()),future_columns_irrelevant=True))
 print('FIXTURE_SID',sid,'receipts_so_far',len(tickets),'elapsed',round(time.monotonic()-start,2),flush=True)
 for key in list(a._market):
  if key[0]==sid and key[1]!=pd.Timestamp('2026-06-30'):del a._market[key]
pd.DataFrame(tickets).to_csv(O/'FIXTURE_RECEIPT_FEASIBILITY.csv',index=False);save('PREFIX_QA.json',prefix);save('NATIVE_INDUSTRY_PREFIX_QA.json',knownchecks);save('OPEN_ISOLATION_QA.json',openchecks);save('ECONOMIC_GATE_QA.json',blocked);save('FIXTURE_TIMINGS.json',timings)
sources=a.verify_sources();sources[str(p)]=sha(p);save('FIXTURE_SOURCE_SHA256.json',sources)
assert all(sha(p)==h for p,h in code.items());old=json.loads((O/'OLD_TREE_SHA256_BEFORE.json').read_text());assert all(sha(p)==h for p,h in old.items())
summary=dict(result='PASS_REAL_INPUT_PREFIX_RECEIPT_SIZE_ONLY_NOT_ECONOMIC_LABELS',sids=protocol['fixture_sids'],prefix_checks=len(prefix),industry_physical_prefix_checks=len(knownchecks),open_isolation_checks=len(openchecks),receipts=len(tickets),industry=dict(collections.Counter(r['industry'] for r in tickets)),close_size=dict(collections.Counter(r['close_check'] for r in tickets)),open_size=dict(collections.Counter(r['isolated_open_size'] for r in tickets)),per_window={w:dict(receipts=sum(r['window']==w for r in tickets),close_size_pass=sum(r['window']==w and r['close_check']=='PASS' for r in tickets)) for w in protocol['fixture_dates']},cash_loops=0,trade_rounds=0,selected_universe_labels=0,known_at='market receipts historical CLOSE; actual generated labels would be known no earlier than actual 2026 research creation; upstream historical sources remain NON_PIT',unverified=['full pool AB/PRICE competition','ownership and prior state','same-contract cash ledger for new dates','financial eligibility of new selected rounds','outcome maturities'],elapsed_seconds=time.monotonic()-start,peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20,old_tree_unchanged=True)
save('FIXTURE_QA.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
