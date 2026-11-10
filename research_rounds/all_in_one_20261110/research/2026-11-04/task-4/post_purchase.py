from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json,gzip,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;T=O.parent/'task'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
L=T/'loss_correction/no60_behavior_v1';src={}
def bind(p):
 p=Path(p);src[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
bind(__file__);bind(O/'POST_PURCHASE_PROTOCOL.txt')
a=read(L/'PVR_NO60-SEMICONDUCTOR_ACCEPTED_LIFECYCLES.json')
summary=read(L/'SEMICONDUCTOR_HOLD_EXIT_REENTRY_SUMMARY.json')['PVR_NO60']['all_actual_layers'];lm={x['layer']:x for x in summary}
funnel=read(L/'PVR_NO60-SEMICONDUCTOR_FUNNEL.json')['all_market_receipts']
stock={x['sid']:x for x in read(O/'SEMICONDUCTOR_ALL126_COMPARISON.json') if x['policy']=='PVR_NO60'}
old={x['sid'] for x in read(O/'SEMICONDUCTOR_ALL126_COMPARISON.json') if x['policy']=='PVR_BASELINE' and x['actual_layers']}
sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
frames={s:pd.read_parquet(bind(sm[s]['refs']['facts']),columns=['close','raw_close','factor']) for s in {x['sid'] for x in a}}
path=T/'pvr_pool_feasibility/runs/2025_26/pair/daily.jsonl.gz'
with gzip.open(bind(path),'rt') as f:daily=[json.loads(x) for x in f]
daily={x['at'][:10]:x for x in daily};days=sorted(daily)
rows=[]
for x in a:
 sid=x['sid'];r=lm[x['layer']];f=frames[sid];fill=x['actual_fill'];entry=fill['at'][:10]
 p0=D(str(f.loc[:'2025-12-31'].close.iloc[-1]));pend=D(str(f.loc[:'2026-06-30'].close.iloc[-1]))
 actual_economic=D(fill['price'])*D(x['entry_factor_known_corporate_action_units'])
 q=[z for z in funnel if z['sid']==sid];first=q[0]['signal_day'] if q else None
 closed=r['closed'];nextq=[z for z in q if closed and z['signal_day']>=closed]
 # A layer close is not necessarily a stock-flat event; expose the distinction.
 stockflat=bool(closed and not daily[closed]['positions'].get(sid,0))
 z=dict(r,halfyear_stock_price_return_pct=stock[sid]['H1_price_return_pct'],stock_was_funded_baseline=sid in old,
    before_actual_buy_price_change_since_2025end_pct=(actual_economic/p0-1)*100,
    hindsight_price_change_actual_buy_toJun30_pct=(pend/actual_economic-1)*100,
    first_833_market_receipt=first,first_833_to_actual_buy_market_observations=days.index(entry)-days.index(first) if first else None,
    first_833_categories_before_this_buy=dict(Counter(z['category'] for z in q if z['signal_day']<entry)),
    actual_stock_flat_after_this_layer_close=stockflat,
    later_833_receipts_if_stock_flat=len(nextq) if stockflat else None,
    later_833_categories_if_stock_flat=dict(Counter(z['category'] for z in nextq)) if stockflat else None,
    terminal_price_label_is_not_trade_PnL=True)
 rows.append(z)
save('POST_PURCHASE_ALL25_PATHS.json',rows)
stockrows=[]
for sid in sorted(frames):
 rs=[x for x in rows if x['sid']==sid];s=stock[sid]
 stockrows.append(dict(sid=sid,name=s['name'],stock_was_funded_baseline=sid in old,H1_stock_price_return_pct=s['H1_price_return_pct'],
    actual_layers=len(rs),actual_first_buy=min(x['opened'] for x in rs),actual_last_buy=max(x['opened'] for x in rs),
    actual_buy_cost=sum((D(x['buy_cost']) for x in rs),D(0)),actual_net=sum((D(x['net']) for x in rs),D(0)),
    actual_closed_negative_layers=sum(x['closed_net_negative'] for x in rs),still_open_layers=sum(x['quantity']>0 for x in rs),
    first_actual_buy_preceded_by_price_change_pct=min(rs,key=lambda x:x['opened'])['before_actual_buy_price_change_since_2025end_pct'],
    paths=rs))
save('POST_PURCHASE_ALL18_STOCKS.json',stockrows)
new=[x for x in rows if not x['stock_was_funded_baseline']]
groups={}
for name,rs in [('all',rows),('new7_stocks_all_layers',new),('H1_stock_doubled',[x for x in rows if float(x['halfyear_stock_price_return_pct'])>=100])]:
 groups[name]=dict(stocks=len({x['sid'] for x in rs}),layers=len(rs),cost=sum((D(x['buy_cost']) for x in rs),D(0)),
    actual_net=sum((D(x['net']) for x in rs),D(0)),closed_negative_layers=sum(x['closed_net_negative'] for x in rs),
    negative_no_profitable_close_layers=sum(x['closed_net_negative'] and not x['ever_close_above_actual_fill'] for x in rs),
    negative_earlier_profitable_close_layers=sum(x['closed_net_negative'] and x['ever_close_above_actual_fill'] for x in rs),
    actual_entry_actions=dict(Counter(x['action'] for x in rs)),
    original_exit_request_reasons=dict(Counter(z for x in rs for z in x['actual_exit_reasons'])))
save('POST_PURCHASE_SUMMARY.json',groups);save('POST_PURCHASE_SOURCE_SHA256.json',src)
print(json.dumps(groups,ensure_ascii=False,indent=2,default=str))
print(json.dumps([{k:v for k,v in x.items() if k!='paths'} for x in stockrows if not x['stock_was_funded_baseline']],ensure_ascii=False,indent=2,default=str))
