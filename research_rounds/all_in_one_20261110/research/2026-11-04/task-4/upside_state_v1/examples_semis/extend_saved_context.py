"""Saved-state context and scalar accounting only; no order proposal or allocation."""
from pathlib import Path
from decimal import Decimal as D
import gzip,hashlib,json,pickle
import pandas as pd

ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4');OUT=ROOT/'upside_state_v1/examples_semis'
PAIR=ROOT/'new_price_trend_v1/funding/runs/strong_OFF/pair'
SOURCE={}
def bind(p):
 p=Path(p);h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 SOURCE[str(p)]=h.hexdigest();return p
def rj(p):return json.loads(bind(p).read_text())
def lines(p):
 with gzip.open(bind(p),'rt')as f:yield from map(json.loads,f)
def save(name,x):(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')

daily={r['at'][:10]:r for r in lines(PAIR/'daily.jsonl.gz')}
book=json.load(gzip.open(bind(PAIR/'B.json.gz'),'rt'))
ops=[r for r in lines(PAIR/'opportunities.jsonl.gz')if r['sid']=='605358.SH'and'2026-05-08'<=r['day']<='2026-05-21']
fund=[r for r in lines(PAIR/'funding.jsonl.gz')if r['sid']=='605358.SH'and'2026-05-08'<=r['at'][:10]<='2026-05-21']
rank=[r for r in lines(PAIR/'rank-policy.jsonl.gz')if r['sid']=='605358.SH'and r['day']in['2026-05-19','2026-05-20']]
industry=[r for r in lines(PAIR/'industry.jsonl.gz')if r['sector']=='URFI881121'and r['day']<='2026-05-20']
ref=rj(ROOT/'reentry_v1/funding_agent/ALL16_RECEIPTS_WITH_REAL_RESOURCES.json')
gold21=next(r for r in ref if r['sid']=='603061.SH'and r['signal_day']=='2026-05-20')['exact_open_responsibility']
manifest=rj('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
by_sid={r['symbol']:r for r in manifest}
fpath=bind(ROOT/'new_price_trend_v1/PRICE_FEATURES.pkl')
with fpath.open('rb')as f:features=pickle.load(f)

day='2026-05-20';d=daily[day];industry_layers=[r for r in d['layers']if r['sector']=='URFI881121']
industry_arithmetic=[]
for r in industry_layers:
 m=by_sid[r['sid']];path=bind(m['refs']['facts']);assert SOURCE[str(path)]==m['output_sha256'][str(path)]
 f=pd.read_parquet(path).loc[day];raw=D(str(f.raw_close));factor=D(str(f.factor));floor=D(r['floor'])/factor
 industry_arithmetic.append(dict(layer=r['id'],sid=r['sid'],role=r['role'],pool=r['pool'],qty=r['qty'],raw_CLOSE=raw,factor=factor,stored_adjusted_floor=r['floor'],raw_floor=floor,capital=D(r['qty'])*raw,known_line_risk_excluding_fees=D(r['qty'])*max(D(0),raw-floor),scope='Scalar original live-layer arithmetic, not a new reservation/admission.'))

row=next(r for r in industry_arithmetic if r['sid']=='605358.SH')
sold21=[r for r in book['trades']if r['side']=='sell'and r['at'][:10]=='2026-05-21']
net_sales21=sum((D(r['gross_cny'])-D(r['fees_cny'])for r in sold21),D(0))
cash21=D(d['available'])+net_sales21
assert abs(cash21-D(str(gold21['pools'][0]['budget_cash'])))<D('.000001')
winner=dict(signal_day=day,sid='605358.SH',source_state_kind='Saved original CLOSE, no TREND_ADD existed',
 daily_header={k:v for k,v in d.items()if k not in ['positions','layers']},stock_qty=d['positions']['605358.SH'],stock_original_layers=[r for r in d['layers']if r['sid']=='605358.SH'],stock_capital=row['capital'],stock_NAV_weight_pct=row['capital']/D(d['nav'])*100,
 latest_industry_event=industry[-1],industry_live_layers=industry_arithmetic,industry_capital=sum((r['capital']for r in industry_arithmetic),D(0)),industry_known_line_risk=sum((r['known_line_risk_excluding_fees']for r in industry_arithmetic),D(0)),
 saved_original_opportunities=ops,saved_original_funding=fund,saved_original_rank_policy=rank,
 next_OPEN_original_sales=sold21,next_OPEN_original_sale_net=net_sales21,next_OPEN_cash_after_original_sells_before_original_new_reservations=cash21,original_decision_10pct_cash_reserve=D(d['nav'])*D('.1'),next_OPEN_spendable_before_original_reservations=cash21-D(d['nav'])*D('.1'),
 next_OPEN_later_gold_candidate_turn=dict(scope='Later original gold turn, NOT hypothetical winner slot; original preceding reservations change industry/cash, cannot transfer this rejection to a new winner order',original_rank=gold21['original_rank'],pools=gold21['pools'],prior_actual_reserved_competitors=gold21['prior_actual_reserved_competitors'],prior_actual_reserved_gross=gold21['prior_actual_reserved_gross'],prior_actual_reserved_fees=gold21['prior_actual_reserved_fees']),
 missing=['No original TREND_ADD intent, risk-budget freeze, source token, routing result, or rank-policy row exists for 2026-05-20 winner','opportunity.rank is original H1 rank, not PVR slot. Introducing a new typed role must rerun original sorting and consumes resources; not done here','No causal economic result or hypothetical next-OPEN fill inferred from source availability'])
save('WINNER_605358_2026_05_20_SAVED_CONTEXT.json',winner)

raw_manifest=rj('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/manifest.json')
raw_rec={r['series_id']:r for r in raw_manifest['series']}['605358.SH'];raw_path=bind(raw_rec['raw']['path']);assert SOURCE[str(raw_path)]==raw_rec['raw']['sha256']
bars=pd.read_parquet(raw_path);bars=bars.set_index(pd.to_datetime(bars.trade_date)).sort_index();out=[]
for day in ['2026-05-19','2026-05-20','2026-05-21']:
 r=bars.loc[day];j=bars.index.get_loc(pd.Timestamp(day));prev=bars.iloc[j-1]
 out.append(dict(day=day,previous_trade_day=str(bars.index[j-1].date()),previous_close=str(prev.close),**{k:str(r[k])for k in ['open','high','low','close','volume']},flat_day=bool(r.high<=r.low)))
rules=rj('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
dated=next(r for r in reversed(rules['quantity_versions']['605358.SH'])if r['from']<='2026-05-21'and(r.get('to')is None or'2026-05-21'<r['to']))
save('WINNER_NEXT_OPEN_RAW_AND_UNITS.json',dict(sid='605358.SH',bars=out,dated_quantity_rule=dated,scope='Original raw bar and dated rule only. Full same-day HLV is ex-post execution proxy, not a signal-CLOSE input or queue guarantee.'))

fp=bind(by_sid['605358.SH']['refs']['facts']);f=pd.read_parquet(fp);z=features['605358.SH'];break_context=[]
for at in f.loc['2026-05-08':'2026-05-20'].index:
 pos=f.index.get_loc(at);hist=f.iloc[pos-20:pos];r=f.loc[at];known=(len(hist)==20 and hist.segment_id.eq(r.segment_id).all() and hist.close.notna().all() and hist.close.gt(0).all());h=float(hist.close.max())if known else None
 break_context.append(dict(day=str(at.date()),continuous_close=float(r.close),raw_close=float(r.raw_close),EMA20=float(z.loc[at].ema20),EMA60=float(z.loc[at].ema60),prior20_close_max=h,strict_close_breakout=bool(r.close>h)if known else None,i_buy=None if pd.isna(r.i_buy)else bool(r.i_buy),i_target=int(r.i_target)))
save('WINNER_PREVIOUS_BREAKOUT_CONTEXT.json',dict(sid='605358.SH',fixed_interval='Original entry decision May8 through proposed demonstration May20, no later observations',rows=break_context,latest_strict_breakout_before_May20=next((r for r in reversed(break_context)if r['day']<'2026-05-20'and r['strict_close_breakout']),None)))
save('ADDITIONAL_SOURCE_SHA256.json',SOURCE)
print(json.dumps(dict(no_new_accounts=True,no_new_backtest=True,no_new_route=True,winner_cash_before_new_reservations=str(cash21),winner_spendable_before_new_reservations=str(cash21-D(d['nav'])*D('.1')),industry_capital=str(winner['industry_capital']),industry_risk=str(winner['industry_known_line_risk'])),ensure_ascii=False))
