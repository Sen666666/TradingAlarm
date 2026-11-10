"""Read existing saved attribution and raw ledger only; no accounts or policy changes."""
from pathlib import Path
import json,gzip,pandas as pd,math,hashlib,collections
from decimal import Decimal as D
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
O=R/"semiconductor_account_attribution_v1"; S=R/"semiconductor_h1_scope_v1"; P=R/"account_comparison_continuous_v1/run_1200000/pair"
def read(n):return json.loads((O/n).read_text())
def norm(x):
 if isinstance(x,D):return str(x)
 if isinstance(x,dict):return {str(k):norm(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [norm(v) for v in x]
 if isinstance(x,float) and not math.isfinite(x):return None
 if hasattr(x,"item"):return norm(x.item())
 return x
def save(n,x):(O/n).write_text(json.dumps(norm(x),ensure_ascii=False,indent=2,allow_nan=False)+"\n")
profiles=read("ALL_112_STOCK_PROFILES.json"); ids={x["sid"] for x in profiles}; doubles={x["sid"] for x in profiles if x["double_posthoc"]}
cp=read("ALL_739_CP_EVENT_FUNNEL.json"); minimum=read("ALL_1113_CLOSE_MINIMUM_DIAGNOSIS.json")
fund=read("RAW_FILTERED_FUNDING_2026.json"); intents=read("RAW_FILTERED_PENDING_2026.json"); op=read("RAW_FILTERED_OPPORTUNITIES_2026.json"); tr=read("RAW_FILTERED_TRADES_2026.json")
a=json.load(gzip.open(P/"PVR.json.gz","rt"))
daily=[]
for l in gzip.open(P/"daily.jsonl.gz","rt"):
 if "2026-" not in l and "2025-12-31" not in l:continue
 x=json.loads(l)
 if x["account"]=="PVR":daily.append(x)
dmap={x["at"][:10]:x for x in daily}
signal=pd.read_parquet(S/"ENRICHED_DAILY.parquet")
sigmap={(x["sid"],x["day"]):x for x in signal[signal.day.le("2026-05-15")&signal.sid.isin(ids)].to_dict("records")}
assert not (set(dmap["2025-12-31"]["positions"])&ids)
money=[]
for pr in profiles:
 sid=pr["sid"];t=[x for x in tr if x["security_id"]==sid];buy=[x for x in t if x["side"]=="buy"];sell=[x for x in t if x["side"]=="sell"];q=dmap["2026-05-15"]["positions"].get(sid,0)
 bg=sum((D(x["gross_cny"]) for x in buy),D(0));bf=sum((D(x["fees_cny"]) for x in buy),D(0));sg=sum((D(x["gross_cny"]) for x in sell),D(0));sf=sum((D(x["fees_cny"]) for x in sell),D(0));mv=D(q)*D(str(sigmap[(sid,"2026-05-15")]["raw_close"])) if q else D(0)
 acts=[x for x in a["audit"] if (x["kind"]=="dividend_accrual" and x["receivable"]["security_id"]==sid and x["receivable"]["ex_at"]>="2026") or (x["kind"]=="split" and x["sid"]==sid and x["at"]>="2026")]
 assert not acts
 row=dict(sid=sid,name=pr["name"],double_posthoc=sid in doubles,buy_gross=bg,buy_fees=bf,buy_paid=bg+bf,sell_gross=sg,sell_fees=sf,sell_net=sg-sf,ending_qty=q,ending_inventory=mv,dividends=0,wealth_contribution=sg-sf+mv-bg-bf)
 money.append(row);pr.update(norm(row))
save("ALL_112_STOCK_PROFILES_WITH_MONEY.json",profiles)
pd.DataFrame(profiles).drop(columns=["fund_reasons","CP_categories"]).to_csv(O/"ALL_112_STOCK_PROFILES_WITH_MONEY.csv",index=False)
save("ALL_112_STOCK_CASH_BRIDGE.json",money)
sums={}
for name,pool in [("strict112",ids),("retrospective_double51",doubles)]:
 rows=[x for x in money if x["sid"] in pool]
 sums[name]={k:sum((x[k] for x in rows),D(0)) for k in ("buy_gross","buy_fees","buy_paid","sell_gross","sell_fees","sell_net","ending_inventory","wealth_contribution")}
 sums[name].update(unique_stocks=len(pool),bought_stocks=sum(x["buy_paid"]>0 for x in rows),buy_layers=sum(x["side"]=="buy" and x["security_id"] in pool for x in tr),ending_stocks=sum(x["ending_qty"]>0 for x in rows),closed_contribution=sum((x["wealth_contribution"] for x in rows if x["ending_qty"]==0),D(0)),open_marked_contribution=sum((x["wealth_contribution"] for x in rows if x["ending_qty"]>0),D(0)))
assert sums["strict112"]["wealth_contribution"]==D("-8664.1114494169545")
assert sums["retrospective_double51"]["wealth_contribution"]==D("-2859.0890874640045")
save("CASH_BRIDGE_SUMMARY.json",sums)
allr=pd.read_csv(R/"selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv")
def rrsummary(r):
 closed=r[r.closed.eq(True)]
 return dict(rounds=len(r),closed=len(closed),wins=int(closed.round_pnl.gt(0).sum()),losses=int(closed.round_pnl.lt(0).sum()),zero=int(closed.round_pnl.eq(0).sum()),open=len(r)-len(closed),winrate=float(closed.round_pnl.gt(0).mean()),denominator="closed net 0-to-0 holding rounds; adds are not separate rounds")
winrates=dict(new2026_entries=rrsummary(allr[(allr.account=="PVR")&allr.entry_day.ge("2026")]),closed_during2026_including_carry=rrsummary(allr[(allr.account=="PVR")&allr.closed_day.ge("2026")]),strict112=rrsummary(allr[(allr.account=="PVR")&allr.entry_day.ge("2026")&allr.sid.isin(ids)]),retrospective_double51=rrsummary(allr[(allr.account=="PVR")&allr.entry_day.ge("2026")&allr.sid.isin(doubles)]),cutoff="2026-05-15")
save("NET_ROUND_WINRATES.json",winrates)
caseids=["300666.SZ","301611.SZ","603061.SH"]
cases=[]
for sid in caseids:
 for day,d in sorted(dmap.items()):
  if day<"2026":continue
  zz=sigmap.get((sid,day));oo=next((x for x in op if x["sid"]==sid and x["day"]==day),None)
  cases.append(dict(sid=sid,day=day,signal=zz,opportunity=oo,close_intents=[x for x in intents if x["sid"]==sid and x["day"]==day],funding_events_today=[x for x in fund if x["sid"]==sid and x["at"][:10]==day],trades_today=[x for x in tr if x["security_id"]==sid and x["at"][:10]==day],ending_quantity=d["positions"].get(sid,0),exit_pending=sid in d["pending_sells"],live_layers=[x for x in d["layers"] if x["sid"]==sid],exit_requests=[x for x in a["audit"] if x["kind"]=="exit_request" and x.get("sid")==sid and x["at"][:10]==day]))
save("THREE_CASES_FULL_255_ACCOUNT_DAYS.json",cases)
oldpath=Path("/Users/bytedance/Documents/Codex/2026-11-04/task/loss_correction/no60_behavior_v1/SEMICONDUCTOR_HOLD_EXIT_REENTRY_SUMMARY.json")
old=json.loads(oldpath.read_text())["PVR_NO60"]["all_actual_layers"]; oldids={x["sid"] for x in old};newids={x["security_id"] for x in tr if x["side"]=="buy"}
save("ACCOUNT_VERSION_DIFFERENCES.json",dict(old_account="100万元 NO60, 2025-07-01 to 2026-06-30",old_halfyear_stocks=len(oldids),old_halfyear_layers=len(old),old_halfyear_contribution="-16783.5804624931475",new_account="120万元 continuous PVR 2022-01-01 to 2026-05-15",new_period_stocks=len(newids),new_period_layers=sum(x["side"]=="buy" for x in tr),new_period_contribution=sums["strict112"]["wealth_contribution"],intersection=sorted(oldids&newids),only_new=sorted(newids-oldids),only_old=sorted(oldids-newids),old_summary_path=str(oldpath),warning="Different initial capital, start history and cutoff; old first buys after May15 cannot be counted as current omissions"))
coverage=pd.read_csv(S/"ALL_126_COVERAGE_WITH_NAMES.csv")
save("EXCLUDED_14_SCOPE.json",coverage[~coverage.sid.isin(ids)].to_dict("records"))
groups={}
for tag,pool in [("112",ids),("51",doubles)]:
 pp=[x for x in profiles if x["sid"] in pool];c=[x for x in cp if x["sid"] in pool];f=[x for x in fund if x["sid"] in pool and "09:30" in x["at"]]
 rr=[x for x in c if x["category"]=="open_rejected" and x["sector_auth"]]
 groups[tag]=dict(stocks=len(pool),terminal_groups=dict(collections.Counter(x["terminal_group"] for x in pp)),CP_events=len(c),CP_stocks=len({x["sid"] for x in c}),CP_category_events=dict(collections.Counter(x["category"] for x in c)),CP_category_stocks={k:len({x["sid"] for x in c if x["category"]==k}) for k in {x["category"] for x in c}},CP_stage_events=dict(collections.Counter(x["eligibility_stage"] for x in c)),authorized_open_reject_events=len(rr),authorized_open_reject_stocks=len({x["sid"] for x in rr}),authorized_reject_cash_events=sum("cash_or_original_reserve" in ",".join(x["open_reasons"]) for x in rr),authorized_reject_cash_stocks=len({x["sid"] for x in rr if "cash_or_original_reserve" in ",".join(x["open_reasons"])}),any_pending_top20_stocks=sum(x["ever_pending_top20"] for x in pp),no_fill_but_any_pending_top20_stocks=sum(x["ever_pending_top20"] and x["first_buy"] is None for x in pp),actual_open_funding_events_including_prior_close=len(f))
save("FUNNEL_SUMMARY.json",groups)
rankrows=[]
for line in gzip.open(P/"rank-policy.jsonl.gz","rt"):
 if "2026-" not in line:continue
 x=json.loads(line)
 if x["account"]=="PVR" and x["sid"] in ids:rankrows.append(x)
rankmap={(x["sid"],x["day"]):x for x in rankrows}
for x in cp:
 r=rankmap.get((x["sid"],x["day"]))
 x["actual_queue_position"]=r["final_slot"]+1 if r else None
 x["original_pending_H1_position"]=r["original_slot"]+1 if r else None
 x["ranking_note"]="rank is sparse priority key; actual position from original PVR rank-policy final_slot+1"
save("CP_EVENTS_WITH_ACTUAL_QUEUE_POSITIONS.json",cp)
assert all(x["account"]=="PVR" for x in rankrows+fund+op+daily)

unknown=dict(raw_stockdays=len(sigmap),raw_missing_common_days=85*112-len(sigmap),PVR_unknown_cells=int(signal[signal.day.le("2026-05-15")&signal.sid.isin(ids)].PVR_score.isna().sum()),grade_unknown_cells=int(signal[signal.day.le("2026-05-15")&signal.sid.isin(ids)].g_grade.isna().sum()),CP_missing_PVR=[dict(sid=x["sid"],day=x["day"],category=x["category"]) for x in cp if x["PVR"] is None],not_full_legal_eligibility=dict(sid="300666.SZ",day="2026-05-15",reason="stock_rs_ready_fresh:unknown"),funding_outcomes_without_account_lineage=0,source_missing_open_not_exchange_suspension=True)
save("UNKNOWN_AND_DATA_LIMITS.json",unknown)
hashes=read("SOURCE_HASHES.json")
for p in [Path(__file__),oldpath,S/"ALL_126_COVERAGE_WITH_NAMES.csv",S/"SECTOR_DAILY.csv"]:
 hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
save("SUPPLEMENT_SOURCE_HASHES.json",hashes)
print("SUPPLEMENT_DONE",json.dumps(norm(sums),ensure_ascii=False)); print("WINRATES",winrates)
