"""Combine saved per-cohort support after both new windows are complete; no economics/fitting."""
from pathlib import Path
import ast,hashlib,json,sys
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O))
import EXTENDED_SUPPORT_AUDIT as a
R=a.R;E=a.E;CUTS=a.CUTS;CAL=a.CAL
xs=[];hashes={}
for cohort in ["2023","2024JanAug"]:
 x,h=a.load_new(cohort);hashes.update(h)
 p=O/("EXTENDED_"+cohort+"_PDC_FEATURES.parquet")
 assert p.exists(),("PDC_NOT_READY",str(p))
 f=pd.read_parquet(p);hashes[str(p)]=a.sha(p)
 x=x.merge(f[["round_id","P","D","C","root_known","feature_known","pvr_error"]],on="round_id",how="left",validate="one_to_one")
 assert x.feature_known.notna().all()
 xs.append(x)
oldpath=R/"closed_price_supervised_pilot_support_v1/ALL_ORIGINAL_PRICE_ROWS.parquet"
old=pd.read_parquet(oldpath);hashes[str(oldpath)]=a.sha(oldpath)
for w,cohort,template in [("2022","old2022","LEGACY_2022_DIFFERENT_RESPONSIBILITY_GUARD"),("2024","old2024SepDec",a.TEMPLATE)]:
 x=old[old.window_label.eq(w)].copy()
 x["cohort_id"]=cohort;x["template_id"]=template
 for c in ["signal_day","entry_day","exit_day","status_day"]:x[c]=pd.to_datetime(x[c],errors="coerce")
 x["ordinary_known_at"]=x.label_known_at_proxy;x["ordinary_value"]=x.net_pnl.where(x.ordinary)
 x["scenario_known_at"]=pd.NaT;x["scenario_value"]=np.nan;x["scenario_label_available"]=False
 x["financial_clock_note"]="OLD_PILOT_NONORDINARY_NOT_RECONSTRUCTED_OR_CERTIFIED"
 x["decision_dedup_key"]=[json.dumps([sid,str(day.date()),template]) for sid,day in zip(x.sid,x.signal_day)]
 x["t"]=CAL.get_indexer(x.signal_day)
 xs.append(x)
r=pd.concat(xs,ignore_index=True,sort=False)
r["normalized_decision_key"]=[json.dumps([sid,str(day.date()),template],separators=(",",":")) for sid,day,template in zip(r.sid,r.signal_day,r.template_id)]
def rootnorm(v):
 if pd.isna(v):return None
 try:q=ast.literal_eval(str(v))
 except (ValueError,SyntaxError):q=str(v)
 return json.dumps(q,ensure_ascii=False,separators=(",",":"))
r["root_cluster"]=r.price_root.map(rootnorm)
dup=r[r.duplicated("normalized_decision_key",keep=False)].copy()
a.csv("EXTENDED_DECISION_DUPLICATE_AUDIT.csv",dup[["cohort_id","template_id","round_id","sid","signal_day","normalized_decision_key"]])
assert not len(dup),"DUPLICATE_DECISIONS_REQUIRE_RECONCILIATION_BEFORE_COMBINING"
identity=r[["cohort_id","template_id","round_id","sid","signal_day","normalized_decision_key","root_cluster"]].copy()
a.parquet("EXTENDED_ALL_COHORT_IDENTITIES.parquet",identity)
overlap=[]
for i,left in enumerate(xs):
 for right in xs[i+1:]:
  l=identity[identity.cohort_id.eq(left.cohort_id.iloc[0])];q=identity[identity.cohort_id.eq(right.cohort_id.iloc[0])]
  overlap.append(dict(left_cohort=left.cohort_id.iloc[0],right_cohort=right.cohort_id.iloc[0],same_template=left.template_id.iloc[0]==right.template_id.iloc[0],shared_sids=len(set(l.sid)&set(q.sid)),shared_nonnull_roots=len(set(l.root_cluster.dropna())&set(q.root_cluster.dropna())),shared_decisions=len(set(l.normalized_decision_key)&set(q.normalized_decision_key)),interpretation="DEPENDENCE_NOT_IID_OR_CONTINUOUS_ACCOUNT"))
a.csv("EXTENDED_CROSS_COHORT_DEPENDENCE.csv",pd.DataFrame(overlap))
all_support=[];all_late=[];all_states=[]
for cohort,g in r.groupby("cohort_id",sort=False):
 for fs in ["ALL_LABELS","PDC_KNOWN"]:
  s,l,st,_=a.support(g,fs)
  if cohort in ["old2022","old2024SepDec"]:s=s[s.label_scope.eq("STRICT_ORDINARY")]
  all_support.append(s);all_late.append(l)
  if fs=="ALL_LABELS":all_states.append(st)
a.csv("EXTENDED_PER_COHORT_MATURE_SUPPORT.csv",pd.concat(all_support,ignore_index=True))
a.csv("EXTENDED_PER_COHORT_LATE_DIAGNOSTIC_ONLY.csv",pd.concat(all_late,ignore_index=True))
a.csv("EXTENDED_PER_COHORT_ASOF_STATES.csv",pd.concat(all_states,ignore_index=True))
template_support=[]
for template,g in r.groupby("template_id",sort=False):
 for cut in CUTS:
  t=CAL.get_loc(cut);p=g[g.t.ge(t-504)&g.t.lt(t)];known=p.ordinary&p.ordinary_known_at.lt(cut)
  for fs in ["ALL_LABELS","PDC_KNOWN"]:
   mask=known if fs=="ALL_LABELS" else known&p.feature_known
   x=p[mask];tail=x[x.ordinary_value.gt(9000)]
   template_support.append(dict(template_id=template,cut=str(cut.date()),feature_scope=fs,scope="STRICT_ORDINARY_DEDUP_COUNTERFACTUAL_COHORT_UNION_NOT_ACCOUNT",n=len(x),W=int(x.ordinary_value.gt(0).sum()),stocks=x.sid.nunique(),signal_dates=x.signal_day.nunique(),root_clusters=x.root_cluster.nunique(),right_tail_stocks=tail.sid.nunique(),right_tail_dates=tail.signal_day.nunique(),right_tail_roots=tail.root_cluster.nunique(),**a.bins(x.ordinary_value),cohort_counts=json.dumps(x.cohort_id.value_counts().to_dict()),tail_cohort_counts=json.dumps(tail.cohort_id.value_counts().to_dict())))
a.csv("EXTENDED_TEMPLATE_STRATIFIED_SUPPORT.csv",pd.DataFrame(template_support))
assert all(a.sha(p)==h for p,h in hashes.items())
a.dump("EXTENDED_COMBINED_QA.json",dict(status="MATURE_PROXY_SUPPORT_ONLY_NO_MODEL",source_hashes=hashes,rows=len(r),cohorts=r.cohort_id.value_counts().to_dict(),templates=r.template_id.value_counts().to_dict(),duplicate_decisions=len(dup),sources_unchanged=True,no_2022_backfill=True,no_unmarked_2022_pooling=True,independent_flat_cohorts_not_continuous_account=True,old_nonordinary_clocks_not_claimed=True,models_fit=0,economic_runs=0))
print(pd.DataFrame(template_support).to_csv(index=False))
print(pd.DataFrame(overlap).to_csv(index=False))
