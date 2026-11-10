#!/usr/bin/env python3
"""Read-only arithmetic audit of already sealed seed-round ADD fills. No strategy import/run."""
import json, gzip, pathlib, hashlib, csv, collections, datetime
from decimal import Decimal as D, getcontext
getcontext().prec=40
ROOT=pathlib.Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
RUN=ROOT/"mobile_first_probe_protection_v1/conditional_paths_v1/run"
REPORT=RUN.parent/"audit_outcomes_v1/REPORT_v2.md"
OUT=ROOT/"conditional_profit_add_risk_audit_v1"
OUT.mkdir(exist_ok=True)
ZERO=D(0); SLIP=D(".9995")
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,obj):
 (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str)+"\n")
def table(name,rows):
 if not rows:return
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with (OUT/name).open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False,default=str) if isinstance(v,(list,dict)) else v for k,v in r.items()})
def fee_parts(g,day,side):
 if not g:return {}
 p={"net_brokerage":max(D(5),g*D(".0002")),
 "handling":g*D(".0000341" if day>="2023-08-28" else ".0000487"),
 "regulatory":g*D(".00002"),"transfer":g*D(".00001" if day>="2022-04-29" else ".00002")}
 if side=="sell":p["stamp_duty"]=g*D(".0005" if day>="2023-08-28" else ".001")
 return p
def fee(g,day,side):return sum(fee_parts(g,day,side).values(),ZERO)
def close_enough(a,b):return abs(D(a)-D(b))<D(".00000001")
declared=json.loads((RUN/"OUTPUT_HASHES.json").read_text())
source_before={str(RUN/n):sha(RUN/n) for n in declared}
assert all(source_before[str(RUN/n)]==h for n,h in declared.items())
source_before[str(RUN/"OUTPUT_HASHES.json")]=sha(RUN/"OUTPUT_HASHES.json")
source_before[str(REPORT)]=sha(REPORT)
# Freeze every existing seed ADD identity before financial comparisons. CP seed is kind=add, so exclude original signal/order.
paths=[]; frozen=[]; cases=[]
for path in sorted(RUN.glob("*/PATH.json.gz")):
 x=json.loads(gzip.decompress(path.read_bytes()));seed=next((r for r in x["rounds"] if r["origin"]=="SEED_MOBILE"),None)
 ids=set(seed["layers"]) if seed else set()
 adds=[t for t in x["trades"] if t["side"]=="buy" and t.get("layer") in ids and t.get("kind")=="add" and t["signal_at"]!=seed["signal"]]
 paths.append((path,x,seed,adds))
 for t in adds:
  frozen.append({"case_id":x["case"]["round_id"],"name":x["case"]["name"],"arm":x["summary"]["arm"],"round":seed["round"],"layer":t["layer"],"signal_at":t["signal_at"],"fill_at":t["at"],"receipt_id":t["receipt_id"],"q":t["shares"],"source":str(path),"source_sha256":sha(path)})
 cases.append({"case_id":x["case"]["round_id"],"name":x["case"]["name"],"arm":x["summary"]["arm"],"seed_present":bool(seed),"seed_round":seed["round"] if seed else None,"seed_original_signal":seed["signal"] if seed else None,"seed_existing_status":seed["status"] if seed else "NO_SEED_ENTRY","seed_existing_net":seed["net"] if seed else None,"subsequent_seed_add_count":len(adds),"add_layers":[t["layer"] for t in adds],"add_fill_days":[t["at"][:10] for t in adds]})
assert len(paths)==28 and len({x["case"]["round_id"] for _,x,_,_ in paths})==14
dump("SOURCE_HASHES_BEFORE.json",source_before);dump("FROZEN_SEED_ADD_UNIVERSE.json",frozen);table("FROZEN_SEED_ADD_UNIVERSE.csv",frozen);dump("FROZEN_CASES.json",cases)
fee_checks=[];snapshot_rows=[];layer_rows=[];add_rows=[];bridge_rows=[];case_metrics=[]
for path,x,seed,adds in paths:
 for a in x["audit"]:
  if a["kind"]=="fill":
   t=a["receipt"];parts=fee_parts(D(t["gross_cny"]),t["at"][:10],t["side"])
   assert all(close_enough(v,a["fee_components"].get(k,0)) for k,v in parts.items())
   assert close_enough(sum(parts.values(),ZERO),t["fees_cny"])
   fee_checks.append({"source":path.parent.name,"receipt":t["receipt_id"],"day":t["at"][:10],"fee_schedule":a["fee_schedule"],"fee":t["fees_cny"]})
 if not seed:continue
 ids=set(seed["layers"]);seed_trades=[t for t in x["trades"] if (t["side"]=="buy" and t["layer"] in ids) or (t["side"]=="sell" and any(p["layer"] in ids for p in t["parts"]))]
 # Seed paths contain no split. Keep the unsupported boundary explicit rather than inventing a cost allocation.
 assert not [a for a in x["audit"] if a["kind"]=="split" and seed["opened"]<=a["at"]<=(seed["closed"] or x["daily"][-1]["at"])]
 seed_end=seed["closed"] or x["daily"][-1]["at"]
 divs=[a["receivable"] for a in x["audit"] if a["kind"]=="dividend_accrual" and seed["opened"]<=a["receivable"]["ex_at"]<=seed_end]
 def ledger(at):
  poolk=ZERO;qty=0;cash=ZERO;buycost=ZERO;salenet=ZERO;layers={}
  for t in seed_trades:
   if t["at"]>=at:continue
   if t["side"]=="buy":
    cost=D(t["gross_cny"])+D(t["fees_cny"]);cash-=cost;buycost+=cost;poolk+=cost;qty+=t["shares"]
    l=layers.setdefault(t["layer"],{"qty":0,"remaining_cost":ZERO,"realized":ZERO,"cash":ZERO,"kind":t["kind"],"original":t["signal_at"]==seed["signal"]})
    l["qty"]+=t["shares"];l["remaining_cost"]+=cost;l["cash"]-=cost
   else:
    for p in t["parts"]:
     if p["layer"] not in ids:continue
     l=layers[p["layer"]];n=p["shares"];net=D(p["net_cash"])
     removed=l["remaining_cost"]*D(n)/D(l["qty"]);l["remaining_cost"]-=removed;l["qty"]-=n;l["realized"]+=net-removed;l["cash"]+=net
     poolk-=poolk*D(n)/D(qty);qty-=n;cash+=net;salenet+=net
  accrual=sum((D(v["net_local"]) for v in divs if v["ex_at"]<at),ZERO)
  paid=sum((D(v["net_local"]) for v in divs if v.get("paid_at") and v["paid_at"]<at),ZERO)
  layerk=sum((l["remaining_cost"] for l in layers.values()),ZERO)
  assert close_enough(cash+layerk,sum((l["realized"] for l in layers.values()),ZERO))
  return {"qty":qty,"K_pool":poolk,"K_layer":layerk,"trade_cash":cash,"buy_cost":buycost,"sale_net":salenet,"dividend_accrued":accrual,"dividend_paid_recorded":paid,"dividend_receivable":accrual-paid,"realized_pool":cash+poolk,"realized_layer":cash+layerk,"realized_ADD_layer":sum((l["realized"] for l in layers.values() if not l["original"]),ZERO),"layers":layers}
 # End-of-round cash bridge; terminal mark is the sealed raw native mark, not an invented closing sale.
 endstate=ledger("9999")
 endingmark=D(seed["terminal_mark"]);endingdiv=sum((D(v["net_local"]) for v in divs),ZERO)
 assert close_enough(endstate["trade_cash"]+endingdiv+endingmark,seed["net"])
 bridge_rows.append({"case_id":x["case"]["round_id"],"name":x["case"]["name"],"arm":x["summary"]["arm"],"round":seed["round"],"cumulative_buy_fee_cost":endstate["buy_cost"],"cumulative_net_sales":endstate["sale_net"],"trade_cash":endstate["trade_cash"],"dividend_accrued":endingdiv,"dividend_paid_recorded":sum((D(v["net_local"]) for v in divs if v.get("paid_at")),ZERO),"dividend_actual_payment":"UNKNOWN_NO_PAYMENT_RECORD","terminal_native_raw_mark":endingmark,"remaining_qty":endstate["qty"],"net_reconstructed":endstate["trade_cash"]+endingdiv+endingmark,"net_sealed":seed["net"],"existing_status":seed["status"],"check":"PASS"})
 for t in adds:
  ident={"case_id":x["case"]["round_id"],"name":x["case"]["name"],"arm":x["summary"]["arm"],"seed_round":seed["round"],"add_layer":t["layer"],"signal_at":t["signal_at"],"fill_at":t["at"],"receipt_id":t["receipt_id"],"seed_existing_status":seed["status"],"seed_existing_net":seed["net"]}
  signal=next(d for d in x["daily"] if d["at"]==t["signal_at"])
  prev=[d for d in x["daily"] if d["at"]<t["at"]][-1]
  fillday=next(d for d in x["daily"] if d["at"][:10]==t["at"][:10])
  intent=next(i for d in x["decisions"] if d["at"]==t["signal_at"] for i in d["intents"] if i["kind"]=="add")
  assert intent["floor"]==t["floor"]
  assert prev["at"]==signal["at"] # No expired or deferred fill here.
  assert prev["close_factor"]==fillday["close_factor"] # Opening raw-coordinate conversion does not need execution-day close.
  assert not any(z["side"]=="sell" and z["at"]==t["at"] for z in seed_trades)
  gate=next(g for g in x["profit_gate"] if g["at"]==t["at"] and g["kind"]=="add")
  orderid=next(j["budget_order"] for j in x["journal"] if j["kind"]=="real_buy_fill" and j["layer"]==t["layer"])
  recorded_order=x["ending_budget"]["orders"][orderid]
  snapshots=[]
  for phase,at,mark,q,p in [("t_close",signal["at"],D(signal["raw_close_today"]),int(intent["cap"]),D(signal["raw_close_today"])*D("1.0005")),("OPEN_before_ADD",t["at"],D(t["raw_open"]),t["shares"],D(t["price"]))]:
   state=ledger(at);factor=D(signal["close_factor"]);q=D(q);day=at[:10]
   assert state["qty"]>0
   assert close_enough(state["K_pool"],signal["remaining_stock_cost"])
   assert state["qty"]==sum(l["qty"] for l in signal["layers"])
   stockgross=D(state["qty"])*mark*SLIP;V=stockgross-fee(stockgross,day,"sell")
   U=V-state["K_pool"];Ulayer=V-state["K_layer"];Uround=state["trade_cash"]+V+state["dividend_accrued"]
   groups=collections.defaultdict(lambda:{"q":0,"layers":[]})
   detail=[]
   for l in signal["layers"]:
    if l["id"] not in ids or not l["qty"]:continue
    rawfloor=D(l["floor"])/factor;g=D(l["qty"])*rawfloor*SLIP
    assert state["layers"][l["id"]]["qty"]==l["qty"]
    detail.append({"layer":l["id"],"kind":l["kind"],"q":l["qty"],"floor_adjusted":l["floor"],"factor":factor,"floor_raw":rawfloor,"protection_gross":g,"isolated_sell_fee":fee(g,day,"sell"),"isolated_protection_net":g-fee(g,day,"sell"),"remaining_layer_buy_fee_cost":state["layers"][l["id"]]["remaining_cost"],"original_seed":state["layers"][l["id"]]["original"],"floor_observed_at":signal["at"],"mark_raw_below_floor":mark<rawfloor})
    groups[rawfloor]["q"]+=l["qty"];groups[rawfloor]["layers"].append(l["id"])
   Vprotect_isolated=sum((l["isolated_protection_net"] for l in detail),ZERO)
   # Main scenario charges one order per distinct frozen floor. Isolated-layer variant is reported too.
   Vprotect=sum((D(g["q"])*floor*SLIP-fee(D(g["q"])*floor*SLIP,day,"sell") for floor,g in groups.items()),ZERO)
   S=D(t["floor"])/factor;gstop=q*S*SLIP;buyg=q*p;buyfee=fee(buyg,day,"buy");sellfee=fee(gstop,day,"sell");newrisk=buyg+buyfee-gstop+sellfee
   if phase=="OPEN_before_ADD":
    assert close_enough(buyfee,t["fees_cny"]) and close_enough(S,recorded_order["floor"])
    assert close_enough(V,gate["net_liquidation"]) and close_enough(state["K_pool"],gate["cost"]) and state["qty"]==gate["qty"]
   oldprotect_round=state["trade_cash"]+Vprotect+state["dividend_accrued"]
   after_round=oldprotect_round-newrisk
   # Marginal ADD has its own sell order; cannot assume it shares an old lot's future execution.
   row={**ident,"phase":phase,"asof":at,"mark_raw":mark,"existing_qty":state["qty"],"candidate_qty":int(q),"candidate_qty_basis":"FROZEN_SIGNAL_CAP" if phase=="t_close" else "ACTUAL_OPEN_FILL","candidate_buy_p_with_5bp":p,"candidate_S_raw":S,"candidate_floor_adjusted":t["floor"],"factor_known_t":factor,"candidate_buy_gross":buyg,"candidate_buy_fee":buyfee,"candidate_buy_fee_cost":buyg+buyfee,"candidate_protection_sell_gross":gstop,"candidate_protection_sell_fee":sellfee,"candidate_new_plan_risk":newrisk,"V_inventory_net_liquidation":V,"K_remaining_pool_buy_fee":state["K_pool"],"K_remaining_layer_buy_fee":state["K_layer"],"U_inventory_pool":U,"U_inventory_layer":Ulayer,"realized_pool_net":state["realized_pool"],"realized_layer_net":state["realized_layer"],"realized_ADD_layer_net":state["realized_ADD_layer"],"dividend_accrued":state["dividend_accrued"],"dividend_receivable":state["dividend_receivable"],"dividend_paid_recorded":state["dividend_paid_recorded"],"dividend_actual_payment":"UNKNOWN_NO_PAYMENT_RECORD","U_round_confirmed_paid":Uround-state["dividend_accrued"]+state["dividend_paid_recorded"],"U_round_ex_dividend":Uround-state["dividend_accrued"],"U_round_accrual":Uround,"old_protection_value_grouped_floor":Vprotect,"old_protection_value_separate_layer":Vprotect_isolated,"old_protection_inventory_pool":Vprotect-state["K_pool"],"old_protection_round_accrual":oldprotect_round,"old_protection_round_ex_dividend":oldprotect_round-state["dividend_accrued"],"mark_to_protection_giveback":V-Vprotect,"old_protection_round_confirmed_paid":oldprotect_round-state["dividend_accrued"]+state["dividend_paid_recorded"],"after_ADD_protection_round_confirmed_paid":after_round-state["dividend_accrued"]+state["dividend_paid_recorded"],"after_ADD_protection_round_accrual":after_round,"after_ADD_protection_round_ex_dividend":after_round-state["dividend_accrued"],"after_ADD_protection_round_separate_layers":state["trade_cash"]+Vprotect_isolated+state["dividend_accrued"]-newrisk,"newrisk_gt_U_inventory_pool":newrisk>U,"newrisk_gt_U_round_accrual":newrisk>Uround,"newrisk_gt_old_protection_round":newrisk>oldprotect_round,"has_prior_realized_ADD_loss":state["realized_ADD_layer"]<0,"mark_below_any_old_floor":any(l["mark_raw_below_floor"] for l in detail),"mark_below_old_floor_layers":[l["layer"] for l in detail if l["mark_raw_below_floor"]],"inventory_one_order_sell_fee":fee(stockgross,day,"sell"),"inventory_separate_layers_sell_fees":sum((fee(D(l["q"])*mark*SLIP,day,"sell") for l in detail),ZERO),"inventory_separate_layers_minus_one_order_fee":sum((fee(D(l["q"])*mark*SLIP,day,"sell") for l in detail),ZERO)-fee(stockgross,day,"sell"),"newrisk_gt_U_round_confirmed_paid":newrisk>Uround-state["dividend_accrued"]+state["dividend_paid_recorded"],"old_floor_groups":[{"floor":floor,**g} for floor,g in groups.items()],"candidate_fee_components_buy":fee_parts(buyg,day,"buy"),"candidate_fee_components_protection_sell":fee_parts(gstop,day,"sell"),"source":str(path)}
   assert close_enough(Uround,U+state["realized_pool"]+state["dividend_accrued"])
   assert close_enough(Uround,Ulayer+state["realized_layer"]+state["dividend_accrued"])
   assert close_enough(after_round,Uround-row["mark_to_protection_giveback"]-newrisk)
   snapshot_rows.append(row);snapshots.append(row)
   layer_rows.extend([{**ident,"phase":phase,"asof":at,**l} for l in detail])
  actual=snapshots[1];closedlayer=next(l for l in x["layers"] if l["id"]==t["layer"])
  add_rows.append({**ident,"q_signal_cap":intent["cap"],"q_OPEN_fill":t["shares"],"buy_fee_cost":D(t["gross_cny"])+D(t["fees_cny"]),"new_plan_risk_OPEN":actual["candidate_new_plan_risk"],"U_inventory_pool_OPEN":actual["U_inventory_pool"],"U_round_accrual_OPEN":actual["U_round_accrual"],"U_round_confirmed_paid_OPEN":actual["U_round_confirmed_paid"],"mark_below_any_old_floor":actual["mark_below_any_old_floor"],"mark_below_old_floor_layers":actual["mark_below_old_floor_layers"],"prior_realized_ADD_net":actual["realized_ADD_layer_net"],"old_protection_round_OPEN":actual["old_protection_round_accrual"],"mark_to_protection_giveback_OPEN":actual["mark_to_protection_giveback"],"after_protection_round_OPEN":actual["after_ADD_protection_round_accrual"],"sealed_ADD_layer_trade_cash":closedlayer["cash"],"sealed_ADD_layer_dividend":closedlayer["dividend"],"sealed_ADD_layer_closed":closedlayer["closed"],"sealed_ADD_layer_remaining_qty":closedlayer["qty"]})
opens=[r for r in snapshot_rows if r["phase"]=="OPEN_before_ADD"]
stats={"paths":len(paths),"fixed_cases":14,"seed_rounds_entered":len(bridge_rows),"true_seed_ADD_fills":len(frozen),"snapshots":len(snapshot_rows),"fee_receipts_recomputed":len(fee_checks),"q_signal_cap_differs_from_fill":sum(r["q_signal_cap"]!=r["q_OPEN_fill"] for r in add_rows),"same_day_sell_at_ADD":0,"factor_changed_between_t_and_OPEN_ADD":0,"seed_round_split_events":0}
for arm in ["CP_CONTROL_COMMON_I_SIZE","I_PROBE_COMMON_I_SIZE"]:
 a=[r for r in opens if r["arm"]==arm]
 stats[arm]={"ADD_fills":len(a),"seed_arms_with_ADD":len({r["case_id"] for r in a}),"newrisk_gt_U_inventory_pool":sum(r["newrisk_gt_U_inventory_pool"] for r in a),"newrisk_gt_U_round_accrual":sum(r["newrisk_gt_U_round_accrual"] for r in a),"old_protection_round_negative":sum(r["old_protection_round_confirmed_paid"]<0 for r in a),"after_protection_round_negative":sum(r["after_ADD_protection_round_confirmed_paid"]<0 for r in a),"prior_realized_ADD_net_negative":sum(r["has_prior_realized_ADD_loss"] for r in a),"newrisk_gt_U_round_confirmed_paid":sum(r["newrisk_gt_U_round_confirmed_paid"] for r in a),"U_round_confirmed_nonpositive_while_inventory_positive":sum(r["U_round_confirmed_paid"]<=0<r["U_inventory_pool"] for r in a),"mark_below_any_old_floor":sum(r["mark_below_any_old_floor"] for r in a)}
dump("INVENTORY_POSITIVE_CYCLE_NONPOSITIVE.json",[{k:r[k] for k in ["case_id","name","arm","fill_at","U_inventory_pool","realized_pool_net","dividend_accrued","dividend_paid_recorded","U_round_confirmed_paid","U_round_accrual"]} for r in opens if r["U_inventory_pool"]>0 and r["U_round_confirmed_paid"]<=0])
for c in cases:
 a=[r for r in opens if r["case_id"]==c["case_id"] and r["arm"]==c["arm"]]
 case_metrics.append({**c,"newrisk_gt_U_inventory_count":sum(r["newrisk_gt_U_inventory_pool"] for r in a),"newrisk_gt_U_round_count":sum(r["newrisk_gt_U_round_confirmed_paid"] for r in a),"after_protection_round_negative_count":sum(r["after_ADD_protection_round_confirmed_paid"]<0 for r in a),"prior_realized_ADD_loss_count":sum(r["has_prior_realized_ADD_loss"] for r in a)})
for basename,rows in [("SNAPSHOTS",snapshot_rows),("EXISTING_LAYER_FLOORS",layer_rows),("ADD_FINANCE_BRIDGE",add_rows),("SEED_ROUND_FINANCE_BRIDGE",bridge_rows),("CASE_COVERAGE",case_metrics)]:
 dump(basename+".json",rows);table(basename+".csv",rows)
dump("CHECKS.json",{"status":"PASS","stats":stats,"fees_match":True,"all_seed_round_bridges_match":True,"all_actual_ADD_gates_match":True,"strategy_engine_imports":0,"economic_runs":0,"new_candidates":0,"new_future_labels":0,"NOACT_original_contract_included":False,"snapshots_no_future_close":True,"formula":"q*(p-S_raw*0.9995)+dated_buy_fee(q*p)+dated_sell_fee(q*S_raw*0.9995)","scope":"Only sealed 14 cases x 2 conditional arms; original seed order excluded even if kind=add; all later 0-to-0 reentries excluded.","fees":"Every 929 actual fill fee component verified from sealed audit receipts; fee schedule is historical proxy contract, not a fresh brokerage quote."})
source_after={p:sha(pathlib.Path(p)) for p in source_before};assert source_after==source_before
dump("SOURCE_HASHES_AFTER.json",source_after)
def fmt(v):return f"{D(v):,.2f}"
lines=["# 固定14例：条件臂种子后续ADD利润与计划风险独立审计","",
"## 结论与冻结范围",
f"- 仅重算现存封存记录。14例×2臂，26个真实种子回合、58次真正后续ADD、116个t收盘/OPEN快照；CP原始种子虽标kind=add，也按原始signal排除，所有归零后正常重入排除。全部赢家和输家保留。",
"- 没有重跑策略经济，没有候选筛选、参数扫描、按股系数、未来新标签。原NOACT合同未混入。",
"- 当前利润只说明某一时点账面高于成本。不能用追加本金替代新增风险，更不能把库存利润、整轮利润及保护后可保留利润互换。",
"- 58笔实际OPEN追加中，库存U>0而整轮现金U<=0：CP 0/23，I 0/35。未付分红不给信用，名单为空。仅把库存正利润门换成整轮正利润门，在本固定样本没有筛除作用；不据此构造反事实PnL。",
"- 新增计划风险>库存利润：CP 8/23、I 12/35；>整轮现金利润：CP 8/23、I 10/35。新增后分层保护情景整轮为负：CP 18/23、I 26/35。58笔均没有OPEN已低于旧floor的情况，仍不代表未来能按floor成交。",
"","## 格力两笔：风险金额与利润口径"]
for r in opens:
 if r["case_id"]==1542 and r["arm"].startswith("I_") and r["fill_at"][:10] in ["2024-01-17","2024-03-28"]:
  lines+=["",f"### {r['fill_at'][:10]} OPEN",f"- q={r['candidate_qty']}，买价p={r['candidate_buy_p_with_5bp']}，S_raw={r['candidate_S_raw']}。",
  f"- 新增含费本金{fmt(r['candidate_buy_fee_cost'])}；新增计划风险{fmt(r['candidate_new_plan_risk'])}=q×(p−S×0.9995)+买费{fmt(r['candidate_buy_fee'])}+卖费{fmt(r['candidate_protection_sell_fee'])}。",
  f"- 原路径池化库存净盈利{fmt(r['U_inventory_pool'])}；整轮累计已实现池化净额{fmt(r['realized_pool_net'])}；含权益整轮净盈利{fmt(r['U_round_accrual'])}。",
  f"- 按实际分层原成本，库存净盈利{fmt(r['U_inventory_layer'])}、累计已实现净额{fmt(r['realized_layer_net'])}，其中已退出/售出ADD累计{fmt(r['realized_ADD_layer_net'])}。两个成本归属桥都得到同一整轮净额。",
  f"- 旧仓在既有floor的分层保护情景：整轮{fmt(r['old_protection_round_accrual'])}；从当前mark到该情景回吐{fmt(r['mark_to_protection_giveback'])}；再减新ADD计划风险后为{fmt(r['after_ADD_protection_round_accrual'])}。"]
lines+=["","3/28风险708.55高于库存166.25，却低于整轮724.59。不能说这笔风险超过整轮全部当前利润；但原旧仓保护情景已为负，因此也不能说当前利润已经被保护下来可担保新增。3/28的15392.18是池化平均剩余成本，不是未卖首层原成本13352.53。分层确认已退出ADD亏1481.31不可漏算，也不能在池化实现净额上再重复减一次。",
"","## t收盘与OPEN必须分别看",
"- t_close使用信号收盘可见raw close、已更新的既有floor、冻结intent cap，买价参考为close×1.0005。OPEN_before_ADD使用实际raw OPEN×1.0005、实际成交股数、前一信号收盘已知floor和factor。",
f"- {stats['q_signal_cap_differs_from_fill']}笔信号cap与OPEN成交股数不同，均分别报告；不拿未来成交股数冒充t时点计划。58笔均无t至OPEN factor变更、同OPEN先卖后加、延迟多日或同轮拆股边界，所以无需事后收盘价格/保护线。",
"- t收盘和OPEN均只是持仓按统一价格卖出的净额代理，不声称可当日卖出；新增当日受T+1限制。",
"","## 全样本覆盖与计划风险比较",
"| 原case | 名称 | 臂 | 种子现有结果 | 后续ADD | 风险>库存利润 | 风险>整轮利润 | 新增后保护情景<0 | 已有ADD实现净亏后再加 |",
"|---|---|---|---|---:|---:|---:|---:|---:|"]
for c in sorted(case_metrics,key=lambda r:(r["case_id"],r["arm"])):
 lines.append(f"| {c['case_id']} | {c['name']} | {'CP' if c['arm'].startswith('CP') else 'I'} | {c['seed_existing_status']} | {c['subsequent_seed_add_count']} | {c['newrisk_gt_U_inventory_count']} | {c['newrisk_gt_U_round_count']} | {c['after_protection_round_negative_count']} | {c['prior_realized_ADD_loss_count']} |")
lines+=["","这些计数只是已冻结样本的算术描述，不是新交易过滤器，不把利润/风险比改造成调参阈值。中国动力I未闭，只保留原生账面状态，不标胜。",
"","## 烽火与湖南：所有种子追加",
"| 名称 | 臂 | OPEN | q | 新风险 | 库存利润 | 整轮利润 | 已实现ADD净额 | 旧保护整轮 | 新增后保护整轮 |",
"|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
for r in opens:
 if r["case_id"] in [2893,2898]:
  lines.append(f"| {r['name']} | {'CP' if r['arm'].startswith('CP') else 'I'} | {r['fill_at'][:10]} | {r['candidate_qty']} | {fmt(r['candidate_new_plan_risk'])} | {fmt(r['U_inventory_pool'])} | {fmt(r['U_round_accrual'])} | {fmt(r['realized_ADD_layer_net'])} | {fmt(r['old_protection_round_accrual'])} | {fmt(r['after_ADD_protection_round_accrual'])} |")
lines+=["","## 财务桥与保护情景定义",
"- K_pool严格重建原路径池化平均成本（买费计入、股息不冲减），同时提供真实剩余分层原成本K_layer。pool与layer的实现损益不同是成本归属差异，整轮现金经济完全相同。",
"- U_inventory=当前库存净清算V−剩余K；U_round=累计卖净款−累计买含费支出+当前库存净清算V+已获股息权益。等价于U_inventory+累计已实现净额+股息权益。禁止忘掉旧亏，也禁止双减旧亏。",
"- 主整轮利润U_round_confirmed_paid只给已确认支付信用，58笔均没有已确认支付；U_round_accrual仅用于权益财务桥。OPEN库存U>0而主整轮U<=0的具体名单在INVENTORY_POSITIVE_CYCLE_NONPOSITIVE.json。",
"- 所有已得股息按原合同权益记录单列应收；有记录实付为0，现实是否到账UNKNOWN。含应收与除股息整轮净额并排提供；不将应收称为到账现金。",
"- 旧仓每层使用截至t已存在的floor。主情景同一floor层合并一个卖单，不同floor各一个卖单、分别收dated最低佣金；另给每层独立卖单费用更保守版本。candidate单独计一买一卖，不假设与旧层将来共用订单。",
"- 另逐层及逐笔标记当时mark/OPEN是否已经低于旧floor（mark_below_any_old_floor）；若已低于，更不能把floor情景称为可以拿到或锁定的盈利。无改floor、跳空系数或风险模型执行。",
"- 库存V按整股一次卖单计费；另列每层单卖佣金与整体单卖费用差，不能把sum(layer U)直接当成原门U。",
"- 分层不同floor是不同层分别在其计划保护价格退出的假设，不是存在一个可同时成交的清算价格；不是实际未来现金流，不预言触发顺序。",
"- 保护金额乘卖出5bp，费用使用当日已知历史费率，不预知未来实际卖日费率。隔夜跳空、缺价、涨跌停/真实可成交性UNKNOWN、T+1及交易时钟均可能令实际损失超过计划风险；没有保证型风险帽。",
"- after保护整轮=旧仓保护情景整轮−新增计划风险=当前整轮净利润−mark到旧保护的回吐−新风险。不能仅比较新风险与当前未锁定利润就声称整轮不亏。",
"","## 核验与文件",
"- 929次实际成交dated fee组件全部独立重算通过；58次OPEN盈利门的数量、V、K全部对齐；26个种子完整/未闭回合现金桥对齐封存net。",
"- SOURCE_HASHES_BEFORE/AFTER覆盖run封存36项、OUTPUT_HASHES及最终REPORT_v2，共38个源文件；全部前后相同。这里不声称重新校验SOURCE_FREEZE指向的外部347个原始源，本任务未越界读取。",
"- FROZEN_SEED_ADD_UNIVERSE：事先冻结的58笔真实种子后续ADD身份。CASE_COVERAGE：全14×2，包括无ADD和未入场。",
"- SNAPSHOTS：116个t/OPEN利润、风险、保护情景全字段。EXISTING_LAYER_FLOORS：每笔事前已知分层floor、数量和成本。",
"- ADD_FINANCE_BRIDGE：58笔新增和原已存在层结果（未闭保持未闭）。SEED_ROUND_FINANCE_BRIDGE：26个整轮现金/权益/原生mark桥。",
"- CHECKS.json及OUTPUT_HASHES.json：核验与本审计产物hash。audit.py只读封存记录，原产物未改。",
"","## 小结",
"盈利可追加的布尔门没有要求新增计划风险由已保护的整轮利润覆盖。格力1/17的真实新增计划风险确实超过当时库存及整轮利润；3/28只能说超过池化库存利润，不能夸大为超过整轮利润。两笔旧仓保护后均不能保住整轮本金。所有赢家/输家真实ADD已经一并冻结并披露，当前结果用于识别责任口径，不直接产生新交易规则。"]
(OUT/"REPORT.md").write_text("\n".join(lines)+"\n")
hashes={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!="OUTPUT_HASHES.json"}
dump("OUTPUT_HASHES.json",hashes)
print(json.dumps({"out":str(OUT),"stats":stats,"source_files_unchanged":len(source_before),"report_sha256":sha(OUT/"REPORT.md"),"selected":[r for r in add_rows if r["case_id"] in [1542,2893,2898]]},ensure_ascii=False,default=str))
