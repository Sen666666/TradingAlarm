"""One saved-signal/risk/money join. No MA, price, account or ledger recomputation."""
from pathlib import Path
from decimal import Decimal as D,getcontext
import json,hashlib,datetime,collections
getcontext().prec=50
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');O=Path(__file__).resolve().parent
A=B/'ar6_native_feasibility/ma63_recovery_chain_v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
P=B/'risk_constraints/no60_continuation2023_finance/analysis/2022_2023/PVR_NO_CONFIRMED60/LAYERS.json'
E=B/'loss_correction/entry_risk_commitment_review/2022_2024_ENTRIES.json'
C=B/'pvr_pool_feasibility/market_phase_2022_2023/ALL_PERIODS.json'
assert (A/'DAILY.json').exists() and (A/'ALL_EPISODES.json').exists(),'shared original MA63 labels pending; no substitute/recompute'
daily=read(A/'DAILY.json');signals={r['day']:r for r in daily};episodes=read(A/'ALL_EPISODES.json');assert len(signals)==len(daily)==484
src=[P,E,C,A/'DAILY.json',A/'ALL_EPISODES.json',O/'PROTOCOL.txt',Path(__file__)]
save('INPUT_FREEZE.json',dict(before_join=True,time_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_sha256={str(p):sha(p) for p in src},common_cutoff='2023-12-29',no_new_MA_price_or_account=True))
entry={r['layer']:r for r in read(E)};parents=read(P);assert len(parents)==1557
rows=[]
for p in parents:
    x=dict(entry[p['layer']])
    for k in ['sid','cost','net','value','qty','closed']:assert x[k]==p[k],('2023prefix differs',p['layer'],k)
    assert p['qty']==0 and p['closed'][:10]<='2023-12-29'
    at=x['budget_order'].split('|')[1].replace('T',' ');assert at==x['decision_at'] and at[11:19]=='15:10:00'
    r=signals.get(at[:10]);assert r is None or r['decision_close']==at
    pos='UNKNOWN' if r is None else r['price_position'];slope='unknown' if r is None else r['ma63_slope_direction']
    assert pos in ['ABOVE','BELOW','EQUAL','UNKNOWN'] and slope in ['up','down','flat','unknown']
    x.update(benchmark_signal=None if r is None else r,benchmark_MA63_class=pos+'_'+slope,benchmark_position=pos,benchmark_slope=slope,benchmark_known=pos!='UNKNOWN' and slope!='unknown',benchmark_episode_id=None if r is None else r['episode_id'],strict_below_MA_and_down=pos=='BELOW' and slope=='down',original_money_cutoff='2023-12-29')
    rows.append(x)
def total(z,k):return sum((D(str(x[k])) for x in z),D(0))
def agg(z):
    known=[x for x in z if x.get('actual_initial_nominal_risk') is not None]
    return dict(layers=len(z),stocks=len({x['sid'] for x in z}),signal_known=sum(x['benchmark_known'] for x in z),signal_unknown=sum(not x['benchmark_known'] for x in z),original_cost=total(z,'cost'),original_gross_buy_notional=total(z,'cost')-total(z,'buy_fee'),original_net=total(z,'net'),original_positive_net=sum((D(x['net']) for x in z if D(x['net'])>0),D(0)),original_negative_net=sum((D(x['net']) for x in z if D(x['net'])<0),D(0)),positive_layers=sum(D(x['net'])>0 for x in z),negative_layers=sum(D(x['net'])<0 for x in z),strict_realized=total(z,'strict_realized'),open_unrealized=total(z,'open_unrealized'),recognized_dividend_AR=total(z,'recognized_dividend_AR'),buy_fee=total(z,'buy_fee'),sell_fee=total(z,'sell_fee'),initial_nominal_risk_known_layers=len(known),initial_nominal_risk_unknown_layers=len(z)-len(known),cumulative_initial_nominal_risk=sum((D(x['actual_initial_nominal_risk']) for x in known),D(0)))
classes=[p+'_'+s for p in ['ABOVE','BELOW','EQUAL','UNKNOWN'] for s in ['up','down','flat','unknown']]
def profile(z):return dict(all=agg(z),by_MA_position_slope={k:agg([x for x in z if x['benchmark_MA63_class']==k]) for k in classes},by_action={a:agg([x for x in z if x['action']==a]) for a in ['first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat']},by_role={r:agg([x for x in z if x['role']==r]) for r in ['core','mobile']},by_pool={p:agg([x for x in z if x['pool_at_fill']==p]) for p in ['probe','confirmed']})
bear=[x for x in rows if x['strict_below_MA_and_down']]
summary={'all1557':profile(rows),'strict_below_MA_and_down':profile(bear),'note':'all contributions original2023 cutoff, not MA-state/month period PnL or avoidable loss'}
months=[f'{y}-{m:02d}' for y in [2022,2023] for m in range(1,13)]
contexts={r['period']:r for r in read(C) if r['grain']=='month' and r['policy']=='NO60'};assert set(months)==set(contexts)
monthly=[]
for month in months:
    z=[x for x in rows if x['decision_at'].startswith(month)];f=[x for x in rows if x['opened'].startswith(month)];b=[x for x in z if x['strict_below_MA_and_down']];ctx=contexts[month]
    monthly.append(dict(month=month,decision_cohort=profile(z),decision_below_down=profile(b),actual_fill_cohort=agg(f),original_actual_month_trade_chain={k:ctx[k] for k in ['actual_buy_cash','actual_sell_net','actual_fees','buy_fills','sell_fills']},monthly_entry_net_not_monthly_NAV_PnL=True))
episode_results=[]
for ep in episodes:
    z=[x for x in rows if x['benchmark_episode_id']==ep['episode_id']];r=signals.get(ep['start_day']);episode_results.append(dict(original_episode=ep,true_upcross_at_start=bool(r and r['cross_event']=='UP_CROSS'),original_entry_cohort=profile(z),strict_below_down_entries=agg([x for x in z if x['strict_below_MA_and_down']]),zero_original_buys_preserved=not z))
winners=[x for x in bear if D(x['net'])>0]
save('ALL_1557_ROWS.json',rows);save('SUMMARY.json',summary);save('ALL_24_MONTHS.json',monthly);save('ALL_EPISODES.json',episode_results);save('BELOW_DOWN_ALL_ORIGINAL_POSITIVE_ROWS.json',winners)
assert sum(x['decision_cohort']['all']['layers'] for x in monthly)==1557
assert sum(x['original_entry_cohort']['all']['layers'] for x in episode_results)==1557
assert abs(agg(rows)['original_net']-(D('745426.9583780900535')-D('1000000')))<D('1e-20')
assert all(sha(Path(p))==h for p,h in read(O/'INPUT_FREEZE.json')['source_sha256'].items())
save('COMPLETED.json',dict(status='PASS_SAVED_MA63_BUY_CHAIN_ONLY',new_models=0,new_MA_or_prices=0,new_accounts=0,months=24,episodes=len(episode_results),true_upcrosses=sum(x['true_upcross_at_start'] for x in episode_results),layer_count=1557,source_post_exact=True,original2023cutoff_bridge_exact=True,all_bear_positive_rows=len(winners),not_period_PnL_or_avoidable_loss=True))
print(json.dumps({'all':summary['all1557']['all'],'below_down':summary['strict_below_MA_and_down'],'episodes':len(episode_results),'all_positive_bear_layers':len(winners),'output':str(O)},ensure_ascii=False,default=str,indent=2))
