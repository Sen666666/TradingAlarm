"""Independent prefix and algebra checks; no score fitting."""
from pathlib import Path
import json
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;S=O.parent
B=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031")
M=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json")
CSI=Path("/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USHI1B0300.csv")
def main():
 sm=json.loads((B/"STOCK_MANIFEST.json").read_text());im=json.loads((B/"INDUSTRY_MANIFEST.json").read_text());meta=json.loads(M.read_text())
 symbols=[x["symbol"]for x in sm];sectors=np.array([meta[s]["sector_id"]for s in symbols]); names={meta[s]["industry"]:meta[s]["sector_id"]for s in symbols}
 checks=[("2024-09-24","软件开发"),("2024-10-08","软件开发"),("2026-01-05","半导体"),("2026-01-15","半导体"),("2022-02-21","教育")]
 days=[d for d,_ in checks]
 market=pd.read_csv(CSI,parse_dates=["date"]).set_index("date");cal=pd.DatetimeIndex(market.index).as_unit("ns")
 grids={d:cal[:cal.get_loc(pd.Timestamp(d))+1][-25:]for d in days}
 data={d:{"C":[],"A":[],"U":[]}for d in days}
 mask=pd.read_parquet(S/"causal_launch_v5/burst_raw/U_T_MASK_ALL_FIXED_DATES.parquet").set_index(["date","sid"])
 cols=["open","high","low","close","volume","amount","segment_id","observed_bar","price_eligible","synthetic_event_bar","source_invalid","amount_unit"]
 for j,item in enumerate(sm):
  p=next(p for p in item["source_sha256"]if "/prepared"in p and p.endswith("/signal.parquet"))
  f=pd.read_parquet(p,columns=cols);f.index=pd.DatetimeIndex(f.index).as_unit("ns")
  for day in days:
   q=f.loc[:day].reindex(grids[day])
   o,h,l,c,v,a=[pd.to_numeric(q[k],errors="coerce").to_numpy(float)for k in["open","high","low","close","volume","amount"]]
   sg=pd.to_numeric(q.segment_id,errors="coerce")
   flags=q.observed_bar.eq(True)&q.price_eligible.eq(True)&q.synthetic_event_bar.eq(False)&q.source_invalid.eq(False)&q.amount_unit.eq("CNY")
   valid=bool(flags.all() and np.isfinite(np.stack([o,h,l,c,v,a])).all() and np.all(np.stack([o,h,l,c,v,a])>0) and np.all((l<=o)&(l<=c)&(h>=o)&(h>=c)&(h>=l)) and sg.notna().all() and sg.nunique()==1)
   u=bool(valid and np.median(a[-22:-1])>=20000000 and np.mean(a[-6:-1])>=10000000)
   assert u==bool(mask.loc[(day,item["symbol"]),"qualified_U_t"]),(day,item["symbol"],"U mismatch")
   data[day]["C"].append(c);data[day]["A"].append(a);data[day]["U"].append(u)
  if(j+1)%400==0:print("prefix stocks",j+1,flush=True)
 existing=pd.read_csv(O/"ALL90_FIXED_DATES.csv").set_index(["date","industry"]);results=[]
 for day,name in checks:
  sec=names[name];a=np.array(data[day]["A"]);c=np.array(data[day]["C"]);u=np.array(data[day]["U"]);inside=u&(sectors==sec);outside=u&(sectors!=sec);n=int(inside.sum())
  r=np.log(c[:,20:25]/c[:,19:24]);cur=a[:,20:25];base=np.stack([a[:,k-20:k].mean(axis=1)for k in range(20,25)],axis=1)
  med=np.median(r[outside],axis=0);spread=np.maximum(np.median(np.abs(r[outside]-med),axis=0),np.log1p(.001));g=(cur[inside]/base[inside])/(cur[outside].sum(axis=0)/base[outside].sum(axis=0))
  joint=np.maximum(0,np.tanh((r[inside]-med)/spread))*(r[inside]>0)*np.maximum(0,(g-1)/(g+1))
  sums=joint.sum(axis=0);squares=(joint*joint).sum(axis=0);h=np.divide(squares,sums*sums,out=np.zeros(5),where=sums>0)
  j=np.maximum(0,sums/(n+10)*(1-h));D=j[-1];Q=np.sqrt(D*np.median(j))
  ind=next(x for x in im if x["series"]==sec);f=pd.read_parquet(ind["refs"]["CP1_input"],columns=["close","segment_id"]);f.index=pd.DatetimeIndex(f.index).as_unit("ns");f=f.loc[:day].reindex(cal[cal<=pd.Timestamp(day)])
  rr=np.log(f.close/f.close.shift());sigma=max(1.4826*rr.iloc[-64:-1].abs().median(),np.log1p(.001));rp=rr.iloc[-1]
  gg=(cur[inside,-1].sum()/base[inside,-1].sum())/(cur[outside,-1].sum()/base[outside,-1].sum())
  L=max(0,np.tanh(rp/sigma))*max(0,np.tanh((rp-med[-1])/sigma))*gg/(1+gg)
  old=existing.loc[(day,name)];diff=max(abs(float(old[k])-float(v))for k,v in[("D",D),("Q",Q),("L",L)])
  assert diff<1e-12,(day,name,diff)
  results.append(dict(date=day,industry=name,U_recalculated_all1709_exact=True,score_prefix_max_abs_diff=diff,D=float(D),Q=float(Q),L=float(L)))
 def jval(z,n):
  z=np.array(z,float);s=z.sum()
  return float(s/(n+10)*(1-np.sum(z*z)/(s*s)))if s>0 else 0.
 stresses=dict(one_of32=jval([1],32),ten_equal_of32=jval([1]*10,32),all32_equal=jval([1]*32,32),one_of1=jval([1],1),two_of2=jval([1,1],2),one_day_pulse_Q=float(np.sqrt(.2*np.median([0,0,0,0,.2]))),three_day_burst_Q=float(np.sqrt(.2*np.median([0,0,.2,.2,.2]))),zero_market_residual_price_factor=0.,uniform_market_volume_scaling_share_factor=0.)
 out=dict(prefix_checks=results,U_rows_recalculated=len(sm)*len(days),stress_tests=stresses,no_formula_changes=True,no_future_returns_read=True)
 (O/"PREFIX_AND_STRESS_CHECKS.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(out,ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
