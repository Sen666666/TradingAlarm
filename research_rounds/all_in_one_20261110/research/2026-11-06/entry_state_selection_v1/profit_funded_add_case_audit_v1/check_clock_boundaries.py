"""Small independent causal-factor / scenario-fee boundary supplement."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D
import importlib.util, json, gzip, hashlib, sys
import pandas as pd
O=Path(__file__).resolve().parent;R=O.parent
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
H=load('audit_arithmetic',O/'audit_original_noact.py')
FP=R/'account_comparison_continuous_v1/factors/continuous_factors.py'
F=load('factor_arithmetic_only',FP)
cf=json.loads((R/'mobile_first_probe_protection_v1/conditional_paths_v1/run/SOURCE_FREEZE.json').read_text())
rp=next(p for p in cf if p.endswith('/execution-rules-v2.json'));H.rules=json.loads(Path(rp).read_text())
rows=json.loads((O/'ADD_CLOCK_SNAPSHOTS.json').read_text());out=[];factor_cache={};sources={str(FP):H.sha(FP),str(rp):H.sha(rp),str(O/'ADD_CLOCK_SNAPSHOTS.json'):H.sha(O/'ADD_CLOCK_SNAPSHOTS.json')}
for r in rows:
 sid=r['sid'];d=r['at'][:10];at=r['at'];mark=D(r['mark_raw']);details=r['layer_details'];qsum=sum(x['qty']for x in details)
 flags=[x['layer_id']for x in details if D(x['floor_raw'])>=mark]
 groups=defaultdict(int)
 for x in details:groups[D(x['scenario_exit_raw_after_slippage'])]+=x['qty']
 separate=sum((D(x['scenario_sell_fee'])for x in details),D(0));grouped=sum((H.fee(sid,at,'sell',q,p)for p,q in groups.items()),D(0))
 factor_checked=None
 if r['clock']=='OPEN':
  rawp=H.RAW/f'bars/{sid}.parquet';ap=H.RAW/f'actions/{sid}.json';sources[str(rawp)]=H.sha(rawp);sources[str(ap)]=H.sha(ap)
  raw=pd.read_parquet(rawp);raw=raw[pd.to_datetime(raw.trade_date)<pd.Timestamp(d)].copy();actions=json.loads(ap.read_text())['events'];actions=[a for a in actions if a['effective_date']<=d]
  t=F.OpenFactorTimeline(raw,actions,end=d);v=t.factor(d);assert abs(v-D(r['factor']))<D('1e-12'),('prefix factor differs',sid,d,v,r['factor']);factor_checked=str(v)
 # Adding a layer to an existing equal-price hypothetical order has marginal
 # sell fee, not a second minimum. Publish this sensitivity; do not replace the
 # main explicitly independent-layer-order convention.
 q=int(r['new_quantity']);X=D(r['new_scenario_exit_price']);oldfee=H.fee(sid,at,'sell',groups.get(X,0),X)
 marginal=H.fee(sid,at,'sell',groups.get(X,0)+q,X)-oldfee
 combined_newrisk=D(r['new_scenario_price_loss'])+D(r['new_buy_fee'])+marginal
 old_floor_grouped=D(r['old_full_round_protection_net'])+separate-grouped
 out.append(dict(round_id=r['round_id'],sid=sid,new_layer_id=r['new_layer_id'],clock=r['clock'],at=at,known_open_at_or_below_old_floor=bool(flags)if r['clock']=='OPEN'else None,known_mark_at_or_below_old_floor=bool(flags),breached_old_layer_ids=flags,flags=['KNOWN_OPEN_BELOW_OR_AT_OLD_FLOOR']if flags and r['clock']=='OPEN'else [],floor_value_is_locked_or_available_profit=False,independent_floor_order_sell_fee=separate,same_floor_grouped_order_sell_fee=grouped,separate_fee_extra=separate-grouped,old_floor_scenario_net_grouped=old_floor_grouped,new_scenario_risk_standalone=D(r['new_signed_scenario_risk']),new_scenario_risk_equal_floor_marginal_fee=combined_newrisk,post_add_floor_net_same_floor_grouped=old_floor_grouped-combined_newrisk,strict_prefix_open_factor=factor_checked,current_or_future_OPEN_HLCV_used_in_factor=False,pre_add_realized=D(r['cumulative_realized_net_sales']),pre_add_dividend=D(r['booked_dividend_accrual']),pre_add_average_pool_K_equals_sum_layer_K='YES: no prior SELL in any selected round before its ADD; average-pool and layer cost have not diverged yet'))
H.table('CLOCK_BOUNDARY_FLAGS.csv',out);H.dump('CLOCK_BOUNDARY_FLAGS.json',out)
a=json.load(gzip.open(R/'act_only_ablation_continuous_v1/run/pair/NOACT.json.gz','rt'))
lids={r['new_layer_id']for r in rows};rounds=json.loads((O/'ROUND_SUMMARY.json').read_text());round_by={r['round_id']:r for r in rounds}
for r in rows:
 rr=round_by[r['round_id']]
 assert not any(t['side']=='sell'and t['security_id']==r['sid']and rr['opened']<=t['at']<=r['at']for t in a['trades'])
 assert D(r['cumulative_realized_net_sales'])==0 and D(r['booked_dividend_accrual'])==0
z=dict(passed=True,rows=len(out),OPEN_factor_verified_with_strict_prior_close_prefix=sum(x['strict_prefix_open_factor']is not None for x in out),OPEN_at_or_below_old_floor=sum(bool(x['known_open_at_or_below_old_floor'])for x in out),max_extra_fee_from_separate_layer_orders=max(x['separate_fee_extra']for x in out),OPEN_after_add_protection_negative_grouped=sum(x['clock']=='OPEN'and x['post_add_floor_net_same_floor_grouped']<0 for x in out),pre_add_no_prior_sale_cases_verified=len(rows),pre_add_no_booked_dividend_verified=len(rows),source_hashes=sources,not_a_new_policy_or_account=True)
H.dump('CLOCK_BOUNDARY_CHECKS.json',z);print(json.dumps(z,ensure_ascii=False,default=str))
