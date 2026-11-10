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
rows=[];cases=[]
for cut in a.CUTS:
 t=a.CAL.get_loc(cut)
 p=r[r.t.ge(t-504)&r.t.lt(t)&r.ordinary&r.feature_known&r.ordinary_known_at.lt(cut)]
 groups=[("TEMPLATE_UNION",template,g) for template,g in p.groupby("template_id")]
 groups += [("COHORT",cohort,g) for cohort,g in p.groupby("cohort_id")]
 for level,name,g in groups:
  tail=g[g.ordinary_value.gt(9000)].sort_values(["ordinary_value","sid","round_id"],ascending=[False,True,True])
  val=tail.ordinary_value;total=float(val.sum());n=len(tail)
  rows.append(dict(cut=str(cut.date()),aggregation=level,group=name,template_id=g.template_id.iloc[0],mature_PDC_n=len(g),tail_n=n,tail_sids=tail.sid.nunique(),tail_signal_dates=tail.signal_day.nunique(),tail_roots=tail.price_root.nunique(),tail_net_sum_CNY=total,tail_Y_sum=total/3000,tail_mean_CNY=float(val.mean()) if n else None,tail_median_CNY=float(val.median()) if n else None,tail_mean_Y=float(val.mean()/3000) if n else None,tail_median_Y=float(val.median()/3000) if n else None,tail_max_CNY=float(val.max()) if n else None,largest_one_fraction=float(val.max()/total) if n else None,largest_five_fraction=float(val.head(5).sum()/total) if n else None,top_five_count=min(n,5),meaning="MATURE_PROXY_ORIGINAL_FULL_NET_ONLY_NOT_ACCOUNT_OR_IID"))
  for rank,(_,v) in enumerate(tail.head(5).iterrows(),1):
   cases.append(dict(cut=str(cut.date()),aggregation=level,group=name,rank=rank,cohort=v.cohort_id,template_id=v.template_id,round_id=v.round_id,sid=v.sid,signal_day=str(v.signal_day.date()),label_known_at=str(v.ordinary_known_at),net_CNY=float(v.ordinary_value),Y=float(v.ordinary_value/3000)))
a.csv("EXTENDED_PDC_MATURE_TAIL_AMPLITUDE.csv",pd.DataFrame(rows))
a.csv("EXTENDED_PDC_MATURE_TOP5_TAIL_CASES.csv",pd.DataFrame(cases))
assert all(a.sha(p)==v for p,v in hashes.items())
a.dump("EXTENDED_TAIL_AMPLITUDE_QA.json",dict(source_hashes=hashes,sources_unchanged=True,tail_fixed="net/3000>3",only_cut_mature_PDC=True,old2022_separate_template=True,models_fit=0,economic_runs=0))
print(pd.DataFrame(rows).to_csv(index=False))
