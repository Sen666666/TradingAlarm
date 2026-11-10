"""Quantity facts and bounded past-price context; no simulation of selective exits."""
from pathlib import Path
from decimal import Decimal as D
import gzip,hashlib,json,pickle
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4');OUT=ROOT/'upside_state_v1/examples_semis';SRC={}
def bind(p):
 p=Path(p);h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 SRC[str(p)]=h.hexdigest();return p
def rj(p):return json.loads(bind(p).read_text())
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
rows=rj(OUT/'ALL25_SAVED_ROLE_HOLDING_CHAINS.json');by={r['layer']:r for r in rows};answer=[]
for sid,ids,exitday in [('603061.SH',[674,677,684,702],'2026-02-11'),('600584.SH',[1059,1075],'2026-06-01')]:
 rr=[by[i]for i in ids];tt=[r['first_CP_exit_necessary_bound_only']for r in rr];q=sum(t['actual_qty']for t in tt);step=tt[0]['SELL_step'];sell=((q+2*step-1)//(2*step))*step
 answer.append(dict(sid=sid,first_CP_exit_day=exitday,total_actual_qty=q,SELL_step=step,
   per_layer_old_half_tail_retain_qty=[t['optimistic_half_tail_qty']for t in tt],stock_half_sell_grid_quantity=sell,stock_half_retain_quantity=q-sell,
   quantity_calculation_scope='Static integer-grid arithmetic only; not submitted, risk-authorized or filled, and no layer selection/partial PnL computed',
   layers=[dict(layer=r['layer'],signal_at=r['signal_at'],opened=r['opened'],actual_buy_qty=r['actual_buy']['shares'],actual_buy_price=r['actual_buy']['price'],frozen_initial_CP_adjusted=t['entry_hardfloor'],CP_line_checked_at_exit=t['original_CP_checked'],current_I_adjusted=t['current_I'],close_adjusted=t['continuous_close'],old_paper_hardfloor=max(D(t['entry_hardfloor']),D(t['current_I'])),old_paper_hardline_survives=t['hard_priorities_survive'],EMA_license=t['EMA_license'],original_closed_net=r['closed_net'],original_exit_proposals=r['actual_exit_decisions'])for r,t in zip(rr,tt)],
   hard_mixed_classification='Under prior CP-tail paper hard-floor=max(frozen initial CP,I); native original actual exit reason remains CP1_add_protection for all layers',
   original_actual_sell_trade=rr[0]['actual_sell_fills'][0]['whole_trade'],
   FIFO_correction='Native physical inventory sells oldest eligible physical lots, while pilot.fill_exit attributes receipt only to sell_layers target logical ids. Therefore physical FIFO does not itself prove newer broken logical layer cannot be reduced while retaining an older logical winner. Original full exits are facts; a selective policy requires explicit target quantities/ids, remaining_target, hard-priority merge, sellable aggregate and budget synchronization, none simulated here.'))
save('AGGREGATE_LAYER_QUANTITY_FACTS.json',answer)

m={r['symbol']:r for r in rj('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
fpath=bind(m['603061.SH']['refs']['facts']);assert SRC[str(fpath)]==m['603061.SH']['output_sha256'][str(fpath)];f=pd.read_parquet(fpath)
with bind(ROOT/'new_price_trend_v1/PRICE_FEATURES.pkl').open('rb')as h:z=pickle.load(h)['603061.SH']
breaks=[]
for at,r in f.loc['2026-01-01':'2026-01-28'].iterrows():
 i=f.index.get_loc(at);hist=f.iloc[i-20:i];assert len(hist)==20 and hist.segment_id.eq(r.segment_id).all() and hist.close.notna().all() and hist.close.gt(0).all();high=float(hist.close.max())
 breaks.append(dict(day=str(at.date()),close_adjusted=float(r.close),raw_close=float(r.raw_close),prior20_close_max=high,strict_close_breakout=bool(r.close>high),i_target=int(r.i_target),i_buy=bool(r.i_buy),EMA20=float(z.loc[at].ema20),EMA60=float(z.loc[at].ema60)))
pair=ROOT/'new_price_trend_v1/funding/runs/strong_OFF/pair';op=[];fund=[]
for file,target in [('opportunities.jsonl.gz',op),('funding.jsonl.gz',fund)]:
 with gzip.open(bind(pair/file),'rt')as h:
  for line in h:
   r=json.loads(line);day=r.get('day',r.get('at',''))[:10]
   if r.get('sid')=='603061.SH'and'2026-01-01'<=day<='2026-01-29':target.append(r)
save('GOLD_PREENTRY_BREAKOUT_AND_ORIGINAL_PERMISSIONS.json',dict(scope='Only Jan1-Jan28 past inputs, no later maxima; first means first observed H1 session, not first all-history or a permission to trade',fixed_breakout_context=breaks,first_observed_H1_strict_breakout=next(r for r in breaks if r['strict_close_breakout']),original_opportunities=op,original_funding=fund,
   last_add_702_existing_minimum_I_risk=by[702]['signal_minimum_CORE_necessary'],common_floor_arithmetic_for_702=dict(first_seed_initial_line=by[674]['first_CP_exit_necessary_bound_only']['entry_hardfloor'],signal_I='255.92213566639577',signal_EMA20='228.6185',max_seed_I_EMA='255.92213566639577',warning='This example common line equals I; original 100-share fee-inclusive I risk4604.987 exceeds original .25%3844.772. Widening CP to I does not admit the same quantity without changing risk/size; no new order calculated.')))
for p in ['/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py','/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py']:bind(p)
save('AGGREGATE_SOURCE_SHA256.json',SRC)
print(json.dumps(dict(no_new_accounts=True,no_new_backtest=True,no_new_route=True,quantity_examples=len(answer),gold_prior_snapshots=len(breaks))))
