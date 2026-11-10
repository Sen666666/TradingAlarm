"""Four requested cached price inputs for root paper card; no policy execution."""
from pathlib import Path
import gzip,hashlib,json,pickle
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4');OUT=ROOT/'upside_state_v1/examples_semis';SRC={}
def bind(p):
 p=Path(p);h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 SRC[str(p)]=h.hexdigest();return p
m={r['symbol']:r for r in json.loads(bind('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())}
with bind(ROOT/'new_price_trend_v1/PRICE_FEATURES.pkl').open('rb')as f:px=pickle.load(f)
rows=[]
for sid,dates in [('603061.SH',['2026-01-28','2026-02-11']),('605358.SH',['2026-05-19','2026-05-20'])]:
 path=bind(m[sid]['refs']['facts']);assert SRC[str(path)]==m[sid]['output_sha256'][str(path)];facts=pd.read_parquet(path);z=px[sid]
 for day in dates:
  at=pd.Timestamp(day);i=facts.index.get_loc(at);r=facts.loc[at];history=facts.iloc[i-10:i]
  assert len(history)==10 and history.segment_id.eq(r.segment_id).all() and history.close.notna().all() and history.close.gt(0).all()
  # Exact same-source stock observations as the root card; do not invent holidays.
  lag5=facts.index[i-5];prev=facts.index[i-1];assert facts.segment_id.loc[lag5:at].eq(r.segment_id).all()
  rows.append(dict(sid=sid,day=day,continuous_close=float(r.close),EMA20=float(z.loc[at].ema20),EMA60=float(z.loc[at].ema60),EMA20_lag5=float(z.loc[lag5].ema20),lag5_day=str(lag5.date()),previous_observation=str(prev.date()),previous_close=float(facts.loc[prev].close),previous_EMA20=float(z.loc[prev].ema20),previous10_close_min=float(history.close.min()),previous10_window_first=str(history.index[0].date()),previous10_window_last=str(history.index[-1].date()),T5_price_only=bool(r.close>z.loc[at].ema20 and z.loc[at].ema20>z.loc[lag5].ema20),close_below_EMA60=bool(r.close<=z.loc[at].ema60),two_closes_below_EMA20_and_below_prev10close_min=bool(r.close<z.loc[at].ema20 and facts.loc[prev].close<z.loc[prev].ema20 and r.close<history.close.min()),scope='Four exact original observations only; T5 field is price descriptor, not VERIFIED state, H grant, funding or a new order'))
with gzip.open(bind(ROOT/'new_price_trend_v1/funding/runs/strong_OFF/pair/opportunities.jsonl.gz'),'rt')as f:
 op=next(json.loads(s)for s in f if '605358.SH'in s and '2026-05-20'in s)
assert op['sid']=='605358.SH'and op['day']=='2026-05-20'and op['core_Q']is True
result=dict(status='READ_ONLY_FOUR_REQUESTED_INPUTS',rows=rows,original_winner_May20_opportunity_exact=op,clock='Each value is CLOSE-known or earlier in the same valid source segment; no later maximum.',new_accounts=0,new_backtests=0,new_orders=0,new_routes=0,other_dates_T5='NOT_COMPUTED_UNKNOWN')
(OUT/'FOUR_PAPER_T5_L10_INPUTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
(OUT/'FOUR_PAPER_INPUT_SOURCE_SHA256.json').write_text(json.dumps(SRC,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
