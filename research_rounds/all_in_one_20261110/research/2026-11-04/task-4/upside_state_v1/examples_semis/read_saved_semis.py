"""Bounded read-only examples: saved No60 layer chains and already built causal features.

No Account/Market/Runner/RiskBook/route, strategy code, scan or parameter test.
Only the prelisted stock/date snapshots are read. H20C is a close-channel descriptor,
not intraday high and not a new trade signal or admission.
"""
from pathlib import Path
import hashlib, json, math, pickle
import pandas as pd

ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4')
OUT=ROOT/'upside_state_v1/examples_semis'
OUT.mkdir(parents=True,exist_ok=True)
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
sources={}
def sha(p):
 p=Path(p);h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def readj(p):
 p=Path(p);sources[str(p)]=sha(p);return json.loads(p.read_text())
def clean(x):
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,dict):return {k:clean(v)for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v)for v in x]
 if hasattr(x,'item'):return clean(x.item())
 if isinstance(x,float)and not math.isfinite(x):return None
 if isinstance(x,pd.Timestamp):return x.isoformat()
 return x
def dump(name,x):(OUT/name).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

roles=readj(ROOT/'trend_hold_v1/funding/ALL25_ROLE_PROTECTION_DIRECT_EVIDENCE.json')
entries=readj(ROOT/'industry_capital_v1/actual25_role_entry/ALL25_ACTUAL_ENTRY_ROLE_CHAIN.json')
entry_by={r['layer']:r for r in entries}
tails=readj(ROOT/'new_price_trend_v1/CP_TAIL_ALL_ORIGINAL_NECESSARY_BOUNDS.json')
tail_by={r['layer']:r for r in tails if r['window']=='strong' and r['fixed_2026H1_bought_25_layer']}
progress=readj(ROOT/'trend_hold_v1/ALL25_PROFIT_PROGRESS_SCALE.json')
progress_by={r['layer']:r for r in progress}
manifest=readj(MANIFEST);by_sid={r['symbol']:r for r in manifest}
price=ROOT/'new_price_trend_v1/PRICE_FEATURES.pkl';sources[str(price)]=sha(price)
with price.open('rb')as f:features=pickle.load(f)
feature_manifest=readj(ROOT/'new_price_trend_v1/PRICE_FEATURE_MANIFEST.json')
assert sources[str(price)]==feature_manifest['output_sha256']

# Dates are real entry/exit/reentry decisions or fixed mid-hold/month-end observations.
# They are not chosen by later maxima or any fitted price threshold.
dates={
 '300666.SZ':['2026-01-15','2026-01-16','2026-01-23','2026-01-29','2026-02-06','2026-02-09','2026-02-12','2026-02-25','2026-05-25','2026-06-25','2026-06-29'],
 '301611.SZ':['2026-01-15','2026-01-16','2026-01-23','2026-01-29','2026-02-10','2026-05-13','2026-06-24','2026-06-29'],
 '603061.SH':['2026-01-16','2026-01-19','2026-01-20','2026-01-28','2026-02-11','2026-02-12','2026-05-11','2026-05-12','2026-05-20','2026-06-24','2026-06-29'],
 '605358.SH':['2026-05-08','2026-05-11','2026-05-20','2026-06-01','2026-06-30'],
 '600584.SH':['2026-05-20','2026-05-21','2026-05-26','2026-06-01','2026-06-02'],
 '300623.SZ':['2026-02-03','2026-02-04','2026-02-05','2026-03-03'],
}
snapshots=[]
for sid,ds in dates.items():
 rec=by_sid[sid];fp=Path(rec['refs']['facts']);cp=Path(rec['refs']['CP1'])
 sources[str(fp)]=sha(fp);sources[str(cp)]=sha(cp)
 assert sources[str(fp)]==rec['output_sha256'][str(fp)]
 facts=pd.read_parquet(fp);cpdf=pd.read_parquet(cp);px=features[sid]
 for day in ds:
  at=pd.Timestamp(day)
  if at not in facts.index or at not in px.index:
   snapshots.append(dict(sid=sid,day=day,status='unknown_missing_exact_day'));continue
  p=facts.index.get_loc(at);f=facts.loc[at];z=px.loc[at]
  hist=facts.iloc[max(0,p-20):p]
  known=(len(hist)==20 and hist.segment_id.eq(f.segment_id).all() and hist.close.notna().all() and hist.close.gt(0).all())
  prior_h=float(hist.close.max())if known else None
  prior_ema=px.ema20.iloc[p-1]if p and facts.index.equals(px.index) else px.ema20.loc[:at].iloc[-2]if len(px.loc[:at])>=2 else None
  cprow=cpdf.loc[at]if at in cpdf.index else None
  snapshots.append(dict(sid=sid,day=day,status='known',clock='CLOSE only, following OPEN execution would require all original gates again',
   facts={k:f[k]for k in ['close','raw_close','factor','segment_id','e0_ready','e0_target','e0_floor','i_target','i_floor','i_buy','g_ready','g_grade','g_fresh_up']},
   cached_price={k:z[k]for k in ['ema20','ema60','sma20','sma60','bb20_prior_upper','bb20_cross_known','bb20_cross','ema_trend_known','ema_trend','bb_trend']},
   close_channel=dict(prior20close_max=prior_h,known=known,strict_close_breakout=bool(f.close>prior_h)if known else None,note='20 earlier valid observations in same contiguous source segment; excludes today; not a high-OHLC channel'),
   EMA20_rising_one_observation=bool(z.ema20>prior_ema)if prior_ema is not None and pd.notna(prior_ema) and pd.notna(z.ema20) else None,
   CP=dict(ready=cprow.ready,receipt=cprow.receipt,candidate=cprow.candidate,reset_reason=cprow.reset_reason)if cprow is not None else None))

all25=[]
for r in roles:
 e=entry_by[r['layer']];p=progress_by[r['layer']];t=tail_by.get(r['layer'])
 all25.append(dict(layer=r['layer'],sid=r['sid'],name=r['name'],role=r['role'],pool=r['entry_pool'],signal_at=r['signal_at'],opened=r['native_open'],
   actual_buy=r['actual_buy'],original_entry_branch=e['original_planning_branch'],original_signal_facts=e['original_signal_facts'],
   original_core_OPEN_failure_sets=e['original_CORE_OPEN_failure_sets'],signal_minimum_CORE_necessary=e['signal_minimum_CORE_necessary'],
   original_same_stock_layers_at_signal=e['original_same_stock_layers_at_signal'],actual_exit_decisions=r['actual_exit_decisions'],actual_sell_fills=r['actual_sell_fills'],
   closed_net=r['whole_original_closed_net'],still_open_cash_balance_not_profit=r['original_open_cash_balance_not_profit'],
   progress_descriptive_not_signal=p,first_CP_exit_necessary_bound_only=t))

focus_intervals=readj(ROOT/'reentry_v1/FOCUS16_LOCAL_HIGH_AND_SIZE.json')
focus_funding=readj(ROOT/'reentry_v1/funding_agent/ALL16_RECEIPTS_WITH_REAL_RESOURCES.json')
dump('KEY_DATE_INPUTS.json',snapshots)
dump('ALL25_SAVED_ROLE_HOLDING_CHAINS.json',all25)
dump('FOCUS16_SAVED_LOCAL_HIGH_CONTEXT.json',focus_intervals)
dump('FOCUS16_SAVED_ACTUAL_FUNDING_CONTEXT.json',focus_funding)
dump('SOURCE_SHA256.json',sources)
dump('SCOPE.json',dict(status='READ_ONLY_KEY_DATE_EXAMPLES_COMPLETE',snapshot_stocks=len(dates),snapshot_dates=len(snapshots),all25_layers=len(all25),all25_stocks=len({r['sid']for r in all25}),
 no_new_account=True,no_new_backtest=True,no_parameter_test=True,no_new_route=True,no_new_trade_path=True,
 feature_reuse='Existing audited PRICE_FEATURES.pkl, exact SHA binding; limited prior-20-close scalar descriptors only, no market scan or new policy events',
 limits=['Fixed25 is an actual-bought conditional set, not all126 industry stocks or causal opportunity coverage','Diagnostic named stocks were requested after observing past outcomes; not a real-time selection pool','No new maximum, PnL counterfactual, dynamic capital allocation or strategy implementation','Native I/ACT/E0/hardline and FIFO/units/funding must remain explicit; EMA does not override them']))
print(json.dumps(dict(snapshots=len(snapshots),layers=len(all25),new_accounts=0,new_backtests=0,new_routes=0),ensure_ascii=False))
