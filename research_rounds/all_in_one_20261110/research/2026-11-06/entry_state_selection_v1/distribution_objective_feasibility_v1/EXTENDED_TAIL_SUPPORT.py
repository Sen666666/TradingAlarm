"""Age and concentration support only, by true as-of cut; no fit or economics."""
from pathlib import Path
import sys,json
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O));import EXTENDED_SUPPORT_AUDIT as a
rows=[];concentrations=[];hashes={}
for cohort in ["2023","2024JanAug"]:
 x,h=a.load_new(cohort);hashes.update(h);fp=O/("EXTENDED_"+cohort+"_PDC_FEATURES.parquet");hashes[str(fp)]=a.sha(fp)
 f=pd.read_parquet(fp);x=x.merge(f[["round_id","feature_known"]],on="round_id",validate="one_to_one")
 x["exit_age"]=a.CAL.get_indexer(x.exit_day)-a.CAL.get_indexer(x.entry_day)+1
 for cut in a.CUTS:
  t=a.CAL.get_loc(cut);g=x[x.t.ge(t-504)&x.t.lt(t)&x.ordinary&x.ordinary_known_at.lt(cut)&x.feature_known].copy()
  g["age_bin"]=pd.cut(g.exit_age,[0,5,20,60,120,252,np.inf],labels=["1-5","6-20","21-60","61-120","121-252",">252"])
  for age,v in g.groupby("age_bin",observed=False):
   rows.append(dict(cohort=cohort,template_id=a.TEMPLATE,cut=str(cut.date()),feature_scope="PDC_KNOWN",scope="STRICT_ORDINARY_ASOF",exit_age_bin=str(age),n=len(v),stocks=v.sid.nunique(),signal_dates=v.signal_day.nunique(),**a.bins(v.ordinary_value)))
  tail=g[g.ordinary_value.gt(9000)]
  dc=tail.signal_day.value_counts()
  concentrations.append(dict(cohort=cohort,template_id=a.TEMPLATE,cut=str(cut.date()),tail_n=len(tail),tail_sids=tail.sid.nunique(),tail_signal_dates=tail.signal_day.nunique(),tail_roots=tail.price_root.nunique(),top5_signal_date_tail_n=int(dc.head(5).sum()),top5_signal_dates=json.dumps({str(k.date()):int(v) for k,v in dc.head(5).items()}),interpretation="DESCRIPTIVE_DEPENDENCE_NOT_IID"))
a.csv("EXTENDED_PDC_MATURE_AGE_AMOUNT_SUPPORT.csv",pd.DataFrame(rows))
a.csv("EXTENDED_PDC_MATURE_TAIL_CONCENTRATION.csv",pd.DataFrame(concentrations))
assert all(a.sha(p)==v for p,v in hashes.items())
a.dump("EXTENDED_TAIL_SUPPORT_QA.json",dict(source_hashes=hashes,sources_unchanged=True,only_mature_labels_used=True,models_fit=0,economic_runs=0))
print(pd.DataFrame(rows).to_csv(index=False));print(pd.DataFrame(concentrations).to_csv(index=False))
