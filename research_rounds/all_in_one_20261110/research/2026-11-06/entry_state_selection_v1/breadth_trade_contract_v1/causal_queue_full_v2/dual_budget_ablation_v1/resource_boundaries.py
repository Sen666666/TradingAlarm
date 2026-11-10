from pathlib import Path
from decimal import Decimal as D
import pandas as pd,json
P=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/breadth_trade_contract_v1/causal_queue_full_v2/dual_budget_ablation_v1')
R=P.parents[2];U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
sn=json.loads((R/'early_sector_probe_boundary_v1/ORIGINAL_OPEN_RESOURCES.json').read_text());sn={r['day']:r for r in sn['rows']}
im={r['series']:r for r in json.loads((U/'INDUSTRY_MANIFEST.json').read_text())};states={}
a=pd.read_csv(P/'ALL_ADD_ADMISSIONS.csv');a=a[a.q.gt(0)];out=[]
for r in a.itertuples():
 sec=r.event_id.split('|')[-1]
 if sec not in states:
  zz=pd.read_parquet(im[sec]['refs']['state']);zz['day']=pd.to_datetime(zz['day']);states[sec]=zz.set_index('day')
 st=states[sec];sd=pd.Timestamp(r.signal_day);row=st.loc[sd]if sd in st.index else None
 cashneed=D(int(r.q))*D(str(r.buy_price))+D(str(r.buy_fee));s=sn.get(r.open_day)
 x=dict(event_id=r.event_id,sid=r.sid,signal_day=r.signal_day,open_day=r.open_day,q=r.q,cash_required=float(cashneed),original_market_stage=None if row is None else row.stage_name,original_attempt_id=None if row is None else row.attempt_id,real_shared_account='NOT_RECONSTRUCTED',original_pool_sector_account_risk='NOT_INTEGRATED_WITH_NEW_PATH',Tplus1='original_next_open_and_next_open_exit_clock_preserved',tradability='UNKNOWN_NOT_CONFIRMED_FILL')
 if s:
  free=D(s['balance_components']['available'])-D(s['decision_NAV_exact'])*D('.1')
  x.update(original_cash_snapshot='AVAILABLE_NOT_COUNTERFACTUAL_CASH',original_after_10pct_reserve_cash=float(free),original_cash_necessary_test='INSUFFICIENT'if cashneed>free else'SUFFICIENT_ONLY_FOR_OLD_SNAPSHOT')
 else:x.update(original_cash_snapshot='UNKNOWN_AFTER_ORIGINAL_ACCOUNT_END',original_cash_necessary_test='UNKNOWN')
 out.append(x)
z=pd.DataFrame(out);z.to_csv(P/'ADD_RESOURCE_BOUNDARIES.csv',index=False)
summary=dict(rows=len(z),cash_test_counts=z.original_cash_necessary_test.value_counts().to_dict(),stage_counts=z.original_market_stage.value_counts(dropna=False).to_dict(),scope='Old snapshot screen only, not actual cash of a shared counterfactual strategy. No historical cash inferred after source end.')
(P/'RESOURCE_BOUNDARY_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(summary)
