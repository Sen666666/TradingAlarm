"""Exploratory price/share diffusion and immediate index observer. No account backtest."""
from pathlib import Path
import json, hashlib, time
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
S=O.parent
BASE=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031")
META=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json")
CSI=Path("/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USHI1B0300.csv")
HASH={}
def bind(p,h=None):
 p=Path(p);z=hashlib.sha256(p.read_bytes()).hexdigest()
 if h: assert z==h,(str(p),"SHA mismatch")
 HASH[str(p.resolve())]=z
 return p
def save(n,v):
 (O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
def main():
 start=time.monotonic()
 bind(__file__)
 meta=json.loads(bind(META).read_text());sm=json.loads(bind(BASE/"STOCK_MANIFEST.json").read_text());im=json.loads(bind(BASE/"INDUSTRY_MANIFEST.json").read_text())
 mask=pd.read_parquet(bind(S/"causal_launch_v5/burst_raw/U_T_MASK_ALL_FIXED_DATES.parquet"))
 dates=sorted(mask.date.unique());symbols=[r["symbol"] for r in sm];nstock=len(symbols)
 sectors=sorted(r["series"] for r in im)
 names={meta[s]["sector_id"]:meta[s]["industry"] for s in symbols};sidsec=np.array([meta[s]["sector_id"] for s in symbols])
 market=pd.read_csv(bind(CSI),parse_dates=["date"]).set_index("date");cal=pd.DatetimeIndex(market.index).as_unit("ns")
 i0=cal.get_loc(pd.Timestamp(dates[0]))-24;i1=cal.get_loc(pd.Timestamp(dates[-1]))
 grid=cal[i0:i1+1];dateidx={d:grid.get_loc(pd.Timestamp(d)) for d in dates}
 close=np.full((nstock,len(grid)),np.nan);amount=np.full_like(close,np.nan)
 for i,r in enumerate(sm):
  paths=[p for p in r["source_sha256"] if "/prepared" in p and p.endswith("/signal.parquet")];assert len(paths)==1
  f=pd.read_parquet(bind(paths[0],r["source_sha256"][paths[0]]),columns=["close","amount"]);f.index=pd.DatetimeIndex(f.index).as_unit("ns")
  q=f.reindex(grid);close[i]=pd.to_numeric(q.close,errors="coerce");amount[i]=pd.to_numeric(q.amount,errors="coerce")
  if(i+1)%400==0:print("loaded",i+1,"stocks",round(time.monotonic()-start,1),flush=True)
 U=mask.pivot(index="sid",columns="date",values="qualified_U_t").reindex(index=symbols,columns=dates).to_numpy(bool)
 R=np.full_like(close,np.nan);R[:,1:]=np.log(close[:,1:]/close[:,:-1])
 price={}
 for r in im:
  p=r["refs"]["CP1_input"];f=pd.read_parquet(bind(p,r["output_sha256"][p]),columns=["close","segment_id"]);f.index=pd.DatetimeIndex(f.index).as_unit("ns");f=f.reindex(cal)
  c=f.close;seg=f.segment_id;valid=c.gt(0)&np.isfinite(c)&seg.notna();rv=np.log(c/c.shift()).where(valid&valid.shift(fill_value=False)&seg.eq(seg.shift()))
  sigma=(1.4826*rv.abs().shift().rolling(63,min_periods=63).median()).clip(lower=np.log1p(.001))
  continuous=seg.rolling(65,min_periods=65).max().eq(seg.rolling(65,min_periods=65).min())
  price[r["series"]]=pd.DataFrame({"r":rv,"s":sigma.where(continuous)},index=cal)
 rows=[];contrib=[];sourcesvalid=0
 for ti,day in enumerate(dates):
  t=dateidx[day];ut=U[:,ti];assert np.isfinite(close[ut,t-24:t+1]).all() and np.isfinite(amount[ut,t-24:t+1]).all()
  assert (close[ut,t-24:t+1]>0).all() and (amount[ut,t-24:t+1]>0).all()
  sourcesvalid+=int(ut.sum())
  daypositions=list(range(t-4,t+1));a=amount[:,daypositions];r=R[:,daypositions]
  baseline=np.stack([amount[:,d-20:d].mean(axis=1) for d in daypositions],axis=1)
  for sec in sectors:
   inside=ut&(sidsec==sec);outside=ut&(sidsec!=sec);n=int(inside.sum());nout=int(outside.sum())
   if not n or not nout:continue
   rm=np.median(r[outside],axis=0);scale=np.maximum(np.median(np.abs(r[outside]-rm),axis=0),np.log1p(.001))
   outside_exp=a[outside].sum(axis=0)/baseline[outside].sum(axis=0)
   g=(a[inside]/baseline[inside])/outside_exp
   p=np.maximum(0,np.tanh((r[inside]-rm)/scale))*(r[inside]>0)
   v=np.maximum(0,(g-1)/(g+1));z=p*v
   zsum=z.sum(axis=0);z2=(z*z).sum(axis=0)
   hhi=np.divide(z2,zsum*zsum,out=np.zeros(5),where=zsum>0)
   neff=np.divide(zsum*zsum,z2,out=np.zeros(5),where=z2>0)
   J=zsum/(n+10)*(1-hhi);J=np.maximum(J,0)
   D=float(J[-1]);med=float(np.median(J));Q=float(np.sqrt(D*med))
   sec_exp=a[inside].sum(axis=0)/baseline[inside].sum(axis=0);gsec=sec_exp/outside_exp
   rp=float(price[sec].loc[day,"r"]);sp=float(price[sec].loc[day,"s"])
   L=float(max(0,np.tanh(rp/sp))*max(0,np.tanh((rp-rm[-1])/sp))*gsec[-1]/(1+gsec[-1])) if np.isfinite(rp) and np.isfinite(sp) else np.nan
   vals=dict(date=day,sector_id_static=sec,industry=names[sec],n=n,market_outside_n=nout,D=D,Q=Q,J_median5=med,J_days=json.dumps(J.tolist()),positive_J_days=int((J>1e-15).sum()),mean_joint_today=float(zsum[-1]/n),joint_count=int((z[:,-1]>0).sum()),price_count=int((p[:,-1]>0).sum()),share_count=int((v[:,-1]>0).sum()),N_eff=float(neff[-1]),HHI=float(hhi[-1]),largest_contributor_fraction=float(z[:,-1].max()/zsum[-1])if zsum[-1]>0 else 0.,sector_amount_relative_expansion=float(gsec[-1]),sector_amount_expansion=float(sec_exp[-1]),outside_amount_expansion=float(outside_exp[-1]),outside_return_median=float(rm[-1]),index_r=rp,index_sigma_prior63=sp,index_excess_r=rp-float(rm[-1]),L=L,membership_PIT_verified=False)
   rows.append(vals)
   if names[sec] in ["软件开发","半导体","厨卫电器"]:
    ix=np.flatnonzero(inside)
    for k in np.argsort(z[:,-1])[-5:][::-1]:
     contrib.append(dict(date=day,industry=names[sec],sid=symbols[ix[k]],stock_r=float(r[inside][k,-1]),p=float(p[k,-1]),share_expansion=float(g[k,-1]),v=float(v[k,-1]),z=float(z[k,-1])))
  if (ti+1)%20==0: print("dates",ti+1,"/",len(dates),flush=True)
 f=pd.DataFrame(rows)
 for col in ["D","Q","L"]:
  f[col+"_rank_min"]=f.groupby("date")[col].rank(method="min",ascending=False)
  f[col+"_positive"]=f[col]>1e-15
  f[col+"_rank_positive"]=f[col+"_rank_min"].where(f[col+"_positive"])
 f["joint_fraction"]=f.joint_count/f.n
 f["joint_is_strict_majority"]=2*f.joint_count>f.n
 f["one_joint_contributor"]=f.joint_count.eq(1)
 f["index_positive"]=f.index_r.gt(0)
 # Save scores before reading existing case outcomes/ranks. No future returns are read anywhere.
 f.to_csv(O/"ALL90_FIXED_DATES.csv",index=False);f.to_parquet(O/"ALL90_FIXED_DATES.parquet",index=False)
 pd.DataFrame(contrib).to_csv(O/"TOP_STOCK_CONTRIBUTORS.csv",index=False)
 cases=pd.read_csv(bind(S/"causal_launch_v5/MAIN_84_DAILY_CAUSAL.csv"))
 keys=cases[["case_id","date","sector_id_static","relative_session"]]
 caseout=keys.merge(f,on=["date","sector_id_static"],validate="many_to_one");caseout.to_csv(O/"MAIN84_DAILY_EXAMPLES.csv",index=False)
 anchor=f[f.date.isin(["2024-09-24","2024-10-08","2026-01-05","2026-01-15"]) & f.industry.isin(["软件开发","半导体","通信设备","厨卫电器"])]
 print("ANCHORS\n"+anchor[["date","industry","n","joint_count","N_eff","D","D_rank_min","Q","Q_rank_min","L","L_rank_min","sector_amount_relative_expansion","index_r","index_excess_r"]].to_string(index=False),flush=True)
 print("SOFTWARE_924_PATH\n"+f[(f.industry=="软件开发")&f.date.between("2024-09-18","2024-10-18")][["date","n","joint_count","N_eff","D_rank_min","Q_rank_min","L_rank_min","Q","L","sector_amount_relative_expansion"]].to_string(index=False),flush=True)
 print("SEMI_2026_PATH\n"+f[(f.industry=="半导体")&f.date.between("2025-12-25","2026-01-26")][["date","n","joint_count","N_eff","D_rank_min","Q_rank_min","L_rank_min","Q","L","sector_amount_relative_expansion"]].to_string(index=False),flush=True)
 print("SPARSE_CANDIDATES\n"+f[(f.n<=3)&(f.L_rank_min<=10)].sort_values(["date","L_rank_min"])[["date","industry","n","joint_count","N_eff","Q","Q_rank_min","L_rank_min","index_r"]].head(35).to_string(index=False),flush=True)
 for d in ["2024-09-24","2024-10-08","2026-01-05","2026-01-15"]:
  print("TOP",d,json.dumps({c:f[(f.date==d)&f[c+"_positive"]].sort_values(c,ascending=False).head(8)[["industry",c,"n"]].to_dict("records")for c in ["Q","L"]},ensure_ascii=False),flush=True)
 save("SOURCE_SHA256.json",HASH)
 save("SUMMARY.json",dict(rows=len(f),dates=len(dates),stocks=nstock,source_valid_qualified_stock_dates=sourcesvalid,positive_Q_rows=int((f.Q>1e-15).sum()),positive_L_rows=int((f.L>1e-15).sum()),time_seconds=time.monotonic()-start,no_accounts=True,no_future_return_reads=True,no_parameter_search=True,membership_PIT_verified=False))
 print("DONE",round(time.monotonic()-start,2),flush=True)
if __name__=="__main__":main()
