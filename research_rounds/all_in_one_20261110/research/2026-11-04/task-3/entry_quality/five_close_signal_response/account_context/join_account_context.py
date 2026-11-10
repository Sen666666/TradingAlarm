"""Pure join of968 already audited native/finance/A-C published close records.
No ledger re-estimation, signal recalculation, market-universe or candidate gate.
"""
from pathlib import Path
from decimal import Decimal as D,getcontext
from datetime import datetime,timezone
import json,gzip,hashlib,csv

getcontext().prec=60
O=Path(__file__).parent;E=O.parents[1]
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
F=E/'first_entry_regime/realized_feedback';SRC={};Z=D(0);TOL=D('1e-17')


def read(p,gz=False,lines=False):
 SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)


def save(name,x):
 with (O/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')


def close(a,b,key):assert abs(D(str(a))-D(str(b)))<TOL,(key,a,b)


SCOPES=[dict(id='2022_full',reference='2022_2024',start='2022-01-01',end='2022-12-31',expected_closes=242),
        dict(id='2024_Sep02_Nov29',reference='2022_2024',start='2024-09-02',end='2024-11-29'),
        dict(id='2025Jul01_2026Jun30_strong',reference='strong',start='2025-07-01',end='2026-06-30',expected_closes=242)]
save('PROTOCOL.json',dict(frozen_at=datetime.now(timezone.utc).isoformat(),scopes=SCOPES,
  operation='Pure exact-date join of existing published native CLOSE account contexts. No account/market signal/ledger run.',
  A='Prior/current21 original native CLOSE dates of actual sell.parts realized, including older-position sales. No AR.',
  C='Actual layers opened within prior/current21 original native CLOSE dates, all realized-to-now including partial if any. No AR. C sourced from already audited original timeline.',
  windows='A/C windows retain original full-account history before each finite scope start; no resetting at scope boundary. No new21/5 mapping computed.',
  publish_clock='Original native CLOSE15:10+08:00. Real financial sell.parts strictly earlier; raw original fast/breakout/on reflect original CLOSE risk_checkpoint.',
  universes='Account dates only. No stock-selection or market-signal cohort is constructed. No filtering dates by actual buys, holdings, ACT state or outcomes.',
  tails='No94-tail first market signal mapping here; parent will map independent root candidates.',
  new_accounts=0,new_signals=0,new_policies=0))
data={};checks={}
for ref,pair,finance in [('2022_2024',B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair',B/'risk_constraints/continuation2024_finance/PVR_NO_CONFIRMED60_DAILY.json'),
                       ('strong',B/'pvr_pool_feasibility/runs/2025_26/pair',B/'risk_constraints/absolute_loss_2022_2023/NO60_STRONG_DAILY.json')]:
 fin=read(finance);abc=read(F/(ref+'_DAILY_ABC.json'));native=read(pair/'daily.jsonl.gz',gz=True,lines=True);book=read(pair/'B.json.gz',gz=True)
 assert len(fin)==len(abc)==len(native)==(726 if ref=='2022_2024' else 242)
 abymap={x['decision_at']:x for x in abc}
 checkpoints={x['at']:x for x in book['audit'] if x['kind']=='risk_checkpoint'}
 assert len(checkpoints)==len(native)
 cumulative=Z;rr=[]
 for f,n in zip(fin,native):
  at=n['at'];day=at[:10];a=abymap[at];risk=checkpoints[at]
  assert day==f['day']==a['window_last']
  for fk,nk in [('NAV_end','nav'),('market_value','inventory'),('available_cash','available')]:close(f[fk],n[nk],(ref,day,fk))
  close(risk['nav'],n['nav'],(ref,day,'checkpoint NAV'))
  assert f['ACT_after_CLOSE']==n['on']==risk['on']
  cumulative+=D(f['realized_trade_net'])
  unreal=D(f['market_value'])-D(f['held_cost_basis'])
  # Reuse/check the old published accounting identity, never infer a missing leg.
  close(D(1000000)+cumulative+unreal+D(n['dividend_receivable']),n['nav'],(ref,day,'old published wealth bridge'))
  A=a['A_recent_actual_sell_realized'];C=a['C_recent_new_layers_realized'];opennew=a['B1_recent_new_still_held_excluded']
  row=dict(reference=ref,date=day,published_at=at,financial_event_cutoff='actual event timestamp strictly before published_at',
    original_account_origin=fin[0]['day'],original_starting_capital='1000000',
    A_window_first=a['window_first'],A_window_last=a['window_last'],A_native_observations=a['native_observations'],
    A_recent21_sell_realized=A['strict_realized'],A_state=A['state'],A_actual_sell_parts=A['actual_sell_parts'],
    A_gross_price_pnl=A['gross_price_pnl'],A_consumed_original_buyfee=A['consumed_buyfee'],A_actual_sellfee=A['actual_sellfee'],
    C_window_first=a['window_first'],C_window_last=a['window_last'],C_native_observations=a['native_observations'],
    C_recent21_new_layer_realized=C['strict_realized'],C_state=C['state'],C_actual_sell_parts=C['actual_sell_parts'],
    C_gross_price_pnl=C['gross_price_pnl'],C_consumed_original_buyfee=C['consumed_original_buyfee'],C_actual_sellfee=C['actual_sellfee'],
    C_recent_new_original_buycash=C['new_cohort_actual_buycash'],C_recent_new_layers=C['new_cohort_layers'],
    C_recent_new_unrealized_separate=C['current_unrealized_separate'],C_recent_new_AR_separate=C['recognized_dividend_AR_separate'],
    C_still_held_new_layers=opennew['layers'],C_still_held_new_original_buycash=opennew['original_buycash'],
    C_still_held_new_unrealized=opennew['unrealized'],
    actual_today_realized=f['realized_trade_net'],actual_cumulative_realized=cumulative,
    actual_today_unrealized_change=f['unrealized_change'],actual_today_AR_accrual=f['recognized_dividend'],
    actual_today_fees=f['actual_fees'],actual_today_buycash=f['actual_buy_cash'],actual_today_sell_net=f['actual_sell_net'],
    actual_today_buy_fills=f['buy_fills'],actual_today_sell_fills=f['sell_fills'],
    NAV_begin=f['NAV_begin'],NAV=f['NAV_end'],actual_today_wealth=f['wealth_change'],
    inventory_market_value=f['market_value'],remaining_buyfee_inclusive_cost_basis=f['held_cost_basis'],
    actual_current_unrealized=unreal,recognized_unpaid_dividend_AR=n['dividend_receivable'],
    exposure_percent=f['exposure_pct'],nominal_risk=f['nominal_risk'],nominal_risk_percent=f['nominal_risk_pct'],available_cash=f['available_cash'],
    original_ACT_at_OPEN=f['ACT_at_OPEN'],original_ACT_at_CLOSE=risk['on'],original_ACT_fast=risk['fast'],
    original_ACT_breakout=risk['breakout'],original_ACT_previous_fast=risk['previous_fast'],
    original_ACT_event=risk['event'],original_ACT_episode=risk['episode'],original_ACT_episode_drawdown=risk['episode_drawdown'],
    original_ACT_policy=risk['policy'],original_ACT_checkpoint_at=risk['at'])
  assert row['A_window_last']==day and row['C_window_last']==day and row['A_window_first']<=day
  rr.append(row)
 data[ref]=rr
 checks[ref]=dict(original_native_closes=len(rr),original_fast_breakout_available_for_all=True,exact_date_identity=True,
  old_native_finance_NAV_inventory_available_ACT_and_AR_bridge=True,no_published_account_reestimation=True)
out=[];scope_summary=[]
for s in SCOPES:
 rr=[dict(scope=s['id'],**x) for x in data[s['reference']] if s['start']<=x['date']<=s['end']]
 if 'expected_closes' in s:assert len(rr)==s['expected_closes']
 assert len({x['date'] for x in rr})==len(rr) and rr==sorted(rr,key=lambda x:x['date'])
 save(s['id']+'.json',rr);out.extend(rr)
 scope_summary.append(dict(scope=s['id'],reference=s['reference'],closes=len(rr),first_date=rr[0]['date'],last_date=rr[-1]['date'],
    no_buy_dates=sum(x['actual_today_buy_fills']==0 for x in rr),ACT_paused_CLOSE_dates=sum(not x['original_ACT_at_CLOSE'] for x in rr),
    zero_inventory_dates=sum(D(x['inventory_market_value'])==0 for x in rr),
    A_negative_dates=sum(x['A_state']=='negative' for x in rr),C_negative_dates=sum(x['C_state']=='negative' for x in rr),
    first_A_window_first=rr[0]['A_window_first'],first_C_window_first=rr[0]['C_window_first'],
    source_origin=rr[0]['original_account_origin'],actual_period_wealth=sum((D(x['actual_today_wealth']) for x in rr),Z)))
save('DAILY_ACCOUNT_CONTEXT.json',out)
with (O/'DAILY_ACCOUNT_CONTEXT.csv').open('x') as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
save('VALIDATION.json',dict(passed=True,joined_original968_closes=True,selected_closes=len(out),references=checks,scopes=scope_summary,
 no_market_universe_selection=True,no_market_cohort_constructed=True,no_actual_buy_date_filter=True,no94_tail_mapping=True,
 new_account_events=0,new_signals=0,new_ledger=False,limitations=['Current survivors/current sectors/development/daily execution proxy originals retained.',
 'No stock-level market cohort has been selected or measured here; account outcomes must not define market signal eligibility.',
 'Two independent original1m-start accounts are not stitched into one continuous path.',
 'A/C21 observations overlap; current figures are known at published native15:10close, not before the same-day OPEN.',
 'AR recognized but unpaid, sale net not guaranteed spendable cash; current unrealized is raw mark minus original remaining fee-inclusive basis.']))
SRC[str(Path(__file__))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
save('SOURCE_SHA256.json',SRC)
print(json.dumps(scope_summary,ensure_ascii=False,indent=2,default=str))
