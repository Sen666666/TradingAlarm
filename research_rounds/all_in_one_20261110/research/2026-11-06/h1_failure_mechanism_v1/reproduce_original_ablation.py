
from pathlib import Path
import numpy as np,pandas as pd,json,hashlib
O=Path("/Users/bytedance/Documents/Codex/2026-11-06/h1_failure_mechanism_v1")
z=np.load("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
D=pd.DatetimeIndex(z["dates"]);sy=z["symbols"].astype(str);C=z["close"];SEG=z["segment"];OB=z["obs_count"];S=z["score"];N=z["nref"];rows=[]
for day,ss in [("2024-09-19",["002583.SZ","300085.SZ"]),("2024-09-24",["002583.SZ","300085.SZ","URFI881129","URFI881272"]),("2026-01-05",["300666.SZ","301611.SZ","603061.SH"]),("2026-01-12",["300666.SZ"]),("2026-01-15",["300666.SZ","301611.SZ","603061.SH","URFI881121"])]:
 t=D.get_loc(day);v=C[t-np.arange(5)*63];ok=np.isfinite(v).all(axis=0)&(v>0).all(axis=0)&(SEG[t-np.arange(5)*63]==SEG[t]).all(axis=0)&(OB[t]>=6);W=(v[:-1]/v[1:]-1)*np.array([.4,.2,.2,.2])[:,None];raw=np.round(W.sum(axis=0),12);recent=np.round(W[0],12)
 for s in ss:
  j=np.where(sy==s)[0][0];k=ok&np.array([x.startswith("URFI")==s.startswith("URFI")for x in sy]);n=k.sum();p=lambda a:100*((a[k]<a[j]).sum()+.5*(a[k]==a[j]).sum())/n
  assert n==N[t,j]and p(raw)==S[t,j]
  rows.append({"day":day,"sid":s,"same_h_reference_N":int(n),"original_H1_percentile":p(raw),"recent63_only_percentile_same_reference":p(recent),"weighted_recent":W[0,j],"weighted_old":W[1:,j].sum()})
pd.DataFrame(rows).to_csv(O/"ORIGINAL_SAME_REFERENCE_OLD_WINDOW_ABLATION.csv",index=False)
a=pd.read_csv(O/"SIX_DATE_SELECTED_DESCRIPTIVE_LABELS.csv");q=a[(a.day=="2026-01-15")&(a.K==20)];h=q[q.strategy=="H1"];b=q[q.strategy=="B_confirmed"];added=b[~b.sid.isin(h.sid)];removed=h[~h.sid.isin(b.sid)]
x={"added":len(added),"removed":len(removed),"added_positive":int(added.end20.gt(0).sum()),"removed_positive":int(removed.end20.gt(0).sum()),"added_end20_mean":added.end20.mean(),"removed_end20_mean":removed.end20.mean(),"difference_of_sums_over_same_complete19":(added.end20.sum()-removed.end20.sum())/19,"actual_B_minus_H1":b.end20.mean()-h.end20.mean(),"all_changed_labels_complete":bool(added.complete20.all()and removed.complete20.all()),"same_incomplete_stock":sorted(h[~h.complete20].sid)==sorted(b[~b.complete20].sid)}
(O/"JAN15_EXACT_REPLACEMENT_ATTRIBUTION.json").write_text(json.dumps(x,indent=2)+"\n");print(x)
