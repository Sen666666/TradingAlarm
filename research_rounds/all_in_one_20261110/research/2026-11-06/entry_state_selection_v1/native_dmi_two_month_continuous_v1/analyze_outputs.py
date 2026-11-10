"""Read sealed completed monthly outputs only. No accounts or strategy events."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import ast,json,gzip,hashlib,sys,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent;OUT=O/"analysis"
Z=D(0);EPS=D("1e-8")
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(8*1024*1024),b""):h.update(b)
 return h.hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2,default=str,allow_nan=False))
def stream(p):
 with gzip.open(p,"rt") as f:
  for x in f:yield json.loads(x)
def gz(p):
 with gzip.open(p,"rt") as f:return json.load(f)
def csv(p,rows):
 f=pd.DataFrame(rows)
 for c in f.columns:
  if f[c].map(lambda x:isinstance(x,(dict,list,tuple))).any():f[c]=f[c].map(lambda x:json.dumps(x,default=str) if isinstance(x,(dict,list,tuple)) else x)
 f.to_csv(p,index=False)
def decsum(vals):return sum((D(str(x)) for x in vals),Z)
OLD=R/"act_only_ablation_continuous_v1/analysis_preparation/analyze_act_only_v2.py"
env=globals()
exec(compile(ast.Module(body=[n for n in ast.parse(OLD.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in ("stats","nav_stats","replay_account")],type_ignores=[]),str(OLD)+":pure_output_analysis","exec"),env)
def stat(rows,layer=False):
 z=stats(rows)
 z["unit"]="INITIAL_BUY_LAYER" if layer else "COMPLETE_0_TO_0_ROUND"
 if layer:z["return_denominator"]="First actual buy layer gross plus that layer buy fee only; later ADD excluded"
 tail=[r for r in rows if r["buy_cost"]>0 and r["pnl"]/r["buy_cost"]>=D(".30")]
 z.update(fee_net_30pct_tail_count=len(tail),fee_net_30pct_tail_pnl=sum((r["pnl"] for r in tail),Z),buy_fills=sum(r.get("buy_fills",1) for r in rows),sell_fills=sum(r.get("sell_fills",0) for r in rows))
 return z
def main():
 started=time.monotonic();OUT.mkdir(exist_ok=False)
 windows={"2022Jan":("2022-01-04","2022-01-28"),"2026Jan":("2026-01-05","2026-01-30")}
 inputs={str(Path(__file__)):sha(__file__),str(OLD):sha(OLD)}
 data={}
 for w,(lo,hi) in windows.items():
  for arm in ("PVR","DMI"):
   p=O/(w+"_"+arm);done=read(p/"DONE.json");assert done["completed"] and done["days"]==(19 if w=="2022Jan" else 20)
   for name,h in read(p/"OUTPUT_SHA256.json").items():assert sha(p/name)==h,("sealed output drift",w,arm,name)
   inputs[str(p/"OUTPUT_SHA256.json")]=sha(p/"OUTPUT_SHA256.json")
   ds={r["at"][:10]:r for r in stream(p/"pair/daily.jsonl.gz")};a=gz(p/"pair/PVR.json.gz");initial=read(p/"INITIAL_STATE.json")["initial_daily"]
   data[(w,arm)]=dict(ds=ds,a=a,initial=initial,done=done,path=p)
  assert data[(w,"PVR")]["done"]["starting_payload_sha"]==data[(w,"DMI")]["done"]["starting_payload_sha"]
 sys.dont_write_bytecode=True;sys.path.insert(0,str(R/"account_comparison_continuous_v1/inputs"));import continuous_inputs as C
 ids=read(C.U/"FREEZE.json")["stocks"]
 _,market,_=C.J.M.context("2026-01-30",ids=ids)
 marks={}
 for w,(lo,hi) in windows.items():
  days=sorted(data[(w,"PVR")]["ds"])
  for d in (["2025-12-31"] if w=="2026Jan" else [])+days:
   rr=[data[(w,a)]["initial"] if d=="2025-12-31" else data[(w,a)]["ds"][d] for a in ("PVR","DMI")]
   held=set().union(*(set(r["positions"]) for r in rr))
   at=C.J.M.N.iso(rr[0]["at"]);marks[d]={s:m.cny_price(at) for s,m in market.marks(at,held).items()}
   for r in rr:
    inv=sum((D(q)*marks[d][s] for s,q in r["positions"].items()),Z)
    assert abs(inv-D(r["inventory"]))<EPS,("inventory reconstruction",w,d)
    nav=sum((D(r[k]) for k in ("available","order_reserved","settlement_locked","sale_receivable","dividend_receivable","inventory")),Z)-D(r["payable"])
    assert abs(nav-D(r["nav"]))<EPS
 summaries=[];roundrows=[];layerrows=[];trades=[];tails=[];dailyrows=[];rankaudit=[];funding=[];cases=[]
 for (w,arm),v in data.items():
  lo,hi=windows[w];days=sorted(v["ds"]);ds=v["ds"];a=v["a"];initial=v["initial"]
  rr,ll,bridge=replay_account(a,arm,ds,days,marks)
  # Historical helper's occupied-cost list assumes lifetime daily dates; omit
  # those two peak/mean fields when only bounded monthly daily rows are supplied.
  bridge={k:v for k,v in bridge.items() if k not in ("peak_remaining_buy_cost","mean_remaining_buy_cost")}
  layer_sales=Counter(part["layer"] for t in a["trades"] if t["side"]=="sell" for part in t["parts"])
  for l in ll:l["buy_fills"]=1;l["sell_fills"]=layer_sales[l["id"]]
  init={l["id"]:l for l in initial["layers"]}
  layer_month={}
  for l in ll:
   if l["id"] in init:
    q=init[l["id"]];p0=D(q["cash"])+D(q["dividend"])+D(q["qty"])*marks["2025-12-31"][q["sid"]]
    contribution=l["pnl"]-p0;cohort="INHERITED_LIVE_LAYER"
   elif lo<=l["opened"][:10]<=hi:contribution=l["pnl"];cohort="NEW_MONTH_LAYER"
   else:continue
   layer_month[l["id"]]=contribution
   l.update(window=w,arm=arm,month_contribution=contribution,month_cohort=cohort)
   layerrows.append(l)
  navchange=D(ds[days[-1]]["nav"])-D(initial["nav"])
  assert abs(sum(layer_month.values(),Z)-navchange)<EPS,("month contribution bridge",w,arm,sum(layer_month.values(),Z),navchange)
  for r in rr:
   r["window_peak_marked_inventory"]=r.pop("peak_marked_inventory")
   r["window_peak_marked_inventory_NAV_fraction"]=r.pop("peak_marked_inventory_NAV_fraction")
   r["marked_peak_scope"]="Observed month CLOSEs only, not lifetime peak"
   r.update(window=w,arm=arm,month_contribution=sum((layer_month.get(i,Z) for i in r["layer_ids"]),Z))
   r["month_cohort"]="NEW_MONTH_ROUND" if lo<=r["opened"][:10]<=hi else "INHERITED_ROUND" if any(i in init for i in r["layer_ids"]) else "BEFORE_MONTH_CLOSED"
  relevant=[r for r in rr if r["month_cohort"]!="BEFORE_MONTH_CLOSED"]
  new=[r for r in relevant if r["month_cohort"]=="NEW_MONTH_ROUND"];inherited=[r for r in relevant if r["month_cohort"]=="INHERITED_ROUND"]
  closed=[r for r in relevant if r["closed"] and lo<=r["closed"][:10]<=hi]
  opens=[r for r in relevant if not r["closed"]]
  initial_month_closed=[l for l in ll if l["initial_layer"] and l["closed"] and lo<=l["closed"][:10]<=hi]
  initial_new_closed=[l for l in initial_month_closed if lo<=l["opened"][:10]<=hi]
  new_initial_open=[l for l in ll if l["initial_layer"] and lo<=l["opened"][:10]<=hi and not l["closed"]]
  mt=[t for t in a["trades"] if lo<=t["at"][:10]<=hi];fee=decsum(t["fees_cny"] for t in mt)
  assert fee==D(v["done"]["month_fees"])
  risk=[]
  for d in days:
   r=ds[d];risk.append(dict(window=w,arm=arm,day=d,nav=r["nav"],available=r["available"],inventory=r["inventory"],dividend_receivable=r["dividend_receivable"],stock_count=len(r["positions"]),layers=len(r["layers"]),ACT_on=r["on"],pending_intents=r["pending_intents"],inventory_fraction=float(D(r["inventory"])/D(r["nav"])),max_stock_NAV_fraction=max((float(D(q)*marks[d][s]/D(r["nav"])) for s,q in r["positions"].items()),default=0)))
   for sid in ["300666.SZ","301611.SZ"]:
    q=r["positions"].get(sid,0);cases.append(dict(window=w,arm=arm,day=d,sid=sid,shares=q,position_value=D(q)*marks[d].get(sid,Z),NAV=r["nav"]))
  dailyrows+=risk
  sr=dict(window=w,arm=arm,**nav_stats([ds[d] for d in days],D(initial["nav"])),initial_available=initial["available"],final_available=ds[days[-1]]["available"],initial_inventory=initial["inventory"],final_inventory=ds[days[-1]]["inventory"],initial_dividend_receivable=initial["dividend_receivable"],final_dividend_receivable=ds[days[-1]]["dividend_receivable"],month_NAV_change=navchange,month_fees=fee,buy_fills=sum(t["side"]=="buy" for t in mt),sell_fills=sum(t["side"]=="sell" for t in mt),buy_cash_including_fees=decsum(D(t["gross_cny"])+D(t["fees_cny"]) for t in mt if t["side"]=="buy"),embedded_open_slippage=decsum(D(t["shares"])*abs(D(t["price"])-D(t["raw_open"])) for t in mt),new_rounds=len(new),inherited_rounds=len(inherited),new_closed_rounds=stat([r for r in new if r["closed"]]),inherited_closed_rounds_lifetime=stat([r for r in inherited if r["closed"]]),all_closed_during_month_lifetime=stat(closed),new_open_rounds_right_censored=len([r for r in new if not r["closed"]]),inherited_open_rounds_right_censored=len([r for r in inherited if not r["closed"]]),new_open_rounds_marked_pnl=sum((r["pnl"] for r in new if not r["closed"]),Z),new_initial_layers_independently_closed=stat(initial_new_closed,layer=True),all_initial_layers_closed_during_month_lifetime=stat(initial_month_closed,layer=True),new_initial_layers_still_open=len(new_initial_open),initial_layer_closed_but_round_still_open=sum(l["closed"] is not None and next(r for r in rr if r["round_id"]==l["round_id"])["closed"] is None for l in initial_new_closed),inherited_live_layer_month_contribution=sum((layer_month[i] for i in init),Z),new_layer_month_contribution=sum((p for i,p in layer_month.items() if i not in init),Z),month_contribution_bridge_pass=True,end_positions=len(ds[days[-1]]["positions"]),end_live_layers=len(ds[days[-1]]["layers"]),end_pending_roles=v["done"]["pending_end"],mean_inventory_fraction=float(np.mean([r["inventory_fraction"] for r in risk])),max_stock_NAV_fraction=max(r["max_stock_NAV_fraction"] for r in risk),ACT_off_closes=sum(not r["ACT_on"] for r in risk),full_lifetime_bridge=bridge,seconds_native=v["done"]["seconds"])
  summaries.append(sr);roundrows+=relevant
  for r in closed:
   if r["pnl"]/r["buy_cost"]>=D(".30"):tails.append(r)
  trades += [dict(window=w,arm=arm,**t) for t in mt]
  if arm=="DMI":
   aa=list(stream(v["path"]/"DMI_RANK_AUDIT.jsonl.gz"));rankaudit += [dict(window=w,**r) for r in aa]
   sr["DMI_candidate_stock_days"]=len(aa);sr["DMI_UNKNOWN_candidate_stock_days"]=sum(r["d"] is None for r in aa);sr["DMI_mutable_stock_days"]=sum(r["mutable"] for r in aa);sr["DMI_moved_stock_days"]=sum(r["rank"]!=r["original_PVR_rank"] for r in aa)
  ff=Counter((r["role"],r["result"]) for r in stream(v["path"]/"pair/funding.jsonl.gz"))
  funding += [dict(window=w,arm=arm,role=k[0],result=k[1],rows=n) for k,n in ff.items()]
 # Compare observed round entry identity, inherited and new separately. Different starts are not paired returns.
 entries={};tailcompare=[]
 for w in windows:
  by={}
  for arm in ("PVR","DMI"):
   rows=[r for r in roundrows if r["window"]==w and r["arm"]==arm]
   by[arm]={(r["sid"],r["opened"]):r for r in rows}
  for key in sorted(set(by["PVR"])|set(by["DMI"])):
   x=dict(window=w,sid=key[0],opened=key[1],cohort="NEW_MONTH_ROUND" if key[1][:10]>=windows[w][0] else "INHERITED_ROUND",presence="BOTH" if key in by["PVR"] and key in by["DMI"] else "DMI_ONLY" if key in by["DMI"] else "PVR_ONLY")
   for arm in ("PVR","DMI"):
    r=by[arm].get(key);x[arm+"_closed"]=bool(r and r["closed"]);x[arm+"_pnl"]=r["pnl"] if r else None;x[arm+"_fee_net_return"]=float(r["pnl"]/r["buy_cost"]) if r else None;x[arm+"_tail30"]=bool(r and r["closed"] and r["pnl"]/r["buy_cost"]>=D(".30"));x[arm+"_state"]="ABSENT" if r is None else "CLOSED" if r["closed"] else "RIGHT_CENSORED"
   x["tail_change"]="DMI_ONLY_OBSERVED_TAIL" if x["DMI_tail30"] and not x["PVR_tail30"] else "PVR_ONLY_OBSERVED_TAIL" if x["PVR_tail30"] and not x["DMI_tail30"] else "BOTH_TAIL" if x["DMI_tail30"] else "NEITHER_OBSERVED_TAIL"
   tailcompare.append(x)
 for name,rows in [("ROUND_DETAILS",roundrows),("MONTH_LAYER_CONTRIBUTIONS",layerrows),("MONTH_TRADES",trades),("COMPLETE_FEE_NET_30PCT_TAILS",tails),("NEW_ENTRY_IDENTITY_COMPARISON",[r for r in tailcompare if r["cohort"]=="NEW_MONTH_ROUND"]),("INHERITED_ENTRY_IDENTITY_COMPARISON",[r for r in tailcompare if r["cohort"]=="INHERITED_ROUND"]),("DAILY_EQUITY_RISK",dailyrows),("DMI_CANDIDATE_AUDIT",rankaudit),("NATIVE_FUNDING_COUNTS",funding),("JIANGFENG_KEMA_DAILY",cases)]:csv(OUT/(name+".csv"),rows)
 save(OUT/"SUMMARY.json",dict(status="COMPLETED_SEALED_OUTPUT_ANALYSIS",economic_runs=0,summaries=summaries,fee_net_tail_definition="Complete 0-to-0 round net cash plus booked dividends divided by every buy gross plus buy fees, >=30%; no MFE; no terminal forced close",independent_first_layer_definition="Earliest actual buy layer in each 0-to-0 round; closed layer counts even if the whole round remains open",new_tail_counts={w:{k:sum(r["window"]==w and r["cohort"]=="NEW_MONTH_ROUND" and r["tail_change"]==k for r in tailcompare) for k in ["DMI_ONLY_OBSERVED_TAIL","PVR_ONLY_OBSERVED_TAIL","BOTH_TAIL"]} for w in windows},inherited_tail_counts={w:{k:sum(r["window"]==w and r["cohort"]=="INHERITED_ROUND" and r["tail_change"]==k for r in tailcompare) for k in ["DMI_ONLY_OBSERVED_TAIL","PVR_ONLY_OBSERVED_TAIL","BOTH_TAIL"]} for w in windows},limitations=["Two short development-seen conditional windows, not a long-run win-rate estimate or cross-regime validation.","2026 inherited complete original PVR account. Month mark-to-mark contribution is separate from full-lifetime closed round PnL.","Fixed future-known stock universe and current industry classification are NON-PIT.","Original next-open +/-5bp, dated constraints and prior20 volume proxy; actual historical tradability and external dividend payment evidence UNKNOWN.","January final pending not executed; open rounds right-censored; no February or 2024 new run.","New entry identity comparison is not causal paired-trade matching when start dates/lifecycles differ."],sources=inputs,seconds_analysis=time.monotonic()-started))
 for p,h in inputs.items():assert sha(p)==h
 save(OUT/"OUTPUT_SHA256.json",{p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name!="OUTPUT_SHA256.json"})
 print("ANALYSIS_DONE",json.dumps(summaries,default=str),flush=True)
if __name__=="__main__":main()
