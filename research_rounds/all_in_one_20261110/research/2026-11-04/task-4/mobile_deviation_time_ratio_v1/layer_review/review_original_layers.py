"""Saved CSV scalar division plus original closed-layer reconciliation only."""
import csv
import gzip
import hashlib
import json
from collections import Counter
from decimal import Decimal, localcontext
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
SOURCE=ROOT/'mobile_trend_measurements_v1/MOBILE_SIGNAL_METRICS_AND_ORIGINAL_ACTIONS.csv'
SIGNALS=list(csv.DictReader(SOURCE.open()))
D=lambda x:Decimal(str(x))
def dump(name,x):
    (OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def csvsave(name,rows):
    with (OUT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

paths={name:ROOT/f'new_price_trend_v1/funding/runs/{name}/pair/B.json.gz' for name in ['long_OFF','strong_OFF']}
books={}
for name,p in paths.items():
    with gzip.open(p,'rt') as f:books[name]=json.load(f)
scalars=[];layers=[];source_layers=[]
for r in SIGNALS:
    deviation=D(r['close_deviation_ema20_pct']);slope=D(r['ema20_five_observation_slope_pct_per_observation'])
    with localcontext() as ctx:
        ctx.prec=40
        ratio=deviation/slope if slope else None
    scalar=dict(sid=r['sid'],name=r['name'],signal_day=r['date'],
                signal_CLOSE_at=r['date']+' 15:10:00+08:00',
                deviation_EMA20_pct=deviation,slope_EMA20_pct_per_observation=slope,
                R_price_observations=ratio,denominator_exactly_zero=slope==0,
                near_zero_threshold='PARENT_POLICY_NOT_REDEFINED_HERE',
                next_original_OPEN=r['next_original_OPEN'],
                original_next_OPEN_status=r['original_mobile_next_OPEN_status'],
                original_next_OPEN_funding_results=r['original_mobile_next_OPEN_funding_results'],
                original_filled_shares=int(r['original_mobile_filled_shares']))
    scalars.append(scalar)
    if not scalar['original_filled_shares']:continue
    run='strong_OFF' if r['sid']=='000547.SZ' else 'long_OFF';b=books[run]
    buys=[t for t in b['trades'] if t['security_id']==r['sid'] and t['side']=='buy' and t.get('kind')=='add' and t['signal_at']==scalar['signal_CLOSE_at'] and t['at']==r['next_original_OPEN']]
    assert sum(t['shares'] for t in buys)==scalar['original_filled_shares']
    for buy in buys:
        layer=next(x for x in b['layers'] if x['id']==buy['layer'])
        meta=b['metadata'][str(layer['id'])]
        assert meta['role']=='mobile' and layer['qty']==0 and layer['closed'] is not None
        allbuys=[t for t in b['trades'] if t['side']=='buy' and t.get('layer')==layer['id']]
        assert len(allbuys)==1
        parts=[dict(sell_at=t['at'],sell_receipt_id=t['receipt_id'],part=p) for t in b['trades'] if t['side']=='sell' for p in t.get('parts',[]) if p['layer']==layer['id']]
        cost=D(buy['gross_cny'])+D(buy['fees_cny'])
        sale_net=sum((D(p['part']['net_cash']) for p in parts),D(0))
        net=D(layer['cash'])+D(layer['dividend'])
        assert sale_net-cost+D(layer['dividend'])==net
        assert sum(p['part']['shares'] for p in parts)==buy['shares']
        row=dict(**scalar,original_account_run=run,original_layer_id=layer['id'],
                 original_opened=layer['opened'],original_closed=layer['closed'],
                 original_initial_qty=layer['initial_qty'],original_terminal_qty=layer['qty'],
                 original_actual_buy_qty=buy['shares'],original_actual_buy_price=buy['price'],
                 original_actual_buy_gross=buy['gross_cny'],original_actual_buy_fee=buy['fees_cny'],
                 original_buy_cash_cost=cost,original_actual_net_sale_cash=sale_net,
                 original_native_layer_cash=layer['cash'],original_dividend=layer['dividend'],
                 original_closed_lifecycle_net=net,net_sign='positive' if net>0 else 'negative' if net<0 else 'zero',
                 original_lifecycle_net_per_buy_cost_pct=100*net/cost,
                 layer_id_selection='All actual Mobile fills whose original signal is in fixed 59-signal source, before examining outcome',
                 not_calendar_year_return=True,not_counterfactual_deleted_trade_return=True)
        layers.append(row)
        source_layers.append(dict(original_account_run=run,original_layer=layer,original_metadata=meta,original_buy=buy,original_sell_parts=parts))

assert len(SIGNALS)==59 and len(layers)==19
assert len({(r['original_account_run'],r['original_layer_id']) for r in layers})==19
csvsave('ALL_59_INDEPENDENT_SCALAR_R.csv',scalars)
csvsave('ALL_19_ORIGINAL_MOBILE_LAYERS.csv',layers)
dump('ALL_19_ORIGINAL_MOBILE_LAYERS.json',layers)
dump('ORIGINAL_LAYER_RECORDS.json',source_layers)
rejected=[r for r in scalars if r['original_next_OPEN_status']=='ORIGINAL_MOBILE_OPEN_REJECTED']
csvsave('ALL_38_ORIGINAL_REJECTED_SIGNALS_NO_RETURN_LABEL.csv',rejected)
positive=[r for r in layers if r['original_closed_lifecycle_net']>0]
negative=[r for r in layers if r['original_closed_lifecycle_net']<0]
pairs=[]
for loss in negative:
    gain=min(positive,key=lambda g:abs(g['R_price_observations']-loss['R_price_observations']))
    pairs.append(dict(absolute_R_gap=abs(gain['R_price_observations']-loss['R_price_observations']),
                      negative=dict(sid=loss['sid'],signal_day=loss['signal_day'],layer=loss['original_layer_id'],R=loss['R_price_observations'],net=loss['original_closed_lifecycle_net']),
                      positive=dict(sid=gain['sid'],signal_day=gain['signal_day'],layer=gain['original_layer_id'],R=gain['R_price_observations'],net=gain['original_closed_lifecycle_net'])))
pairs.sort(key=lambda x:x['absolute_R_gap'])
dump('OPPOSITE_NET_NEAREST_R_EXAMPLES.json',pairs)
summary=dict(signals=len(scalars),actual_closed_mobile_layers=len(layers),
             signal_action_counts=dict(Counter(r['original_next_OPEN_status'] for r in scalars)),
             positive_net_layers=len(positive),negative_net_layers=len(negative),zero_net_layers=sum(r['original_closed_lifecycle_net']==0 for r in layers),
             all_59_R_signs=dict(Counter('positive' if r['R_price_observations']>0 else 'negative' if r['R_price_observations']<0 else 'zero' for r in scalars if r['R_price_observations'] is not None)),
             minimum_absolute_saved_slope=min(abs(r['slope_EMA20_pct_per_observation']) for r in scalars),
             positive_net_R_min=min(r['R_price_observations'] for r in positive),positive_net_R_max=max(r['R_price_observations'] for r in positive),
             negative_net_R_min=min(r['R_price_observations'] for r in negative),negative_net_R_max=max(r['R_price_observations'] for r in negative),
             all_dividends_zero=all(D(r['original_dividend'])==0 for r in layers),
             source_closed_layer_cash_reconciliation_all_exact=True,
             formula='R = saved close_deviation_ema20_pct / saved ema20_five_observation_slope_pct_per_observation, signed, no threshold or abs transform',
             forbidden_inference='No threshold tuning, deleted-order PnL, replacement portfolio, causal strategy effect or claim of full-year account return',
             model_account_backtest_or_indicator_engine_calls=0)
dump('COUNTS_AND_SCOPE.json',summary)
sources=[SOURCE,*paths.values(),ROOT/'mobile_trend_measurements_v1/FROZEN_DEFINITIONS.txt']
dump('SOURCE_SHA256.json',[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sources])
print(json.dumps(summary,ensure_ascii=False,default=str))
print(json.dumps(pairs[:3],ensure_ascii=False,default=str))
