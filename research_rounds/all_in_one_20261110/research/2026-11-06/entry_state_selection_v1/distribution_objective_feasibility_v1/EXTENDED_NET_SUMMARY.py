"""Fixed >3R mature PDC tail amplitude, stratified by template; no fit or economics."""
from pathlib import Path
import sys,json
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O));import EXTENDED_SUPPORT_AUDIT as a
xs=[];hashes={}
for cohort in ["2023","2024JanAug"]:
 x,h=a.load_new(cohort);hashes.update(h);fp=O/("EXTENDED_"+cohort+"_PDC_FEATURES.parquet");hashes[str(fp)]=a.sha(fp)
 f=pd.read_parquet(fp);x=x.merge(f[["round_id","feature_known"]],on="round_id",validate="one_to_one");xs.append(x)
oldp=a.R/"closed_price_supervised_pilot_support_v1/ALL_ORIGINAL_PRICE_ROWS.parquet";old=pd.read_parquet(oldp);hashes[str(oldp)]=a.sha(oldp)
for w,cohort,template in [("2022","old2022","LEGACY_2022_DIFFERENT_RESPONSIBILITY_GUARD"),("2024","old2024SepDec",a.TEMPLATE)]:
 x=old[old.window_label.eq(w)].copy();x["cohort_id"]=cohort;x["template_id"]=template;x["ordinary_known_at"]=x.label_known_at_proxy;x["ordinary_value"]=x.net_pnl.where(x.ordinary);x["t"]=a.CAL.get_indexer(x.signal_day);xs.append(x)
r=pd.concat(xs,ignore_index=True,sort=False)
r["decision_key"]=[json.dumps([sid,str(day.date()),template]) for sid,day,template in zip(r.sid,r.signal_day,r.template_id)]
assert not r.decision_key.duplicated().any()

rows=[]
for cut in a.CUTS:
 t=a.CAL.get_loc(cut)
 p=r[r.t.ge(t-504)&r.t.lt(t)&r.ordinary&r.feature_known&r.ordinary_known_at.lt(cut)]
 groups=[("TEMPLATE_UNION",template,g) for template,g in p.groupby("template_id")]
 groups += [("COHORT",cohort,g) for cohort,g in p.groupby("cohort_id")]
 for level,name,g in groups:
  v=g.ordinary_value;w=v[v>0];l=v[v<0];n=len(v)
  rows.append(dict(cut=str(cut.date()),aggregation=level,group=name,template_id=g.template_id.iloc[0],feature_scope="PDC_KNOWN",label_scope="STRICT_ORDINARY_CUT_MATURE_ORIGINAL_ALL_RETAINED",n=n,W=len(w),L=len(l),Z=int(v.eq(0).sum()),w=float(len(w)/n) if n else None,mean_winner_CNY=float(w.mean()) if len(w) else None,mean_loser_CNY=float(l.mean()) if len(l) else None,mean_win_over_abs_mean_loss=float(w.mean()/abs(l.mean())) if len(w) and len(l) else None,net_sum_CNY=float(v.sum()),net_mean_CNY=float(v.mean()) if n else None,profit_factor=float(w.sum()/abs(l.sum())) if len(l) else None,tail_gt3R_n=int(v.gt(9000).sum()),stocks=g.sid.nunique(),signal_dates=g.signal_day.nunique(),meaning="CLOSURE_COVERAGE_CONDITIONED_DESCRIPTION_NOT_POLICY_OR_ACCOUNT"))
a.csv("EXTENDED_MATURE_PDC_NET_SUMMARY.csv",pd.DataFrame(rows))
assert all(a.sha(p)==v for p,v in hashes.items())
a.dump("EXTENDED_NET_SUMMARY_QA.json",dict(source_hashes=hashes,sources_unchanged=True,only_cut_mature_PDC=True,no_selection_or_threshold_tuning=True,old2022_separate_template=True,models_fit=0,economic_runs=0))
print(pd.DataFrame(rows).to_csv(index=False))
