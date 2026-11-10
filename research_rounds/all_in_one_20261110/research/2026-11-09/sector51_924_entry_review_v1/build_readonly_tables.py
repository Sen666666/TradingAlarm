
from pathlib import Path
import json,collections,hashlib
from decimal import Decimal as D
import numpy as np,pandas as pd
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
O=Path("/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1")
O.mkdir(parents=True,exist_ok=False)
M=Path("/Users/bytedance/Documents/ChatGPT/money")
G={"证券保险":["D061","D062"],"银行":["C6D6","C6D7","C6D8","C6D9"],"半导体":["BCA5","BCA6","C6EC","C6ED","C6EE","D0B8","D0B9"]}
master=pd.read_csv(M/"research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv")
ro=pd.read_csv(R/"momentum_persistence_breadth_v1/FIXED_ROSTER.csv")
ro=ro.merge(master[["symbol","industry_leaf_code","industry_leaf_name"]],on="symbol",how="left",validate="1:1")
ro["sector51"]=ro.industry_leaf_code.map({x:g for g,ls in G.items() for x in ls})
ro[ro.sector51.notna()].to_csv(O/"CORE_CLASSIFICATION.csv",index=False)
Q=R/"momentum_persistence_breadth_v1/canonical_mu3_comparison_v2"
k=pd.read_parquet(Q/"KNOWN3.parquet"); r=pd.read_parquet(Q/"RIGHT3.parquet")
ps=pd.read_parquet(R/"pvr_persistence_breadth_v1/STOCK_DAILY.parquet",columns=["sid","day","state"]).pivot(index="day",columns="sid",values="state").reindex(index=k.index,columns=k.columns)
both=k&ps.ge(0); right=r&both
out=[]
for name in G:
 cols=ro[ro.sector51.eq(name)].symbol.tolist();N=len(cols);kk=both[cols];rr=right[cols]
 K=kk.sum(axis=1);n=rr.sum(axis=1);U=N-K;pair=kk&kk.shift(3,fill_value=False);J=pair.sum(axis=1)
 ent=(pair&rr&~rr.shift(3,fill_value=False)).sum(axis=1);leave=(pair&~rr&rr.shift(3,fill_value=False)).sum(axis=1);delta=ent-leave
 lo=n.ge(3)&((n.mul(3).ge(N)&J.gt(0)&delta.gt(0))|n.mul(2).ge(N))
 hi=(n+U).ge(3)&(((n+U).mul(3).ge(N)&(delta.gt(0)|J.eq(0)))|(n+U).mul(2).ge(N))
 gate=pd.Series(np.where(lo,1,np.where(~hi,0,-1)),index=k.index)
 f=pd.DataFrame(dict(sector51=name,N=N,K=K,n=n,U=U,paired_K=J,entered3=ent,left3=leave,net_diffusion3=delta,breadth_lower=n/N,state=gate))
 f["sector_true3"]=gate.eq(1).rolling(3).sum().eq(3)
 f["majority3"]=n.ge(N/2).rolling(3).sum().eq(3)
 f["new_birth"]=gate.eq(1)&gate.shift().eq(0)
 f["next_common_open"]=pd.Series(k.index,index=k.index).shift(-1)
 out.append(f.loc["2024-09-02":"2024-10-31"].rename_axis("day").reset_index())
signal=pd.concat(out,ignore_index=True);signal.to_csv(O/"CORE_DAILY_51CLASS_SIGNALS.csv",index=False)
sm=json.loads(Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json").read_text())
sources={x["symbol"]:next(p for p in x["source_sha256"] if p.endswith("/signal.parquet")) for x in sm}
source_hashes={}
frames={}
def load(sid):
 if sid not in frames:
  p=Path(sources[sid]);frames[sid]=pd.read_parquet(p).loc["2024-08-01":"2024-10-31"];source_hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 return frames[sid]
arms={"original":"tech407_admission_mask_ablation_v1/run_all1709_once","no_risk":"no_risk_ceilings_python_retry_v1/run_no_risk_ceilings_once","no_probe_cap":"no_risk_unpooled_probe_sector4_v1/run_unpooled_probe_sector4_once"}
smap=ro.set_index("symbol").sector51.to_dict();daily=[];tradeout=[];equityout=[];snapchecks=[]
for arm,path in arms.items():
 P=R/"m3_ab_shared_probe_v1"/path
 archives=json.loads((P/"ARCHIVES.json").read_text());journal=json.loads((P/"EXACT_TRADE_JOURNAL.json").read_text())
 ledger=json.loads((P/"DAY_LEDGER.json").read_text());claims=json.loads((P/"CLAIM_LEDGER.json").read_text());bridges=json.loads((P/"EQUITY_BRIDGES.json").read_text())
 for nfile in ["ARCHIVES.json","EXACT_TRADE_JOURNAL.json","DAY_LEDGER.json","CLAIM_LEDGER.json","EQUITY_BRIDGES.json"]:
  p=P/nfile;source_hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 qty=collections.defaultdict(int);cashflow=collections.defaultdict(lambda:D(0));buycash=collections.defaultdict(lambda:D(0));claimval=collections.defaultdict(lambda:D(0));fees=collections.defaultdict(lambda:D(0))
 for dayrec in ledger:
  day=dayrec["day"][:10]
  if day>"2024-10-31":break
  cl=dayrec["CLOSE"];assert cl["certified"]
  for tx in journal:
   if tx["day"][:10]!=day:continue
   meta=archives[tx["round_id"]];sid=meta["sid"];g=smap.get(sid)
   if not isinstance(g,str):continue
   isbuy=tx["side"].startswith("buy");q=int(tx["q"]);qty[sid]+=q if isbuy else -q;assert qty[sid]>=0
   cash=sum((D(v["cash_delta"]) for v in tx["report_only_allocations"].values()),D(0));cashflow[g]+=cash
   if isbuy:buycash[g]-=cash
   fees[g]+=D(tx["exact_whole_order_fee"])
   tradeout.append(dict(arm=arm,day=day,sector51=g,sid=sid,name=meta["name"],side=tx["side"],qty=q,price=tx["exact_price"],fee=tx["exact_whole_order_fee"],cash_delta=str(cash)))
  for ev in claims:
   if ev["day"][:10]!=day:continue
   sid=archives[ev["round_id"]]["sid"];g=smap.get(sid)
   if isinstance(g,str):
    v=D(str(ev.get("cash_delta",0)))+D(str(ev.get("receivable_delta",0)));claimval[g]+=v
    equityout.append(dict(arm=arm,day=day,sector51=g,sid=sid,event=ev["event"],cash_delta=ev.get("cash_delta",0),receivable_delta=ev.get("receivable_delta",0)))
  values=collections.defaultdict(lambda:D(0));counts=collections.Counter()
  for sid,q in qty.items():
   if q==0:continue
   f=load(sid);dt=pd.Timestamp(day);assert dt in f.index and f.at[dt,"price_eligible"] and f.at[dt,"observed_bar"],(sid,day)
   v=D(str(f.at[dt,"raw_close"]))*q;values[smap[sid]]+=v;counts[smap[sid]]+=1
  nav=D(cl["NAV"])
  for g in G:
   pnl=values[g]+cashflow[g]+claimval[g]
   daily.append(dict(arm=arm,day=day,sector51=g,stocks=counts[g],market_value=str(values[g]),weight_pct_NAV=str(values[g]/nav*100),cumulative_buy_cash=str(buycash[g]),cumulative_trade_cashflow=str(cashflow[g]),recognized_dividend_and_claim_value=str(claimval[g]),marked_fee_net_pnl=str(pnl),contribution_pct_seed=str(pnl/D(1200000)*100),paid_trade_fees=str(fees[g]),account_NAV=cl["NAV"],account_stock_weight_pct=str(D(cl["gross_inventory"])/nav*100),account_seed_return_pct=str((nav/D(1200000)-1)*100)))
  cp=P/("CHECKPOINT_"+day+".json")
  if cp.exists():
   x=json.loads(cp.read_text());vals=collections.defaultdict(lambda:D(0))
   for h in x["snapshot"]["holdings"]:
    g=smap.get(h["sid"])
    if isinstance(g,str):vals[g]+=D(str(h["mark"]))*int(h["qty"])
   for g in G:assert abs(vals[g]-values[g])<D("0.00001"),(arm,day,g,vals[g],values[g])
   snapchecks.append(dict(arm=arm,day=day,checked=True))
  for ev in bridges:
   if ev["day"][:10]==day and isinstance(smap.get(archives[ev["round_id"]]["sid"]),str):
    assert ev["kind"] in ["HELD_COORDINATE","PENDING_COORDINATE_Q0"],ev
pd.DataFrame(daily).to_csv(O/"CORE_DAILY_EXISTING_ACCOUNTS_RELABELED.csv",index=False)
pd.DataFrame(tradeout).to_csv(O/"CORE_EXISTING_TRADES.csv",index=False)
pd.DataFrame(equityout).to_csv(O/"CORE_EQUITY_EVENTS.csv",index=False)
# All-current sector raw-price availability is a diagnostic, not a promise of limit-order execution.
av=[];window=pd.DatetimeIndex(signal.day.unique()).sort_values()
for g in G:
 cols=ro[ro.sector51.eq(g)].symbol.tolist()
 for dt in window:
  nxt=signal.loc[(signal.sector51.eq(g))&signal.day.eq(dt),"next_common_open"].iloc[0]
  knownright=[s for s in cols if dt in right.index and bool(right.at[dt,s])]
  valid=0;flat=0;missing=0;gaps=[]
  for sid in knownright:
   f=load(sid)
   if nxt not in f.index or not bool(f.at[nxt,"observed_bar"]) or not bool(f.at[nxt,"price_eligible"]) or not bool(f.at[nxt,"volume_eligible"]):
    missing+=1;continue
   valid+=1
   flat+=int(f.at[nxt,"raw_high"]==f.at[nxt,"raw_low"])
   if dt in f.index:gaps.append((f.at[nxt,"open"]/f.at[dt,"close"]-1)*100)
  av.append(dict(sector51=g,signal_close=dt,next_common_open=nxt,right_members=len(knownright),next_valid_daily_OHLCV=valid,next_missing=missing,next_flat_HL_expost_diagnostic=flat,median_next_open_gap_pct=float(np.median(gaps)) if gaps else None,note="Next date is earliest conditional execution; H/L and volume are ex-post diagnostics only, not order permission; exact historical limits/order queues not certified."))
pd.DataFrame(av).to_csv(O/"CORE_NEXT_OPEN_OBSERVABILITY.csv",index=False)
(O/"SOURCE_HASHES.json").write_text(json.dumps(source_hashes,ensure_ascii=False,indent=2))
qa=dict(account_runs=0,signal_reaggregation_only=True,current_classification=True,member_pool=1709,groups={g:dict(full_current=int(master.industry_leaf_code.isin(c).sum()),research=int(ro.sector51.eq(g).sum())) for g,c in G.items()},saved_checkpoint_checks=snapchecks,sources_unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in source_hashes.items()),price_sources=len(frames),no_execution_guarantee=True,new_strategy_not_run=True)
(O/"QA.json").write_text(json.dumps(qa,ensure_ascii=False,indent=2))
print(json.dumps(qa,ensure_ascii=False))
df=pd.DataFrame(daily)
print(df[df.day.isin(["2024-09-11","2024-09-13","2024-09-18","2024-09-23","2024-09-30","2024-10-08","2024-10-31"])][["arm","day","sector51","weight_pct_NAV","marked_fee_net_pnl"]].to_string(index=False))
