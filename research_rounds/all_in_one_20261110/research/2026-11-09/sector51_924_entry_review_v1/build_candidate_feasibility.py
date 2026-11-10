import pandas as pd,numpy as np,json,sys
from pathlib import Path
from decimal import Decimal as D
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1");B=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025")
sys.path.insert(0,str(B/"code"))
from market_rules import version_on,market_identity_on
from sector_account import QuantityRule,FeeComponent,FeeSchedule
rules=json.loads((B/"inputs-v2/market-rules.json").read_text());proxies=json.loads((B/"inputs-v2/economic-protocol.json").read_text())["approved_proxy_ids"]
def meta(s,dt):
 day=str(dt.date());ident=market_identity_on(rules,s,day,proxies);v=version_on(rules["fee_versions"][ident["venue"]],day,proxies)["schedule"]
 return QuantityRule(**version_on(rules["quantity_versions"][s],day,proxies)["rule"]),FeeSchedule(v["schedule_id"],tuple(FeeComponent(**x) for x in v["components"])),D(str(rules["security_metadata"][s]["par_value"]))
def fee(s,dt,q,p,side):
 qr,fs,pa=meta(s,dt);return sum(fs.incremental(side,D(q)*p,{}, {},1,shares=q,par_value=pa).values(),D(0))
ro=pd.read_csv(R/"momentum_persistence_breadth_v1/FIXED_ROSTER.csv");ids=ro[ro.sector_name.isin(["证券","保险"])].symbol.tolist()
names=ro.set_index("symbol").name.to_dict();U=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031")
ms={a["symbol"]:a for a in json.loads((U/"STOCK_MANIFEST.json").read_text())}
Q=R/"momentum_persistence_breadth_v1/canonical_mu3_comparison_v2";rr=pd.read_parquet(Q/"RIGHT3.parquet");kk=pd.read_parquet(Q/"KNOWN3.parquet")
pv=pd.read_parquet(R/"pvr_persistence_breadth_v1/STOCK_DAILY.parquet");pv=pv[pv.sid.isin(ids)].set_index(["sid","day"])
fs={s:pd.read_parquet(ms[s]["refs"]["facts"]) for s in ids};raw={s:pd.read_parquet(next(p for p in ms[s]["source_sha256"] if p.endswith("/signal.parquet"))) for s in ids}
cp={s:pd.read_parquet(ms[s]["refs"]["CP1"]) for s in ids}
O=Path("/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1")
for signal,entry in [("2024-09-06","2024-09-09"),("2024-09-18","2024-09-19")]:
 t=pd.Timestamp(signal);e=pd.Timestamp(entry);rows=[]
 for s in ids:
  v=pv.loc[(s,t)]
  if kk.at[t,s] and rr.at[t,s] and v.state>=0 and fs[s].at[t,"i_target"]==1:
   qr,_,_=meta(s,e);q=next(q for q in range(1,1000) if qr.buy_floor(q)>0);p=D(str(raw[s].at[e,"raw_open"]))*D("1.0005");cost=q*p+fee(s,e,q,p,"buy")
   floor=float(fs[s].at[t,"i_floor"])/float(raw[s].at[e,"adjustment_factor"]); capacity=int(raw[s].raw_volume.loc[:t].tail(20).mean()*.01); row=dict(sid=s,name=names[s],PVR=float(v.score),q=q,cost=float(cost),open_above_prior_I=float(raw[s].at[e,"raw_open"])>floor,prior20_capacity_pass=q<=capacity)
   for ds in (["2024-09-11","2024-09-12"] if signal=="2024-09-06" else ["2024-09-19","2024-09-20","2024-09-23"]):
    d=pd.Timestamp(ds);px=D(str(raw[s].at[d,("raw_open" if ds=="2024-09-12" else "raw_close")]))*D("0.9995")
    net=q*px-fee(s,d,q,px,"sell")-cost;row[ds+"_net"]=float(net);row[ds+"_CP"]=bool(cp[s].at[d,"receipt"]);row[ds+"_I"]=bool(fs[s].at[d,"i_target"])
    if ds=="2024-09-20":
     op=pd.Timestamp("2024-09-23");px2=D(str(raw[s].at[op,"raw_open"]))*D("0.9995");net2=q*px2-fee(s,op,q,px2,"sell")-cost;row["Sep23_open_net"]=float(net2);row["Sep23_add_pass"]=bool(net>0 and net2>0 and row[ds+"_CP"] and row[ds+"_I"])
   rows.append(row)
 z=pd.DataFrame(rows).sort_values(["PVR","sid"],ascending=[False,True]); z.to_csv(O/("MINIMUM_LOT_FEASIBILITY_"+signal+".csv"),index=False);print("\nSIGNAL",signal,"MEMBERS",len(z),"MINLOT_COST",z.cost.sum(),"PCT_NAV",z.cost.sum()/1200000*100);print(z.round(4).to_string(index=False));print("SUM_NET",z.filter(like="_net").sum().to_dict())

allrows=[]
for ds in ["2024-09-06","2024-09-18","2024-09-19","2024-09-20","2024-09-23"]:
 t=pd.Timestamp(ds)
 for s in ids:
  v=pv.loc[(s,t)]
  if not (kk.at[t,s] and rr.at[t,s] and v.state>=0):continue
  d=raw[s].loc[t];f=fs[s].loc[t];past=raw[s].loc[:t];valid=past.close.notna()&past.close.gt(0);past=past[valid]
  j=len(past)-1;e=raw[s].index[raw[s].index.get_loc(t)+1];qr,_,_=meta(s,e);q=next(q for q in range(1,1000) if qr.buy_floor(q)>0)
  price=D(str(raw[s].at[e,"raw_open"]))*D("1.0005");cost=q*price+fee(s,e,q,price,"buy")
  prior20=past.close.iloc[-21:-1];volmedian=past.raw_volume.iloc[-21:-1].median()
  allrows.append(dict(signal_close=ds,next_common_open=str(e.date()),sid=s,name=names[s],I_qualified=bool(f.i_target==1),PVR_score=float(v.score),close=float(d.raw_close),return3_pct=float((past.close.iloc[-1]/past.close.iloc[-4]-1)*100),return5_pct=float((past.close.iloc[-1]/past.close.iloc[-6]-1)*100),close_above_prior20high=bool(d.close>prior20.max()),gap_to_prior20high_pct=float((d.close/prior20.max()-1)*100),raw_volume_to_prior20median=float(d.raw_volume/volmedian),I_protection_gap_pct=float((d.close/f.i_floor-1)*100),CP_receipt=bool(cp[s].at[t,"receipt"]),min_lot=q,min_lot_nextopen_cost_EXPOST=float(cost),next_open_raw_EXPOST=float(raw[s].at[e,"raw_open"])))
full=pd.DataFrame(allrows)
for col,label in [("PVR_score","PVR_rank"),("return3_pct","return3_rank"),("gap_to_prior20high_pct","breakout20_rank")]:full[label]=full.groupby("signal_close")[col].rank(ascending=False,method="min")
full.to_csv(O/"ALL_SECURITIES_INSURANCE_CANDIDATES_PRE924.csv",index=False)
summ=[]
for day,x in full.groupby("signal_close"):
 q=x[x.I_qualified]
 summ.append(dict(day=day,M3_known_right=len(x),M3_and_I=len(q),all_min_lot_cost_at_nextopen=float(q.min_lot_nextopen_cost_EXPOST.sum()),pct_120w_NAV=float(q.min_lot_nextopen_cost_EXPOST.sum()/1200000*100),median_return3_pct=float(q.return3_pct.median()),median_volume_ratio=float(q.raw_volume_to_prior20median.median()),CP_receipts=int(q.CP_receipt.sum())))
pd.DataFrame(summ).to_csv(O/"CANDIDATE_BREADTH_AND_CAPITAL_NEED.csv",index=False)
print(pd.DataFrame(summ).to_string(index=False))
