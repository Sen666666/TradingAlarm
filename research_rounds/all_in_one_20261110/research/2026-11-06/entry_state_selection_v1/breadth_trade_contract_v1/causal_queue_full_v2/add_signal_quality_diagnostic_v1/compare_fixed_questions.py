from pathlib import Path
import pandas as pd,numpy as np,json
P=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/breadth_trade_contract_v1/causal_queue_full_v2/add_signal_quality_diagnostic_v1")
a=pd.read_csv(P/"ALL_ACTUAL_ADD_FEATURES.csv")
# Fixed small-sample matching rule: same policy/birth window/signal day/industry,
# different stocks; |PVR|<=5 points and |profit/core_cost|<=2pct. No outcome used.
pairs=[]
for (pol,yr),g in a.groupby(["policy","window"]):
 g=g.sort_values(["event_day","event_id","sid"]).drop_duplicates(["sid","signal_day"])
 candidates=[]
 for (day,sec),v in g.groupby(["signal_day","sector"]):
  ids=list(v.index)
  for k,i in enumerate(ids):
   for j in ids[k+1:]:
    x,y=v.loc[i],v.loc[j]
    dp=abs(x.pvr-y.pvr);du=abs(x.u_fraction-y.u_fraction)
    if x.sid!=y.sid and dp<=5 and du<=.02:
     candidates.append((dp/5+du/.02,day,sec,i,j))
 used=set()
 for dist,day,sec,i,j in sorted(candidates):
  if i in used or j in used:continue
  used|={i,j};x,y=g.loc[i],g.loc[j]
  r=dict(policy=pol,window=yr,signal_day=day,sector=sec,i=i,j=j,stock_x=x.sid,stock_y=y.sid,name_x=x["name"],name_y=y["name"],pvr_x=x.pvr,pvr_y=y.pvr,u_x=x.u_fraction,u_y=y.u_fraction,add_net_x=x.add_net,add_net_y=y.add_net,return_x=x.add_return,return_y=y.add_return,closed_both=x.add_closed and y.add_closed,distance=dist)
  for f in ["pvr_progress","dual_receipt","price_breakout","breadth_progress","cp_distance","amount_multiple","pvr_change_cp"]:
   r[f+"_x"]=x[f];r[f+"_y"]=y[f]
  pairs.append(r)
pair=pd.DataFrame(pairs);pair.to_csv(P/"MATCHED_PAIRS.csv",index=False)
sums=[];effects=[]
def m(g):
 c=g[g.add_closed];w=c[c.add_net>0];l=c[c.add_net<0]
 return dict(n=len(g),closed=len(c),sum_net=c.add_net.sum(),mean_net=c.add_net.mean(),win=c.add_net.gt(0).mean(),mean_return=c.add_return.mean(),payoff=w.add_net.mean()/-l.add_net.mean() if len(w)*len(l) else np.nan)
for (pol,yr),g in a.groupby(["policy","window"]):
 for mode,z in [("events",g),("first_stock_signal",g.sort_values(["event_day","event_id"]).drop_duplicates(["sid","signal_day"]))]:
  for f in ["pvr_progress","dual_receipt","price_breakout","breadth_progress"]:
   for value,v in z.groupby(f):
    sums.append(dict(policy=pol,window=yr,mode=mode,feature=f,value=value,**m(v)))
  c=z[z.add_closed]
  # Posterior right tail ONLY measures retention, never selects the rule.
  top=c.nlargest(max(1,int(np.ceil(len(c)*.1))),"add_net")
  for f in ["pvr_progress","dual_receipt","price_breakout","breadth_progress"]:
   t=c[c[f].eq(True)];u=c[c[f].eq(False)]
   if not len(t) or not len(u):continue
   # Stock and day means estimate each cluster equally, not independent rows.
   de=t.add_return.mean()-u.add_return.mean()
   ds=t.groupby("sid").add_return.mean().mean()-u.groupby("sid").add_return.mean().mean()
   dd=t.groupby("signal_day").add_return.mean().mean()-u.groupby("signal_day").add_return.mean().mean()
   rng=np.random.default_rng(48201);v=c[c[f].notna()].copy()
   si,ss=pd.factorize(v.sid);di,dsid=pd.factorize(v.signal_day)
   expo=v[f].astype(bool).to_numpy();ret=v.add_return.to_numpy()
   bs=[]
   for _ in range(1000):
    sw=rng.multinomial(len(ss),np.ones(len(ss))/len(ss));dw=rng.multinomial(len(dsid),np.ones(len(dsid))/len(dsid));w=sw[si]*dw[di]
    wt=w[expo].sum();wc=w[~expo].sum()
    if wt and wc:bs.append(np.dot(ret[expo],w[expo])/wt-np.dot(ret[~expo],w[~expo])/wc)
   q=np.quantile(bs,[.025,.975]) if bs else [np.nan,np.nan]
   effects.append(dict(policy=pol,window=yr,mode=mode,feature=f,event_return_diff=de,stock_equal_diff=ds,date_equal_diff=dd,cluster95_low=q[0],cluster95_high=q[1],top_decile_count=len(top),top_decile_kept=int(top[f].eq(True).sum()),top_decile_positive_net_kept=top.loc[top[f].eq(True),"add_net"].sum()/top.add_net.sum()))
pd.DataFrame(sums).to_csv(P/"FIXED_GROUPS.csv",index=False)
pd.DataFrame(effects).to_csv(P/"CLUSTER_SENSITIVITY.csv",index=False)
print("MAIN_EFFECTS",pd.DataFrame(effects).query("policy==\"original\"").to_string(index=False))
print("PAIR_COUNTS",pair.groupby(["policy","window"]).agg(n=("i","size"),closed=("closed_both","sum")).to_string())
for (pol,yr),g in pair[pair.closed_both].groupby(["policy","window"]):
 for f in ["pvr_progress","dual_receipt","price_breakout","breadth_progress"]:
  z=g[g[f+"_x"].notna()&g[f+"_y"].notna()&g[f+"_x"].ne(g[f+"_y"])]
  diff=(z.return_x-z.return_y)*np.where(z[f+"_x"].eq(True),1,-1)
  print("PAIR_EFFECT",pol,yr,f,len(z),diff.mean())
print("COUNTEREXAMPLES")
for yr,g in a[a.policy.eq("original")&a.add_closed].groupby("window"):
 cols=["name","sid","event_day","signal_day","pvr","pvr_prev_cp","pvr_change_cp","amount_multiple","cp_distance","breadth_change3","dual_receipt","price_breakout","u_fraction","q","add_net","add_return"]
 print(yr,"PVR_DECLINED_WINNERS",g[g.pvr_progress.eq(False)].nlargest(4,"add_net")[cols].to_string(index=False))
 print(yr,"PVR_PROGRESS_LOSERS",g[g.pvr_progress.eq(True)].nsmallest(4,"add_net")[cols].to_string(index=False))
print("PAIRED_OPPOSITE",pair.query("policy==\"original\" and closed_both").loc[lambda g:g.add_net_x.gt(0).ne(g.add_net_y.gt(0))].to_string(index=False))
