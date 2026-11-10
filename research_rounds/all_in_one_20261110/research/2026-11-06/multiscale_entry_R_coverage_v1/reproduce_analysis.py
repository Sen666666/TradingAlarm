# Read-only reproduction. Historical descriptive audit only. Does not save files or run accounts.
import sys,time,math,json,hashlib
sys.dont_write_bytecode=True
from pathlib import Path
import numpy as np,pandas as pd
start=time.monotonic()
O=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1")
U=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031")
d=pd.read_csv(O/"ALL_FIRST_ENTRIES.csv");d["row_id"]=np.arange(len(d))
for c in ["signal_day","entry_day","closed_day"]:d[c]=pd.to_datetime(d[c])
m={r["symbol"]:r for r in json.loads((U/"STOCK_MANIFEST.json").read_text())}
def calc(f,cp):
 n=len(f); out=np.full((n,6),np.nan); mode=None;seg=None;ext=delta=H=L=None
 for i,(C,ss,z) in enumerate(zip(f.close.to_numpy(float),f.segment_id.to_numpy(),cp.z.to_numpy(float))):
  x=math.log(C)
  if seg!=ss:mode=None;seg=ss;H=L=None
  if not math.isfinite(z):continue
  if mode is None:mode="BOOT";ext=x;lo=hi=x;delta=math.sqrt(21)*z
  elif mode=="BOOT":
   if x<=lo:lo=x
   if x>=hi:hi=x
   if x-lo>=delta:L=lo;mode="UP";ext=x;delta=math.sqrt(21)*z
   elif hi-x>=delta:H=hi;mode="DOWN";ext=x;delta=math.sqrt(21)*z
  elif mode=="UP":
   if x>=ext:ext=x
   if ext-x>=delta:H=ext;mode="DOWN";ext=x;delta=math.sqrt(21)*z
  elif mode=="DOWN":
   if x<=ext:ext=x
   if x-ext>=delta:L=ext;mode="UP";ext=x;delta=math.sqrt(21)*z
  ll=ext if mode=="DOWN" else L
  depth=H-ll if H is not None and ll is not None else math.nan
  rho=min(1.,max(0.,(x-ll)/depth)) if depth>0 else math.nan
  risk=max(H-x,0)/(depth+delta) if depth>=0 else math.nan
  out[i]=[risk,rho,depth,delta,1. if mode=="UP" else 0. if mode=="DOWN" else -1.,float(cp.receipt.iloc[i])]
 return out
features=[];issues=[];prefix=0; hashes={}
groups=list(d.groupby("sid",sort=True))
for k,(sid,g) in enumerate(groups):
 if sid not in m:issues.append((sid,"manifest missing"));continue
 refs=m[sid]["refs"];f=pd.read_parquet(refs["facts"]);cp=pd.read_parquet(refs["CP1"])
 if not f.index.equals(cp.index):raise ValueError((sid,"facts CP index mismatch"))
 arr=calc(f,cp);idx=f.index.get_indexer(g.signal_day)
 for row,ii in zip(g.itertuples(),idx):
  if ii<0:issues.append((sid,str(row.signal_day),"signal date missing"));continue
  vals=arr[ii];features.append(dict(row_id=row.row_id,R=vals[0],rho=vals[1],depth=vals[2],delta=vals[3],up=vals[4],fresh_cp=bool(vals[5])))
 # one physical truncation per stock at the first account signal, compared against full prefix output
 first=int(idx[idx>=0].min())
 pre=calc(f.iloc[:first+1],cp.iloc[:first+1])
 np.testing.assert_allclose(pre,arr[:first+1],rtol=0,atol=0,equal_nan=True);prefix+=1
 if k%200==0:print("PROGRESS",k,len(groups),round(time.monotonic()-start,1),flush=True)
features=pd.DataFrame(features);d=d.merge(features,on="row_id",how="left",validate="one_to_one")
assert d.loc[d.R.notna(),"R"].between(0,1).all()
d["outcome"]=np.where(~d.closed,"OPEN",np.where(d.round_pnl>0,"WIN",np.where(d.round_pnl<0,"LOSS","ZERO")))
d["signal_quarter"]=d.signal_day.dt.to_period("Q").astype(str)
d["Rbin"]=pd.cut(d.R,[-1e-12,0,.25,.5,.75,1.000000001],labels=["0","(0,.25]","(.25,.5]","(.5,.75]","(.75,1]"])
d["round_ge30"]=d.closed & d.round_return_on_cumulative_cost.ge(.3)
print("DONE",json.dumps(dict(seconds=time.monotonic()-start,stocks=len(groups),prefix_checks=prefix,issues=issues,rows=len(d),unknown_R=int(d.R.isna().sum()),first_entries_sha256=hashlib.sha256((O/"ALL_FIRST_ENTRIES.csv").read_bytes()).hexdigest(),manifest_sha256=hashlib.sha256((U/"STOCK_MANIFEST.json").read_bytes()).hexdigest())),flush=True)
print(d.groupby(["account","year","outcome"]).agg(n=("sid","size"),R_known=("R","count"),R_mean=("R","mean"),R_median=("R","median"),R_positive=("R",lambda x:int((x>0).sum())),fresh=("fresh_cp","sum")).to_string(),flush=True)

d["entry_quarter"]=d.entry_day.dt.to_period("Q").astype(str)
def match(g):
 edges=[];rows=[]
 for day,a in g[g.closed & g.R.notna() & g.stock_H1_decision.notna() & g.PVR_decision.notna()].groupby("signal_day"):
  w=a[a.round_pnl>0];l=a[a.round_pnl<0];cand=[]
  for wi,wr in w.iterrows():
   for li,lr in l.iterrows():
    dh=abs(wr.stock_H1_decision-lr.stock_H1_decision);dp=abs(wr.PVR_decision-lr.PVR_decision)
    if dh<=5 and dp<=5:cand.append((math.hypot(dh,dp),str(wr.sid),str(lr.sid),int(wr.row_id),int(lr.row_id),wi,li,dh,dp))
  used=set()
  for dist,ws,ls,wrid,lrid,wi,li,dh,dp in sorted(cand):
   if wi in used or li in used:continue
   used.update([wi,li]);wr=g.loc[wi];lr=g.loc[li]
   rows.append(dict(day=day,year=int(wr.year),quarter=str(wr.entry_day.to_period('Q')),winner_sid=ws,loser_sid=ls,winner_row=wrid,loser_row=lrid,H1_distance=dh,PVR_distance=dp,distance=dist,winner_R=float(wr.R),loser_R=float(lr.R),delta_R=float(lr.R-wr.R),weak=bool(wr.weak_market),both_fresh=bool(wr.fresh_cp and lr.fresh_cp)))
 return pd.DataFrame(rows)
pairs=[]
for ac,g in d.groupby("account"):
 for scope,q in [("all_closed",g),("fresh_only",g[g.fresh_cp]),("2022_original_yearend",g[(g.year==2022)&g.closed_in_entry_year])]:
  pp=match(q);pp["account"]=ac;pp["scope"]=scope;pairs.append(pp)
pairs=pd.concat(pairs,ignore_index=True)
def ps(g):
 v=g.delta_R
 return pd.Series(dict(n=len(g),days=g.day.nunique(),stocks=len(set(g.winner_sid)|set(g.loser_sid)),mean_delta=v.mean(),median_delta=v.median(),positive=int((v>0).sum()),negative=int((v<0).sum()),zero=int((v==0).sum()),H1_distance_mean=g.H1_distance.mean(),PVR_distance_mean=g.PVR_distance.mean()))
print("PAIR_TOTAL");print(pairs.groupby(["account","scope"]).apply(ps,include_groups=False).round(5).to_string())
print("PAIR_YEAR");print(pairs[pairs.scope=="all_closed"].groupby(["account","year"]).apply(ps,include_groups=False).round(5).to_string())
print("PVR_QUARTER");print(pairs[(pairs.account=="PVR")&(pairs.scope=="all_closed")].groupby("quarter").apply(ps,include_groups=False).round(5).to_string())
print("PVR_WEAK");print(pairs[(pairs.account=="PVR")&(pairs.scope=="all_closed")].groupby("weak").apply(ps,include_groups=False).round(5).to_string())
print("FRESH_PVR_YEAR");print(pairs[(pairs.account=="PVR")&(pairs.scope=="fresh_only")].groupby("year").apply(ps,include_groups=False).round(5).to_string())

def sm(g):
 c=g[g.closed];w=c[c.round_pnl>0];l=c[c.round_pnl<0]
 return pd.Series(dict(n=len(g),closed=len(c),wins=len(w),losses=len(l),open=int((~g.closed).sum()),R_unknown=int(g.R.isna().sum()),R_positive=int((g.R>0).sum()),w_Rpositive=int((w.R>0).sum()),l_Rpositive=int((l.R>0).sum()),winrate=len(w)/len(c) if len(c) else np.nan,big60=int(g.big60_posthoc.sum()),complete60=int(g.complete60.sum()),big60_Rpositive=int((g.big60_posthoc & (g.R>0)).sum()),round_ge30=int(g.round_ge30.sum()),round_ge30_Rpositive=int((g.round_ge30 & (g.R>0)).sum()),mean_R=g.R.mean(),mean_q=(1/(1+g.R)).mean()))
p=d[d.account=="PVR"]; y22=p[(p.year==2022)&p.closed_in_entry_year]
print("SCOPE");print(pd.DataFrame({name:sm(g) for name,g in [("PVR_all",p),("PVR_fresh",p[p.fresh_cp]),("PVR_2022_oldclosed",y22),("PVR_WEAK",p[p.weak_market]),("PVR_NONWEAK",p[~p.weak_market])]}).round(5).to_string())
print("PVR_BINS");print(p.groupby("Rbin",observed=True).apply(sm,include_groups=False).round(5).to_string())
print("2022_OLD_BINS");print(y22.groupby("Rbin",observed=True).apply(sm,include_groups=False).round(5).to_string())
print("PVR_WEAK_BINS");print(p[p.weak_market].groupby("Rbin",observed=True).apply(sm,include_groups=False).round(5).to_string())
print("PVR_YEAR_WEAK");print(p.groupby(["year","weak_market"]).apply(sm,include_groups=False).round(5).to_string())
print("MISSING");print(d[d.R.isna()][["account","sid","signal_day","year","outcome","first_kind","fresh_cp","stock_H1_decision","PVR_decision"]].to_string(index=False))
print("MATCH_COVERAGE",len(pairs[(pairs.account=="PVR")&(pairs.scope=="all_closed")])*2,int(p.closed.sum()),p[p.closed].round_pnl.gt(0).sum())
