"""Three fixed single-order necessary examples through original market helpers.
One original stock source, no Account/Runner, no new quote or execution engine.
"""
from pathlib import Path
from types import SimpleNamespace
from decimal import Decimal as D
from datetime import datetime
import dataclasses,gzip,hashlib,json,sys
import pandas as pd

O=Path(__file__).resolve().parent;R=O.parent
M=Path('/Users/bytedance/Documents/ChatGPT/money')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
freeze=read(O/'THREE_TRUE_PVR_SAMPLES_FREEZE.json')
assert freeze['selection_frozen_before_sample_price_read']
samples=freeze['samples'];assert len(samples)==3 and {x['sid']for x in samples}=={'300085.SZ'}
sid='300085.SZ'
mp=M/'TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/manifest.json'
record=next(x for x in read(mp)['series']if x['series_id']==sid)
sm=next(x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')if x['symbol']==sid)
rulespath=M/'research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json'
protocolpath=M/'research_rounds/a-share-selection-e0-20261024/inputs-v2/economic-protocol.json'
fastpath=M/'research_rounds/temperature-sizing-20261026/code/fast_market.py'
cp=Path(sm['refs']['CP1']);fact=Path(sm['refs']['facts'])
receipt=R/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/stock-receipts'/f'{sid}.json'
daily=R/'market_gross_admission_native_v1/full-long-v1/pair/daily.jsonl.gz'
sourcepaths=[O/'THREE_TRUE_PVR_SAMPLES_FREEZE.json',mp,Path(record['raw']['path']),Path(record['adjustment']['actions']['path']),
    rulespath,protocolpath,fastpath,fastpath.with_name('common.py'),
    M/'research_rounds/ix-a-share-entry-20261025/code/multi_runner.py',
    M/'research_rounds/rs-h1-execution-20261025/code/sector_account.py',
    M/'research_rounds/rs-h1-execution-20261025/code/current_pool_bridge.py',
    M/'research_rounds/rs-h1-execution-20261025/code/market_rules.py',fact,cp,receipt,daily,Path(__file__)]
sources={str(p):sha(p)for p in sourcepaths}
assert sources[record['raw']['path']]==record['raw']['sha256']
assert sources[record['adjustment']['actions']['path']]==record['adjustment']['actions']['sha256']
assert sources[str(fact)]==sm['output_sha256'][str(fact)]
assert sources[str(cp)]==sm['output_sha256'][str(cp)]
(O/'THREE_EXAMPLES_INPUT_FREEZE.json').write_text(json.dumps(dict(before_original_market_constructor_and_sample_price_arithmetic=True,sources=sources),indent=2)+'\n')

# Literal original FastMarket and its original FrozenMarket identity comparison.
# Only the immutable one-stock record and original raw source are supplied.
sys.path.insert(0,str(fastpath.parent))
import fast_market as F
rules=read(rulespath);protocol=read(protocolpath)
bundle=SimpleNamespace(lines=(SimpleNamespace(security_id=sid,market='A'),),
    series={sid:SimpleNamespace(record=record)},manifest_path=mp)
market=F.FastMarket(bundle,rules,[],protocol)
facts=pd.read_parquet(fact,columns=['i_target','i_floor','factor','raw_close'])
cps=pd.read_parquet(cp,columns=['receipt','candidate'])
receipts=read(receipt);cash={}
with gzip.open(daily,'rt')as f:
    for line in f:
        row=json.loads(line)
        if row['at'][:10]in {x['day']for x in samples}:cash[row['at'][:10]]=row
result=[]
for q in samples:
    d,nd=q['day'],q['next_OPEN'];at=datetime.fromisoformat(nd+'T09:30:00+08:00');close=datetime.fromisoformat(d+'T15:10:00+08:00')
    r=dict(sample=q,decision_CLOSE=str(close),execution_OPEN=str(at),status='UNKNOWN',failures=[])
    try:
        a=facts.loc[pd.Timestamp(d)];z=cps.loc[pd.Timestamp(d)];sourcecash=cash[d]
        assert bool(a.i_target)and bool(z.receipt)
        cr=[x for x in receipts if x['confirmed_day']==d and x['receipt_id']==q['CP1_id']];assert len(cr)==1
        assert sourcecash['positions']=={} and sourcecash['pending_sells']==[] and sourcecash['pending_intents']==0
        mark=market.latest_mark(sid,close);assert mark.known_at<=close and mark.raw_price==D(str(a.raw_close))
        win=market.window(sid,at,'buy',1)
        if win is None:raise ValueError('original_native_window_absent')
        win.validate();qty=win.quantity.buy_minimum
        nav=D(sourcecash['nav']);available=D(sourcecash['available'])
        factor=D(str(facts.loc[pd.Timestamp(nd),'factor']));priorfactor=D(str(a.factor))
        actions=[x for x in market.actions.get(sid,[])if d<x['effective_date']<=nd]
        assert factor==priorfactor and not actions,'factor change/action timing requires separate proof: stop, no invented OPEN factor'
        floor_adj=max(D(str(a.i_floor)),D(str(z.candidate)));floor=floor_adj/factor
        gross=D(qty)*win.execution_price
        fees=win.fees.incremental('buy',gross,{},{},1,shares=qty,par_value=win.par_value)
        fee=sum(fees.values(),D(0));bnav=nav-fee
        nominal=D(qty)*max(D(0),win.execution_price-floor)
        budget=nav*D('.02');cap=win.quantity.buy_floor(int(budget/mark.raw_price))
        checks={
            'known_original_decision_mark':mark.known_at<=close,
            'original_observed_OPEN_positive':win.raw_open>0,
            'original_market_open':win.market_open is True,
            'original_HL_availability_buy_allowed':win.buy_allowed is True,
            'minimum_within_original_capacity':qty<=win.capacity_shares,
            'OPEN_strictly_above_original_floor':win.raw_open>floor,
            'floor_nonnegative_not_above_execution':D(0)<=floor<=win.execution_price,
            'minimum_within_CLOSE_nominal_quantity_cap':qty<=cap,
            'minimum_within_original_mobile2pct_target':gross<=budget,
            'cash_preserves_original10pct_NAV_buffer':gross+fee<=available-nav*D('.1'),
            'probe10pct_gross_necessary':gross<=D('.1')*bnav,
            'probe_halfpct_nominal_risk_necessary':nominal<=D('.005')*bnav,
            'sector_probe2pct_gross_necessary':gross<=D('.02')*bnav,
            'stock10pct_gross_necessary':gross<=D('.1')*nav,
        }
        nativebar=market.raw[sid].loc[pd.Timestamp(nd)]
        r.update(status='PASS_NECESSARY_ONLY'if all(checks.values())else'FAIL_NECESSARY',checks=checks,
            failures=[k for k,v in checks.items()if not v],original_window=dataclasses.asdict(win),
            original_decision_mark=dataclasses.asdict(mark),minimum_quantity=qty,
            original_CLOSE_NAV=nav,original_CLOSE_available=available,original_dividend_receivable=sourcecash['dividend_receivable'],
            original_I_floor_adjusted=D(str(a.i_floor)),original_CP1_candidate_adjusted=D(str(z.candidate)),floor_adjusted=floor_adj,
            unchanged_factor_known_before_OPEN=factor,floor_raw=floor,
            minimum_gross=gross,minimum_buy_fee=fee,minimum_fee_components=fees,minimum_cash=gross+fee,
            minimum_nominal_risk=nominal,fee_adjusted_reference_NAV=bnav,
            original_mobile_nominal_budget=budget,original_CLOSE_quantity_cap=cap,
            native_HLV_postcheck=dict(raw_high=float(nativebar.high),raw_low=float(nativebar.low),raw_volume=float(nativebar.volume),
                reject_flat_day=protocol['daily_execution']['A']['reject_flat_day']),
            postcheck_scope='Original same-day H/L/V/validity is ex-post execution proxy, not information used to generate the prior-CLOSE certificate or choose sample/fees/floors. Actual intraday limit/halt/queue availability UNKNOWN.',
            source_actions_in_gap=actions)
    except (ValueError,KeyError,AssertionError)as e:
        r.update(status='UNKNOWN',unknown=repr(e))
    result.append(r)
    print(d,sid,r['status'],r['failures'],flush=True)
for p,h in sources.items():assert sha(p)==h
out=dict(scope='Same fixed three CLOSE/mobile samples, original source market/window/mark/fee/quantity helpers; independent single-order necessary examples, NOT sequential candidate positions or native orders',
    rows=result,original_window_vs_original_FrozenMarket_identity_checks=market.window_identity_checks,
    accounts_constructed=0,runners_constructed=0,new_indicators=0,new_orders=0,new_financial_events=0,
    counterfactual_executable_capital='UNKNOWN',candidate_profit_or_recoverable_return='UNKNOWN',
    sources=sources,design_conflicts_resolved=False,
    population_PVR_unknown='600027.SH Sep24 score absent retained explicitly; no zero imputation, no native-priority claim')
p=O/'THREE_EXAMPLES_RESULTS.json';assert not p.exists();p.write_text(json.dumps(out,indent=2,ensure_ascii=False,default=str)+'\n')
print('WINDOW_IDENTITY_CHECKS',market.window_identity_checks,'OUTPUT_SHA',sha(p))
