import csv,json,collections,bisect,math
from pathlib import Path
from decimal import Decimal
R=Path.cwd(); BASE=R/"independent_channel_joint_economic_v1"
cal=[r[""] for r in csv.DictReader((R/"selection_entry_diagnosis_v1/entry_probability_signal_v1/MARKET_CLOCK.csv").open())]
def dec(x): return Decimal(x) if x not in ("",None) else Decimal(0)
def num(x): return float(x) if x not in ("",None) else float("nan")
def nxt(day):
 i=bisect.bisect_right(cal,day);return cal[i] if i<len(cal) else None
allrows={}
for year in ["2022","2024"]:
 p=BASE/("economic_"+year); j=p/"joint"
 rounds=[r for r in csv.DictReader((j/"ROUNDS.csv").open()) if r["owner_lane"]=="PRICE"]
 cov={r["round_id"]:r for r in json.loads((p/"COMPARISON_REPORT_RECOVERED.json").read_text())["round_coverage"] if r["arm"]=="joint"}
 acts=collections.defaultdict(list)
 for a in csv.DictReader((j/"ACTIONS.csv").open()): acts[a["round_id"]].append(a)
 claims={r["owner_round_id"] for r in json.loads((j/"CLAIMS.json").read_text())}
 bridges={r["round_id"] for r in json.loads((j/"BRIDGES.json").read_text())}
 ledger={r["round_id"] for r in csv.DictReader((j/"CLAIM_LEDGER.csv").open())}
 regs={r["owner_round_id"] for r in csv.DictReader((j/"REGISTRATIONS.csv").open())}
 qa={r["round_id"]:r for r in json.loads((j/"LEDGER_QA.json").read_text())}
 for r in rounds:
  rid=r["round_id"]; aa=acts[rid]; cc=cov[rid]; qq=qa.get(rid,{})
  buys=[a for a in aa if a["side"].startswith("buy")]
  sells=[a for a in aa if a["side"].startswith("sell")]
  net=sum((dec(a["q"])*dec(a["price"])-dec(a["fee"]) for a in sells),Decimal(0))-sum((dec(a["q"])*dec(a["price"])+dec(a["fee"]) for a in buys),Decimal(0))
  inv=sum((dec(a["q"]) for a in buys),Decimal(0))-sum((dec(a["q"]) for a in sells),Decimal(0))
  r["_entered"]=any(a["side"]=="buy_core" for a in aa)
  r["_closed"]=r["status"]=="COMPLETE_CONDITIONAL_STOCK_ROUND"
  r["_covered"]=cc["financial_covered"];r["_reason"]=cc["reason"]
  r["_rights"]=rid in claims or rid in bridges or rid in ledger
  r["_rights_registration"]=rid in regs
  r["_claims"]=rid in claims;r["_bridges"]=rid in bridges;r["_ledger"]=rid in ledger
  r["_zero"]=inv==0 and dec(r["core_qty"])==0 and dec(r["add_qty"])==0 and qq.get("qty")==0
  r["_cash_error"]=abs(float(net)-num(r["net_pnl"])) if r["_closed"] else None
  r["_cash_reconciled"]=r["_closed"] and r["_cash_error"]<1e-6 and abs(float(net)-num(r["cashflow_to_date"]))<1e-6 and abs(float(net)-num(r["cash_after_payouts"]))<1e-6 and qq.get("reconciled") is True and abs(float(net)-float(qq["trade_cash"]))<1e-6
  r["_zero_rights_fields"]=all(dec(r.get(k))==0 for k in ["receivable_at_termination","dividend_at_termination","receivable_after_payouts","dividend_net80_total","dividend_net80_paid"]) and all(float(qq.get(k,0))==0 for k in ["paid","receivable"])
  r["_action_clock"]=bool(aa) and max(a["day"] for a in aa)==r["exit_day"] and min(a["day"] for a in aa)==r["entry_day"]
  r["_qual"]=r["_entered"] and r["_closed"] and r["_covered"] and r["_reason"]=="LOCAL_NO_ACTION_EVIDENCE" and not r["_rights"] and r["_zero"] and r["_cash_reconciled"] and r["_zero_rights_fields"] and r["_action_clock"]
  r["_known_next"]=nxt(r["exit_day"]) if r["_qual"] else None
 allrows[year]=rounds
 def summary(rows):
  q=[r for r in rows if r["_qual"]]
  return dict(registered=len(rows),entered=sum(r["_entered"] for r in rows),closed=sum(r["_closed"] for r in rows),no_action_coverage=sum(r["_reason"]=="LOCAL_NO_ACTION_EVIDENCE" for r in rows),qualified=len(q),qualified_w=sum(num(r["net_pnl"])>0 for r in q),qualified_l=sum(num(r["net_pnl"])<=0 for r in q),qualified_stocks=len({r["sid"] for r in q}),qualified_signal_dates=len({r["signal_day"] for r in q}),qualified_exit_min=min((r["exit_day"] for r in q),default=None),qualified_exit_max=max((r["exit_day"] for r in q),default=None),claim_rounds=sum(r["_claims"] for r in rows),bridge_rounds=sum(r["_bridges"] for r in rows),claim_ledger_rounds=sum(r["_ledger"] for r in rows),rights_union_rounds=sum(r["_rights"] for r in rows),rights_closed=sum(r["_rights"] and r["_closed"] for r in rows),rights_registration_rounds=sum(r["_rights_registration"] for r in rows),no_action_closed=sum(r["_closed"] and r["_reason"]=="LOCAL_NO_ACTION_EVIDENCE" for r in rows),qual_registered_pct=len(q)/len(rows)*100 if rows else None,qual_entered_pct=len(q)/sum(r["_entered"] for r in rows)*100 if any(r["_entered"] for r in rows) else None,qual_closed_pct=len(q)/sum(r["_closed"] for r in rows)*100 if any(r["_closed"] for r in rows) else None,qual_cash_max_error=max((r["_cash_error"] for r in q),default=None),qualified_rights_registration=sum(r["_rights_registration"] for r in q))
 print("YEAR",year,json.dumps(summary(rounds),ensure_ascii=False))
 print("EXCLUDED_NOACTION_CLOSED",collections.Counter(tuple(k for k in ["_zero","_cash_reconciled","_zero_rights_fields","_action_clock"] if not r[k]) for r in rounds if r["_closed"] and r["_reason"]=="LOCAL_NO_ACTION_EVIDENCE" and not r["_qual"]))
 print("CLOSED_REASON",collections.Counter(r["_reason"] for r in rounds if r["_closed"]))
for cut in ["2022-07-01","2024-09-02"]:
 i=cal.index(cut); low=cal[i-504] if i>=504 else None
 rr=[r for r in allrows["2022"] if r["signal_day"]<cut and (low is None or r["signal_day"]>=low)]
 old=[r for r in rr if r["_qual"] and r["exit_day"]<cut]
 strict=[r for r in rr if r["_qual"] and r["_known_next"] and r["_known_next"]<cut]
 print("CUT",cut,"signal_window_start",low,"calendar_prior_sessions_available",i,json.dumps(dict(signal_domain=summary(rr),closed_before_cut=summary(old),next_session_strict_before_cut=summary(strict),boundary_equal_next_cut=sum(r["_qual"] and r["_known_next"]==cut for r in rr)),ensure_ascii=False))
 if cut=="2022-07-01": test=[r for r in allrows["2022"] if cut<=r["signal_day"]<="2022-12-31"]
 else: test=[r for r in allrows["2024"] if cut<=r["signal_day"]<="2024-12-31"]
 print("TEST",cut,json.dumps(summary(test),ensure_ascii=False))
