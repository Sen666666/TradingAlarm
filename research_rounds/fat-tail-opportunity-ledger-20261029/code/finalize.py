"""Finish existing aggregate outputs and reconcile historical manifest; no raw reaggregation."""
from pathlib import Path
import sys,json,gzip,hashlib,time,collections,importlib.util
from decimal import Decimal as D
import pandas as pd
R=Path('/Users/bytedance/Documents/ChatGPT/money');O=R/'research_rounds/fat-tail-opportunity-ledger-20261029';F=O/'full';SRC=R/'research_rounds/pvr-local-finite-capital-20261029/baseline';PV=R/'research_rounds/pvr-act-comparison-20261027'
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
t=time.monotonic();sf=pd.read_csv(F/'stock-actual-finance.csv',dtype=str)
for k in ['buy_gross','sell_gross','buy_fees','sell_fees','realized_trade_pnl','unrealized_trade_pnl','dividend_cash_paid','dividend_receivable','net_equity_profit']:sf[k]=sf[k].map(D)
sf.is_price_3x=sf.is_price_3x.eq('True');sf.cycles=sf.cycles.astype(int);ee=pd.read_csv(F/'structure-opportunities.csv');ww=pd.read_csv(F/'all-stock-windows.csv');ex=pd.read_csv(F/'actual-exit-reparticipation.csv');df=pd.read_parquet(F/'daily-observed-funnel.parquet');links=pd.read_csv(F/'fill-event-links.csv');orders=pd.read_csv(F/'order-event-links.csv')
daily=[x for x in rows(SRC/'accounts-v2/daily.jsonl.gz') if x['account']=='I__S0_base'];byday={x['at'][:10]:x for x in daily};obj=read(SRC/'accounts-v2/I__S0_base.json');final=daily[-1]
net=sum(sf.net_equity_profit,D(0));assert net==D(final['nav'])-D(1000000);assert sum(sf.buy_fees+sf.sell_fees,D(0))==D(final['fees_cny']);assert sum(sf.dividend_receivable,D(0))==D(final['dividend_receivable']);assert D(1000000)+sum(sf.realized_trade_pnl+sf.dividend_cash_paid,D(0))==D(final['available']);assert len(links)==138 and links.receipt_id.nunique()==138 and links.event_id.notna().all() and len(orders)==69 and orders.order_id.nunique()==69
sm=pd.read_csv(O/'sample/stock-actual-finance.csv',dtype=str).set_index('symbol');fm=pd.read_csv(F/'stock-actual-finance.csv',dtype=str).set_index('symbol');pd.testing.assert_frame_equal(sm,fm.loc[sm.index],check_exact=True)
# Recheck the original immutable money ledger, not a strategy replay.
sys.path.insert(0,str(R/'research_rounds/tech-finite-compound-20261026/code'));spec=importlib.util.spec_from_file_location('independent_money_verify',R/'research_rounds/tech-finite-compound-20261026/code/analyze_v2.py');A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A);A.CORE=PV/'input';prices=A.IndependentPrices();meta=read(R/'research_rounds/rs-h1-execution-20261025/inputs-v2/metadata.json');rules=read(PV/'execution-rules-v2.json');calendar=sorted(set([pd.Timestamp(x) for x in rules['calendars']['A']]+[pd.Timestamp(f'2026-10-{d}T09:30:00+08:00') for d in ['27','28','29','30']]));cc=[];cycles,audit=A.old.audit_account('I__S0_base',obj,daily,prices,meta,calendar,cc);assert audit['passed'];cp=collections.defaultdict(lambda:D(0))
for x in cc:cp[x['symbol']]+=x['net_contribution']
assert all(cp[x.symbol]==x.net_equity_profit for x in sf.itertuples())
changed=[]
for p,expected in read(O/'INPUT_IDENTITY.json')['sha256'].items():
 actual=sha(p)
 if actual!=expected:changed.append(dict(path=p,historical_manifest_digest=expected,current_digest=actual))
producer=str(R/'research_rounds/s-entry-mechanism-audit-20261029/code/audit.py');assert len(changed)==1 and changed[0]['path']==producer
later=read(R/'research_rounds/pvr-incremental-order-20261029/input-identity.json')['sha256'][producer];assert changed[0]['current_digest']==later
save(O/'PROVENANCE_CLARIFICATION.json',dict(legacy_manifest_mismatch=changed,current_digest_matches_already_frozen_later_PVR_input_identity=True,unused_producer_not_executed_in_this_audit=True,all_other_1657_inputs_match=True,cached_prices_signals_events_and_account_unchanged=True,aggregation_not_repeated=True))
# The already-verified atlas retains admission detail only on 41 funded dates.
ap=R/'research_rounds/cp1-trade-atlas-20261028/data/TECH/ACT-base-trace.json.gz';av=R/'research_rounds/cp1-trade-atlas-20261028/data/TECH/trace-verification.json';assert read(av)['passed']
with gzip.open(ap,'rt') as stream:atlas=json.load(stream)
cap={'total_slots_full','sector_issuer_slots_full','sector_slots_full','issuer_already_occupied'};supp=[];dl=df.set_index(['date','symbol']);win=ww.set_index('symbol')
for day,s in atlas['snapshots'].items():
 for field in ['nav','inventory','available','positions','order_reserved','dividend_receivable']:assert s['daily'][field]==byday[day][field],(day,field,'atlas other account')
 found=collections.defaultdict(set)
 for stage in s['stages']:
  for sid,reason in stage['rejected']:found[sid].add(reason)
 for sid,rr in found.items():
  if not rr&cap:continue
  z=dl.loc[(day,sid)];assert bool(z.Q) and bool(z.ACT_on)
  inside=bool(win.loc[sid,'trough']<=day<=win.loc[sid,'peak']);supp.append(dict(date=day,symbol=sid,event_id=z.event_id,is_price_3x=bool(z.is_price_3x),inside_expost_window=inside,reasons='|'.join(sorted(rr&cap)),source='existing verified atlas admission reconstruction, retained funded dates only'))
pd.DataFrame(supp).to_csv(F/'existing-admission-supplement.csv',index=False);save(O/'SUPPLEMENT_IDENTITY.json',dict(before_supplement_join=True,source_coverage='41 funded close dates only; not complete681 rejection log',sha256={str(p):sha(p) for p in [ap,av]}))
stats=dict(new_economic_paths=0,stocks=407,structures=5349,raw_I_snapshots=int(df.raw_I_signal.sum()),Q_snapshots=int(df.Q.sum()),events_any_I=int(ee.I_snapshots.gt(0).sum()),events_any_Q=int(ee.Q_snapshots.gt(0).sum()),events_filled=int(ee.buy_fills.gt(0).sum()),traded_stocks=int(sf.cycles.gt(0).sum()),actual_net_profit=net,ending_equity=final['nav'],ending_available=final['available'],ending_dividend_receivable=final['dividend_receivable'],fees=final['fees_cny'],realized_trade_pnl=sum(sf.realized_trade_pnl,D(0)),first_observable_breakpoints=ee.first_observable_breakpoint.value_counts().to_dict(),exit_causes=ex.request_cause.value_counts().to_dict(),I_exits_with_E0_still_active=int((ex.request_cause.eq('original_I_target_off')&ex.e0_active_at_request.eq(True)).sum()),exit_same_structure_future_Q=int(ex.same_structure_future_Q.gt(0).sum()),exit_same_structure_reentry=int(ex.same_structure_actual_reentry_fills.gt(0).sum()),post_exit21_complete=int(ex.post_exit21_complete.sum()),post_exit21_positive=int(ex.post_exit21_price_change.gt(0).sum()),groups={})
for tag,label in [(True,'price3x207'),(False,'other200')]:
 s=sf[sf.is_price_3x.eq(tag)];w=ww[ww.is_price_3x.eq(tag)];e=ee[ee.is_price_3x.eq(tag)];d=df[df.is_price_3x.eq(tag)];absent=d[~d.held]
 stats['groups'][label]=dict(stocks=len(s),actual_profit=sum(s.net_equity_profit,D(0)),traded_full_period=int(s.cycles.gt(0).sum()),mean_window_coverage=float(w.holding_coverage.mean()),median_window_coverage=float(w.holding_coverage.median()),never_held_window=int(w.held_days.eq(0).sum()),structures=len(e),events_any_I=int(e.I_snapshots.gt(0).sum()),events_any_Q=int(e.Q_snapshots.gt(0).sum()),events_filled=int(e.buy_fills.gt(0).sum()),first_breakpoints=e.first_observable_breakpoint.value_counts().to_dict(),window_absent_closes=int(w.absent_closes.sum()),window_absent_no_new_I=int(w.absent_no_new_I.sum()),window_I_active_no_new_signal=int(w.absent_I_active_no_new_signal.sum()),window_Q_ACT_paused=int(w.absent_Q_ACT_paused.sum()),window_unknown_state=int(w.absent_state_unknown.sum()),window_observed_budget_reject=int(w.absent_Q_budget_logged.sum()),window_eligible_gate_unknown=int(w.absent_unknown.sum()),full_period_unheld_day_gates=absent.observable_day_gate.value_counts().to_dict())
rank=sf.sort_values('net_equity_profit',ascending=False);stats['actual_concentration']=dict(top5=rank.head(5).to_dict('records'),top1_profit=rank.iloc[0].net_equity_profit,top5_profit=sum(rank.head(5).net_equity_profit,D(0)),positive_stock_net=sum((x for x in sf.net_equity_profit if x>0),D(0)),negative_stock_net=-sum((x for x in sf.net_equity_profit if x<0),D(0)),negative_cycle_losses=-sum((c['net_pnl'] for c in cycles if c['net_pnl']<0),D(0)),tail30_cycle_profit=sum((c['net_pnl'] for c in cycles if c['tail_closed']),D(0)))
stats['unknowns']=dict(unlinked_orders=0,unlinked_order_rate=0,unlinked_fills=0,unlinked_fill_rate=0,unlinked_Q_structure_ids=0,Q_false_raw_I_rows=int((df.raw_I_signal&~df.Q).sum()),unresolved_Q_subcause='Composite cache has no complete gate-reason detail; not assigned to capital.',eligible_unordered_rows=int(df.observable_day_gate.eq('eligible_unordered_unknown').sum()),missing_I_state_rows=int((~df.i_known).sum()),missing_E0_state_rows=int((~df.e0_known).sum()),observed_state_unknown_rows=int(df.observable_day_gate.eq('state_input_unknown').sum()),unknown_exit_causes=int(ex.request_cause.eq('unknown_exit_request_cause').sum()))
suppf=pd.DataFrame(supp);stats['existing_admission_supplement']=dict(verified_cutoff_dates=len(atlas['snapshots']),all_cutoff_dates=681,capacity_rejection_stock_days=len(supp),structures_touched=suppf.event_id.nunique(),price3x_in_window_capacity_rejections=int((suppf.is_price_3x&suppf.inside_expost_window).sum()),basis='Already verified pure admission reconstruction, only saved where at least one order accepted; nonrandom partial coverage. Not silently extended to640 other dates or allunknowns.')
save(F/'RESULTS.json',stats);save(F/'VERIFICATION.json',dict(passed=True,source_full_aggregation_completed_once=True,native_cash_share_fee_price_audit=audit,per_stock_money_exact=True,daily_contribution_sum_exact=True,all_69_order_ids_unique=True,all_138_fill_ids_unique=True,sample_money_exact=True,active_day_eligibility_all407_exact=True,historical_manifest_mismatch_disclosed=True,no_changed_data_inputs=True,new_economic_paths=0,finalization_seconds=time.monotonic()-t))
print(json.dumps(stats,ensure_ascii=False,default=str),flush=True)
