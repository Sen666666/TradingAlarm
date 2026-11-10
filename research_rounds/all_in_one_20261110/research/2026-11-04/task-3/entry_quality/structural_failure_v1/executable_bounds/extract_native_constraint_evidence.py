"""Read-only native rule/actual example extraction. No account/model execution."""
from pathlib import Path
from collections import Counter
import sys,inspect,hashlib,json,gzip
O=Path(__file__).resolve().parent;E=O.parents[1];sys.path.insert(0,str(E/'trend_exit_controls_v1'))
import load_inputs as V
J,A=V.J,V.A
SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p)]=sha(p)
 with (gzip.open(p,'rt')if gz else p.open())as f:return [json.loads(x)for x in f]if lines else json.load(f)
def save(name,x):
 p=O/name
 with p.open('x')as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def function(fn):
 p=inspect.getsourcefile(fn);exists=bool(p and Path(p).is_file())
 if exists:SRC[str(Path(p).resolve())]=sha(p)
 return dict(qualified_name=fn.__qualname__,module=fn.__module__,source_file=p,source_file_exists=exists,first_line=fn.__code__.co_firstlineno,code_sha256=V.IO._code_fingerprint(fn.__code__),source=inspect.getsource(fn)if exists else None)

def main():
 scope=read(O.parent/'DIAGNOSTIC_SCOPE_FREEZE.json')
 assert scope['main_reference'].startswith('Original No60') and scope['no_full_account_yet']
 methods={
 'native_planning':J.Runner.planning,'native_opening':J.Runner.opening,
 'next_clock_and_I_packet':J.C.E.Facts.packet,'last_observation_row':J.C.E.Facts.row,
 'core_resize':J.LR.resize_core,'protection_risk':J.LR.protection_risk,'open_preview':J.LR.preview,
 'native_activation':J.C.activate,'real_known_open_reserve':J.LR.Account.reserve_quantity,
 'joint_reserve_bridge':J.Account.reserve_quantity,'joint_real_buy_bridge':J.Account.fill_buy,
 'joint_real_sell_bridge':J.Account.fill_exit,'layer_sell_union':J.BP.Account.sell,
 'layer_exit_part_allocation':J.BP.Account.fill_exit,'layer_corporate_action_allocation':J.BP.Account.split,
 'real_fill_buy':J.BP.L.SectorAccount.fill_buy,'real_fill_exit':J.BP.L.SectorAccount.fill_exit,
 'real_fee_incremental':J.BP.L.SectorAccount._fee,'real_fee_memory':J.BP.L.SectorAccount._remember_fees,
 'buy_lease_and_release':J.BP.L.SectorAccount.expire_day_buys,'request_exit_latch':J.BP.L.SectorAccount.request_exit,
 'execution_eligibility':J.BP.L.SectorAccount._eligible_event,'event_consumption':J.BP.L.SectorAccount._consume_event,
 'real_split_and_bonus':J.BP.L.SectorAccount.split,'market_fill_window':J.C.E.FastMarket.window,
 'market_slow_fill_identity':J.C.E.FastMarket.__mro__[1].window,
 'ACT_state_transition':J.M.E.risk_policy.advance,'ACT_checkpoint':J.M.E.risk_policy.step,
 'corporate_actions':J.Runner._actions,'dividend_payment':J.Runner._payments}
 evidence={k:function(f)for k,f in methods.items()}
 assert A.Runner.route is A.P.ROUTES[True]
 assert 'account_risk'not in A.P.NEW_ROUTE and "else .60"not in A.P.NEW_ROUTE
 assert "if pool=='probe' and pc+cap>.10*nav"in A.P.NEW_ROUTE
 evidence['effective_No60_route']=dict(source=A.P.NEW_ROUTE,source_sha256=hashlib.sha256(A.P.NEW_ROUTE.encode()).hexdigest(),code_sha256=V.IO._code_fingerprint(A.Runner.route.__code__),declared_code_filename=A.Runner.route.__code__.co_filename,account_3pct_gate=False,confirmed_pool_60pct_gate=False)
 evidence['effective_No60_budget']=dict(source_sha256=hashlib.sha256(A.P.NEW_MODEL.encode()).hexdigest(),model_source=A.P.NEW_MODEL,creator_file=str(Path(A.P.__file__).resolve()))
 for p in [Path(A.__file__),Path(A.P.__file__),Path(__file__),E/'trend_exit_controls_v1/load_inputs.py']:SRC[str(p.resolve())]=sha(p)
 proto=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/economic-protocol.json')
 rules=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
 assert proto['daily_execution']['A']['slippage_bps']=='5' and proto['participation_rate']=='.01'
 assert proto['sellable_lag_sessions']['A']==1 and proto['settlement_lag_sessions']['A']==0
 pair=E/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair'
 book=read(pair/'B.json.gz',True);funding=read(pair/'funding.jsonl.gz',True,True)
 counts=Counter(x['result']for x in funding)
 buys={(r['security_id'],r['at'],'core'if r['kind']=='core'else'mobile')for r in book['trades']if r['side']=='buy'}
 unfilled=[r for r in funding if r['result']=='reserved'and(r['sid'],r['at'],r['role'])not in buys]
 first=unfilled[0]if unfilled else None
 unfilled_evidence=None
 if first:
  rows=[x for x in book['audit']if x.get('sid')==first['sid'] and (x.get('at','')[:10]==first['at'][:10])]
  unfilled_evidence=dict(funding=first,same_day_native_audit=rows,interpretation='Reservation is not a fill. Keep its explicit cash/fee lock until the native cancel/expiry acknowledgement; do not recycle an unfilled order during the same funding pass.')
 chains=read(E/'dec2022_authorization_v1/account_comparison/results_v1/BASELINE_FOUR_STOCK_CLOCK_CHAINS.json')
 timing=[]
 for chain in chains:
  if chain['sid']=='000029.SZ':
   for r in chain['actual_entries']:
    if r['opened'][:7]=='2022-12':timing.append({k:r[k]for k in ['sid','layer_in_this_book','role','decision_at','opened','closed','initial_qty','actual_sale_parts']})
 partial_path=E/'dec2022_authorization_v1/independent_review/H2_STRONG_PARTIAL_BOUNDARY.json';partial=read(partial_path)
 cases=dict(reference='Original No60 BASELINE full2022-24 unless explicitly labelled otherwise',funding_result_counts=dict(counts),selected_real_rejections={key:next((r for r in funding if r['result']==key),None)for key in ['missing_open','open_at_or_below_protection','open_minimum_exceeds_frozen_contract']},reserved_without_same_open_actual_buy_count=len(unfilled),one_reserved_unfilled_example=unfilled_evidence,original_next_open_CP_chain=timing,additional_native_odd_lot_boundary=dict(not_original_baseline=True,arm=partial['arm'],window=partial['window'],source=str(partial_path),rows=partial['rows'],interpretation='Existing separately audited P_ONLY example illustrates the SAME native partial/bonus/odd-lot mechanics, not a No60-baseline occurrence or performance claim.'),new_financial_accounts=0,new_events=0)
 save('NATIVE_RULE_EXAMPLES.json',cases)
 save('SOURCE_EVIDENCE.json',dict(functions=evidence,economic_protocol=proto,execution_rule_top_level_fields=list(rules),source_sha256=SRC,no_new_financial_accounts=True,no_native_source_modified=True,original_No60_reference=True))
 print(json.dumps(dict(status='EXTRACTED_NATIVE_RULES_AND_ORIGINAL_BOOK_EXAMPLES',funding_reserved=counts['reserved'],actual_buy_fills=len(buys),reserved_without_buy=len(unfilled),source_files=len(SRC),new_financial_accounts=0),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
