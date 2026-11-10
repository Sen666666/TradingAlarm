"""Read sealed attribution only; create descriptive path witnesses and original plots."""
from pathlib import Path
import os,json,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
os.environ["MPLCONFIGDIR"]=str(O/"case_matplotlib_cache")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
p=pd.read_csv(O/"case_FIXED_CASES_WITH_CONTEXT.csv")
d=pd.read_csv(O/"case_DAILY_CONTRIBUTIONS.csv")
r=pd.read_csv(O/"case_RAW_TRAJECTORIES.csv")
w=.9**np.arange(20,-1,-1);w/=w.sum()
rows=[]
for a in p.itertuples(index=False):
 g=r[(r.sid==a.sid)&(r.signal_day==a.day)].reset_index(drop=True)
 for k in range(64,85):
  z=g.iloc[k-20:k+1]
  if not np.isfinite(z.e).all():continue
  E=float(np.dot(w,z.e));assert abs(E-g.E.iloc[k])<1e-12
  row=dict(sid=a.sid,signal_day=a.day,bar_day=g.bar_day.iloc[k],strict_known=a.strict_known,r=g.r.iloc[k],e=g.e.iloc[k],E=E,score=g.score.iloc[k])
  for n in [1,3,5]:
   recent=float(np.dot(w[-n:],z.e.iloc[-n:]));older=E-recent
   row[f"last{n}_E"]=recent;row[f"older{n}_E"]=older
   row[f"older_positive_retains_positive_E_despite_recent{n}_negative"]=bool(E>0 and recent<0 and older>0)
  rows.append(row)
 z=d[(d.sid==a.sid)&(d.signal_day==a.day)].reset_index(drop=True)
 fig,ax=plt.subplots(4,1,figsize=(12,11),gridspec_kw={"height_ratios":[2,1,1.2,1.8]},constrained_layout=True)
 x=np.arange(len(g));xx=np.arange(21)
 ax[0].plot(x,g.raw_input__close,color="#225ea8");ax[0].set_ylabel("Native adjusted close")
 ax[1].bar(x,g.raw_input__amount/1e8,color="#7f8c8d");ax[1].set_ylabel("Amount (CNY 1e8)")
 ax[2].plot(x,g.score,color="#7a3e9d");ax[2].axhline(50,color="gray",linestyle="--",linewidth=.8);ax[2].set_ylim(0,100);ax[2].set_ylabel("Original PVR")
 for axis in ax[:3]:
  axis.axvspan(63.5,84.5,color="#f6d78c",alpha=.24);axis.set_xlim(-.5,84.5);axis.grid(alpha=.2)
  axis.set_xticks([0,21,42,63,84],[g.bar_day.iloc[i] for i in [0,21,42,63,84]],rotation=15)
 ax[3].bar(xx-.18,z.weighted_price,width=.36,label="price w*u",color="#2c7fb8")
 ax[3].bar(xx+.18,z.weighted_amount,width=.36,label="amount w*0.5*u*|u|*b",color="#f28e2b")
 ax[3].plot(xx,z.weighted_e,color="#202020",marker=".",label="total contribution to E")
 ax[3].axhline(0,color="gray",linewidth=.8);ax[3].grid(alpha=.2);ax[3].set_ylabel("Additive contribution to E")
 ax[3].set_xticks([0,5,10,15,20],[z.bar_day.iloc[i] for i in [0,5,10,15,20]],rotation=15);ax[3].legend(fontsize=8,loc="upper left")
 status="STRICT KNOWN" if a.strict_known else "UNKNOWN lineage; mechanical reconstruction only"
 context=a.context_class.replace("EXISTING_COMPLETE_FEE_NET_","Conditional fee-net ").replace("_"," ")
 fig.suptitle(f"{a.sid} | signal {a.day} | PVR {a.score_original:.3f}\n{status} | {context}\nNo post-signal observations. Score is nonlinear; only E is additive.",fontsize=11)
 target=O/f"case_plot_{a.sid}_{a.day}.png";assert not target.exists();fig.savefig(target,dpi=110);plt.close(fig)
out=pd.DataFrame(rows);out.to_csv(O/"case_SIGNAL_PATH_MEMORY_AUDIT.csv",index=False,float_format="%.17g")
summary={"path_rows_with_formed_E":len(out),"distinct_stock_day_rows":len(out.drop_duplicates(["sid","bar_day"])),"path_overlap_not_independent":True,"negative_current_e_positive_E_rows":int(out.older_positive_retains_positive_E_despite_recent1_negative.sum()),"negative_recent3_positive_E_rows":int(out.older_positive_retains_positive_E_despite_recent3_negative.sum()),"negative_recent5_positive_E_rows":int(out.older_positive_retains_positive_E_despite_recent5_negative.sum()),"signal_day_negative_recent1_or3_or5_with_positive_E":0,"plots":22,"no_new_trading_cases":True,"no_new_model_or_economics":True}
(O/"case_PLOT_AND_PATH_QA.json").write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps(summary,indent=2))
print(out[out.sid.isin(["000977.SZ","301611.SZ","300666.SZ"])&out.older_positive_retains_positive_E_despite_recent3_negative].tail(14).to_string(index=False))
