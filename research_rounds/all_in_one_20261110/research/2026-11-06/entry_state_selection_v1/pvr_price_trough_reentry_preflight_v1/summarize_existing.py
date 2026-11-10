"""Read-only old-economics summaries and four fixed new-token feasibility checks. No lifecycle."""
from pathlib import Path
import json,ast,sys,hashlib
from decimal import Decimal as D
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent;E=R/"m3_stock_birth_during_sector_v1"
U=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031")
B=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025")
S={}
def src(p):
 p=Path(p);S[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
paths=[E/"relative_priority_equity_run_2022_v1/report/CORE_AND_FULL_ROUNDS.csv",E/"cash_equity_baseline_2024_v1/report/CORE_AND_FULL_ROUNDS.csv"]
z=pd.concat([pd.read_csv(src(p),low_memory=False) for p in paths],ignore_index=True);z=z[z.arm.eq("A_UNION_B")].copy()
z["band"]=pd.cut(z.PVR_score,[-np.inf,60,75,85,np.inf],labels=["LE60","60_75","75_85","GT85"])
rows=[]
for (w,b),g in z.groupby(["window","band"],observed=True):
 c=g[g.evidence_usable_closed.eq(True)];pos=c[c.core_net>0];neg=c[c.core_net<=0]
 rows.append(dict(window=w,band=b,permits=len(g),known_closed=len(c),other=len(g)-len(c),wins=len(pos),winrate=len(pos)/len(c),core_sum=c.core_net.sum(),mean_core=c.core_net.mean(),full_sum=c.net_pnl.sum(),mean_full=c.net_pnl.mean(),core_tail50=(c.core_return>=.5).sum(),all_fees_known_closed=c.all_fees.sum(),win_loss_mean_ratio=pos.core_net.mean()/(-neg.core_net.mean())))
pd.DataFrame(rows).to_csv(O/"EXISTING_PVR_BANDS_DESCRIPTIVE.csv",index=False)
windows=json.loads(src(O/"FIXED_WINDOWS.json").read_text());coverage=[]
for sid,(a,b) in windows.items():
 covered=a[:4] in ["2022","2024"];g=z[z.sid.eq(sid)&z.signal_day.between(a,b)]
 coverage.append(dict(sid=sid,window_start=a,window_end=b,economic_source_scope="DYNAMIC_AB_2022_OR_2024_AVAILABLE" if covered else "NOT_COVERED_BY_THE_TWO_DYNAMIC_SOURCES",matched_original_permits=len(g) if covered else None,zero_permits_is_known=bool(covered and len(g)==0),unobserved_not_zero=not covered))
pd.DataFrame(coverage).to_csv(O/"EXISTING_ECONOMIC_COVERAGE.csv",index=False)
# Use unchanged, definition-only native sizing; never import the script's account driver.
SOURCE=E/"relative_priority_v1/simulate.py";txt=src(SOURCE).read_text();tree=ast.parse(txt)
names={"finite","true","false","flags","getmeta","fee","size","checkclose","DayFrame"}
sys.path.insert(0,str(B/"code"))
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
for p in [B/"code/market_rules.py",B/"code/sector_account.py"]:src(p)
for n in tree.body:
 if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names:exec(compile(ast.Module(body=[n],type_ignores=[]),str(SOURCE)+":only-definitions","exec"),globals())
NAV=D("1200000");INIT=D("24000");RISK=D("3000");SLIP=D(".0005")
rules=json.loads(src(B/"inputs-v2/market-rules.json").read_text());proxies=json.loads(src(B/"inputs-v2/economic-protocol.json").read_text())["approved_proxy_ids"]
manifest={m["symbol"]:m for m in json.loads(src(U/"STOCK_MANIFEST.json").read_text())}
raw={};capacity={};meta={};closecache={};source={};facts={}
def load(sid):
 if sid in raw:return
 m=manifest[sid];p=next(p for p in m["source_sha256"] if p.endswith("/signal.parquet"))
 q=pd.read_parquet(src(p));source[sid]=q
 assert S[str(p)]==m["source_sha256"][p]
 facts[sid]=pd.read_parquet(src(m["refs"]["facts"]))
 raw[sid]=DayFrame(q[["raw_open","raw_close","adjustment_factor","source_kind","source_path","segment_id","observed_bar","price_eligible","volume_eligible","source_invalid","synthetic_event_bar"]])
 v=q.raw_volume[q.raw_volume.gt(0)];capacity[sid]=(v.rolling(20,min_periods=20).mean()*.01).reindex(q.index).ffill().to_dict()
events=pd.read_csv(src(O/"SIGNAL_EVENTS_PRELABEL.csv"),parse_dates=["day"]);events=events[events.i_buy.eq(0)&events.CP.eq(0)]
cal=pd.DatetimeIndex(sorted(pd.read_parquet(src(R/"momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet"),columns=["day"]).day.unique()))
qin=pd.concat([pd.read_parquet(src(R/"fast_entry_equity_2022_v1/ALL_MARKET_INPUTS_2022.parquet")),pd.read_parquet(src(R/"fast_entry_equity_2022_v1/STARTUP_MARKET_INPUTS.parquet"))],ignore_index=True)
out=[]
for ev in events.itertuples():
 sid,d=ev.sid,ev.day;load(sid);f=facts[sid].loc[d];rr=dict(sid=sid,day=d,i_floor=float(f.i_floor))
 c=checkclose(rr);row=dict(sid=sid,day=str(d.date()),**c)
 pq=qin[qin.sid.eq(sid)&qin.day.eq(d)]
 row["original_continuing_Q"]=bool(pq.iloc[0].continuing_Q) if len(pq)==1 and pd.notna(pq.iloc[0].continuing_Q) else None
 row["original_Q_source_row_count"]=len(pq)
 covered=str(d.year) in ["2022","2024"]
 sg=z[z.sid.eq(sid)].copy();sd=pd.to_datetime(sg.signal_day);en=pd.to_datetime(sg.entry_day);ex=pd.to_datetime(sg.exit_day)
 held=sg[(en<=d)&(ex>d)];pending=sg[sd.eq(d)];uncertain=sg[(sd<=d)&~sg.evidence_usable_closed.eq(True)]
 row["baseline_state"]=("HELD" if len(held) else "UNKNOWN_OR_PENDING" if len(uncertain) or len(pending) else "FLAT_FROM_COMPLETE_ORIGINAL_ROUNDS") if covered else "NOT_COVERED"
 row["baseline_state_round_ids"]="|".join(held.round_id.astype(str))
 k=cal.get_loc(d);nd=cal[k+1] if k+1<len(cal) else None;row["next_common_day"]=str(nd.date()) if nd is not None else None
 p=source[sid];a=p.loc[d];b=p.loc[nd] if nd is not None and nd in p.index else None
 row["next_open_size_status"]="UNKNOWN"
 if b is not None and np.isfinite(b.raw_open) and b.raw_open>0 and all(str(a[v])==str(b[v]) for v in ["source_kind","source_path","segment_id"]) and np.isclose(a.adjustment_factor,b.adjustment_factor,rtol=1e-11):
  fl=D(str(f.i_floor))/D(str(a.adjustment_factor));op=D(str(b.raw_open));row["next_raw_open"]=float(op)
  if op<=fl:row["next_open_size_status"]="BELOW_PROTECTION_NOFILL"
  else:
   nq,nfee,nrisk,_,_=size(sid,nd,op*(1+SLIP),fl,INIT,RISK,int(c["prior20_capacity"]))
   row.update(next_open_size_status="SIZE_PASS_ONLY_NOT_FILL" if nq else "MINIMUM_LOT_NOFILL",next_q=nq,next_buy_fee=float(nfee),next_plan_risk=float(nrisk),next_cash_required=float(D(nq)*op*(1+SLIP)+nfee))
 row["not_full_execution"]="No event-slot competition, account cash, limit-lock queue, pending state, actual trade or future payoff simulated."
 out.append(row)
pd.DataFrame(out).to_csv(O/"FOUR_NEW_TOKENS_FEASIBILITY.csv",index=False)
src(Path(__file__))
(O/"SUPPLEMENT_SOURCE_HASHES.json").write_text(json.dumps(S,indent=2))
print(pd.DataFrame(out).to_string(index=False));print(pd.DataFrame(coverage).to_string(index=False))
