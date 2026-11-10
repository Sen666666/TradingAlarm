"""Saved-book arithmetic + selected frozen raw bars; zero trading objects/runs."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict, Counter
import json, hashlib, time, gzip
import pandas as pd

O=Path(__file__).resolve().parent
SHA={}
def bind(p):
    p=Path(p);SHA[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')

start=time.monotonic();bind(__file__)
post=read(O/'ALL_POSTPEAK_NEW_LAYERS.json')
P=O.parents[1]/'new_price_trend_v1/funding/runs/long_OFF/pair'
def gzload(p,lines=False):
    with gzip.open(bind(p),'rt')as f:return list(map(json.loads,f))if lines else json.load(f)
b=gzload(P/'B.json.gz');funding=gzload(P/'funding.jsonl.gz',True);opp=gzload(P/'opportunities.jsonl.gz',True)
filled=[t for t in b['trades']if t['side']=='buy'and t['at'][:10]=='2024-10-10'];assert len(filled)==16
decision=next(d for d in b['decisions']if d['at'][:10]=='2024-10-09')
actual_sids={t['security_id']for t in filled}
four={'300085.SZ','300339.SZ','301236.SZ','688593.SH'}
save('OCT9_10_ACTUAL_ADMISSION_EVIDENCE.json',dict(scope='Only saved native records. Exact gate union is not chronological first cause. All four core entries rejected at sizing despite Q=true; actual mobile reservations use confirmed pool.',signal_CLOSE=dict(at=decision['at'],nav=decision['nav'],ACT_on=decision['on'],actual_next_OPEN_filled_intents=[i for i in decision['intents']if i['sid']in actual_sids]),sixteen_actual_buy_fills=filled,four_stock_opportunities=[r for r in opp if r.get('sid')in four and r['day']=='2024-10-09'],four_stock_funding=[r for r in funding if r.get('sid')in four and r['at'][:10]in['2024-10-09','2024-10-10']],four_stock_reserve_and_fill_journal=[r for r in b['journal']if r.get('sid')in four and r.get('at','')[:10]=='2024-10-10'],four_stock_original_audit=[r for r in b['audit']if r.get('sid')in four and r.get('at','')[:10]=='2024-10-10'and r.get('kind')in['reserve','lot_risk_funded']]))
by_month=defaultdict(list)
for r in post:by_month[r['opened'][:7]].append(r)
months=[]
for m,rs in sorted(by_month.items()):
    v=dict(entry_month=m,layers=len(rs),stocks=len({r['sid']for r in rs}),buy_cash=sum((D(r['entry_cash'])for r in rs),D(0)),terminal_lifecycle_net=sum((D(r['lifecycle_net'])for r in rs),D(0)),categories=dict(Counter(r['category']for r in rs)),positive=sum(D(r['lifecycle_net'])>0 for r in rs),negative=sum(D(r['lifecycle_net'])<0 for r in rs))
    v['by_category']=[dict(category=c,layers=len(cr),terminal_lifecycle_net=sum((D(r['lifecycle_net'])for r in cr),D(0)))for c in sorted({r['category']for r in rs})if(cr:=[r for r in rs if r['category']==c])]
    v['largest_losses']=sorted(rs,key=lambda r:D(r['lifecycle_net']))[:5];months.append(v)
assert sum((v['terminal_lifecycle_net']for v in months),D(0))==sum((D(r['lifecycle_net'])for r in post),D(0))
save('POSTPEAK_ENTRY_MONTH_COHORTS.json',dict(scope='Grouped by actual entry month; terminal lifecycle cash+recognized dividend, NOT calendar-month return or avoidable loss.',months=months))

manifest=read('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/manifest.json')
lookup={s['series_id']:s for s in manifest['series']}
facts=read(O/'SELECTED_CHAIN_CAUSAL_FACTS.json');selected={r['layer']:r for r in facts};rows=[];raw_evidence=[]
for sid in ['300085.SZ','300339.SZ','301236.SZ','688593.SH','002181.SZ','002491.SZ']:
    p=bind(lookup[sid]['raw']['path']);assert SHA[str(p)]==lookup[sid]['raw']['sha256']
    f=pd.read_parquet(p);f=f.set_index(pd.to_datetime(f.trade_date)).sort_index()
    days=['2024-10-09','2024-10-10','2024-10-11','2024-10-14']if sid[:3]not in ['002']else['2024-12-23','2024-12-24','2024-12-25']
    bars=[]
    for day in days:
        d=pd.Timestamp(day);r=f.loc[d];j=f.index.get_loc(d);prev=f.iloc[j-1]
        bars.append(dict(day=day,previous_trade_date=str(f.index[j-1].date()),previous_close=str(prev.close),open=str(r.open),high=str(r.high),low=str(r.low),close=str(r.close),volume=str(r.volume),flat_day=bool(r.high<=r.low)))
    raw_evidence.append(dict(sid=sid,path=str(p),sha256=SHA[str(p)],bars=bars))
    for layer,x in selected.items():
        if x['sid']!=sid:continue
        t=x['entry'];rs=next(v for v in post if v['layer']==layer);entryday=t['at'][:10]
        pts={v['day']:v for v in x['points']};factor=D(pts[entryday]['facts']['factor']);floor=D(t['floor'])/factor;q=D(t['shares']);sell=rs['actual_sell_records'][0];sellbar=next(z for z in bars if z['day']==sell['at'][:10]);sig=D(pts['2024-10-09']['facts']['raw_close']);risk=q*(D(t['price'])-floor)
        out=dict(layer=layer,sid=sid,name=rs['name'],role_kind=t['kind'],signal_at=t['signal_at'],entry_at=t['at'],signal_raw_close=sig,actual_raw_entry_open=t['raw_open'],entry_fill_price=t['price'],open_gap_vs_signal_close_pct=(D(t['raw_open'])/sig-1)*100,entry_factor=factor,entry_protection_adjusted=t['floor'],entry_protection_raw=floor,qty=t['shares'],price_distance_risk_excluding_fees=risk,first_exit=x['first_exit'],actual_sell_at=sell['at'],actual_raw_sell_open=sell['raw_open'],actual_sell_fill_price=sell['price'],sell_open_gap_vs_previous_close_pct=(D(sell['raw_open'])/D(sellbar['previous_close'])-1)*100,terminal_lifecycle_net=rs['lifecycle_net'],loss_over_entry_price_distance_risk=-D(rs['lifecycle_net'])/risk)
        out['close_line_checks']=[dict(day=p['day'],raw_close=p['facts']['raw_close'],factor=p['facts']['factor'],adjusted_close=p['facts']['close'],live_adjusted_floor=p['live_layer_at_CLOSE']['floor']if p['live_layer_at_CLOSE']else None,raw_equivalent_floor=D(p['live_layer_at_CLOSE']['floor'])/D(p['facts']['factor'])if p['live_layer_at_CLOSE']else None,i_target=p['facts']['i_target'],i_buy=p['facts']['i_buy'],g_grade=p['facts']['g_grade'])for p in x['points']]
        rows.append(out)
assert len(rows)==4
save('FOUR_OCT10_LOSS_CAUSAL_CHECKS.json',dict(scope='Observed actual fills; nominal price-distance risk is not a guaranteed stop execution or an avoidable-loss estimate. Raw OHLC is a daily execution proxy, not real queue confirmation.',chains=rows))
save('SELECTED_RAW_EXECUTION_BARS.json',raw_evidence)

CW=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
MW=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
code=[
('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py','11-40','Effective original No60 wires derived no-confirmed60 budget/route, original opening and ranked original planning.'),
('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/component.py','17-34','Derived model removes only three confirmed60 predicates from original no-account model/route; probe10% remains.'),
(CW/'account-risk-ablation-20261031/route_without_account_check.py','1-28','Industry/fresh CP/dated minimum grid and funding checks; cash10%, probe capital/risk, sector capital/risk1%, stock10%; effective No60 confirmed60 check removed. Sorted failure union is not chronological first blocker.'),
(CW/'account-risk-ablation-20261031/model_without_account_check.py','64-94,236-238','Shared gross-loss accounting. record_only neither cancels nor blocks for exhaustion; no original account3% risk gate.'),
(CW/'case-stage-ledger-20261031/v3/joint_v3.py','16,213-259,302-324','20k shared budget record_only; CLOSE ACT/I/CP, CORE/MOBILE proposals; nextOPEN exits before funding, actual OPEN protection/fees/grid/revalidation then execution proxy after all reservations.'),
(CW/'pvr-slot1-native-readiness-20261101/native_rank.py','47-91,115-120','PVR ranks original unique-stock slots; eligibility/protection/execution retained.'),
(MW/'lot-risk-allocation-20261029/code/study.py','16-31,42-66,93-103','CORE .25% risk resize only; MOBILE retains original 2% nominal initial budget. Actual open must exceed floor; frozen contract, shares grid, fee reserve. Mobile bypass of core resize is original design, not routing bypass.'),
(MW/'actual-risk-recovery-20261027/code/engine.py','25-47','I_target maps stock trend, exact-day I_buy maps original buy event; market sessions set nextOPEN. Mobile continuing still requires S0 eligibility.'),
(MW/'actual-risk-recovery-20261027/code/risk_policy.py','8-29','ACT20 episode-peak >=20% CLOSE drawdown pauses; nextOPEN exit, breakout+flat required to resume. Single down day does not imply pause.'),
(MW/'rs-h1-execution-20261025/code/sector_stock_admission.py','185-220','S0 ready/fresh/common/buy/cap>10bn/I/sector/RS checks; unknown is not permission.'),
(MW/'temperature-sizing-20261026/code/fast_market.py','45-67','Dated session/rule/availability, valid HLV, 20 prior positive-volume capacity, flatday buy/sell exclusion, OPEN slippage; daily proxy is not actual limit queue.'),
(MW/'ix-a-share-entry-20261025/code/multi_runner.py','250-310','Lag counts actual subsequent sessions; external explicit limit branch is not conservative HLV proxy.'),
(MW/'rs-h1-execution-20261025/code/sector_account.py','688-797','Inventory sellable-at check, quantity/capacity/fees checks and FIFO exit.'),
(MW/'probe-pyramid-pilot-20261029/code/pilot.py','59-103','Actual layer fills, CORE epoch consumption, FIFO exits and dividend attribution.')]
for p,lines,meaning in code:bind(p)
save('CODE_CONDITIONS.json',[dict(path=str(Path(p)),lines=lines,meaning=meaning,sha256=SHA[str(Path(p))])for p,lines,meaning in code])
save('CAUSAL_SOURCE_SHA256.json',SHA)
save('CAUSAL_SCOPE.json',dict(no_Account_Runner_Market_RiskBook_constructed=True,no_new_backtest=True,source_objects='Existing book/layer summaries and selected frozen raw parquet bars only',runtime_seconds=time.monotonic()-start,all_postpeak_month_counts=303,four_loss_chains_checked=4))
for r in rows:print(r['name'],r['entry_protection_raw'],r['price_distance_risk_excluding_fees'],r['terminal_lifecycle_net'],r['loss_over_entry_price_distance_risk'],r['open_gap_vs_signal_close_pct'],r['sell_open_gap_vs_previous_close_pct'])
