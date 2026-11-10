"""Fixed 22-case forensic original PVR attribution. No trading-policy code."""
from pathlib import Path
import ast, json, hashlib, math, datetime
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent; R=O.parent
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
S=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-current-v3-information-capital-20261101/original_score_function.py")
T=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/code/experiment.py")
F=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-rank-q1-20261027/FORMULA.json")
OLD=R/"common_boundary_translation_preflight_v1"
PV=R/"pvr_persistence_breadth_v1/STOCK_DAILY.parquet"
PRO=O/"case_CASE_PROTOCOL.json"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple,np.ndarray)):return [clean(x) for x in v]
 if isinstance(v,(np.bool_,)):return bool(v)
 if isinstance(v,(np.integer,)):return int(v)
 if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
 if isinstance(v,pd.Timestamp):return v.isoformat()
 return v
def dump(name,v):
 with (O/name).open("x") as f:json.dump(clean(v),f,ensure_ascii=False,indent=2,allow_nan=False);f.write("\n")
def csv(name,df):
 assert not (O/name).exists(),name
 df.to_csv(O/name,index=False,float_format="%.17g")
assert not (O/"case_POINT_FEATURES.csv").exists()
P=json.loads(PRO.read_text());cases=P["cases"]
assert hashlib.sha256(json.dumps(cases,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()==P["case_list_sha256"]
def node(p):return next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=="score")
a=node(S);b=node(T);assert ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False)
ns={"np":np,"pd":pd};exec(compile(ast.Module(body=[a],type_ignores=[]),str(S),"exec"),ns);score=ns["score"]
sources={str(p):sha(p) for p in [M,H,S,T,F,PV,PRO,Path(__file__),OLD/"PROTOCOL.json",OLD/"FIXED_CASES_WITH_CONTEXT.csv",R/"CASE_DATES.csv"]}
cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)["dates"])
mp={x["symbol"]:x for x in json.loads(M.read_text())}
pv=pd.read_parquet(PV,columns=["sid","day","score"],filters=[("sid","in",sorted({x[0] for x in cases}))])
pv["day"]=pd.to_datetime(pv.day);assert not pv.duplicated(["sid","day"]).any();pv=pv.set_index(["sid","day"]).score
weights_raw=.9**np.arange(20,-1,-1);den=float(weights_raw.sum());w=weights_raw/den
def strict_check(q):
 cols=["open","high","low","close"];raw=["raw_"+c for c in cols]
 ok=np.isfinite(q[cols+raw]).all(axis=1)&q[cols+raw].gt(0).all(axis=1)
 ok &=q.high.ge(q[["open","close","low"]].max(axis=1))&q.low.le(q[["open","close","high"]].min(axis=1))
 for c in ["observed_bar","is_observed_bar","price_eligible","volume_eligible"]:ok &=q[c].eq(True)
 for c in ["source_invalid","synthetic_event_bar"]:ok &=q[c].eq(False)
 ok &=np.isfinite(q.raw_volume)&q.raw_volume.gt(0)&np.isfinite(q.amount)&q.amount.gt(0)&q.volume_unit.eq("shares")&q.amount_unit.eq("CNY")
 for c in cols:ok &=(q[c]-q["raw_"+c]*q.adjustment_factor).abs().le(1e-10)
 av=q.amount/q.raw_volume;tol=.5/q.raw_volume+1e-8
 ok &=av.ge(q.raw_low-tol)&av.le(q.raw_high+tol)
 reasons=[];change={}
 if not ok.all():reasons.append("INVALID_OR_MISSING_BAR")
 for c in ["source_kind","source_path","segment_id","adjustment_factor","volume_factor"]:
  if q[c].isna().any() or q[c].nunique(dropna=False)!=1:reasons.append("CHANGE_OR_UNKNOWN_"+c)
  change[c]=[str(v) for v in q[c].drop_duplicates().tolist()]
 return len(reasons)==0,"|".join(reasons),ok,change
points=[];daily=[];raws=[];qas=[];lineages=[]
for sid,gr in pd.DataFrame(cases,columns=["sid","day","case_source"]).groupby("sid",sort=True):
 source=next(k for k in mp[sid]["source_sha256"] if k.endswith("/signal.parquet"));sources[source]=sha(source)
 assert sources[source]==mp[sid]["source_sha256"][source]
 p=pd.read_parquet(source)
 assert p.index.is_unique and p.index.is_monotonic_increasing
 full=score(p)
 for row in gr.itertuples(index=False):
  day=pd.Timestamp(row.day);i=cal.get_loc(day);q=p.reindex(cal[i-84:i+1]).copy()
  assert len(q)==85
  known,reason,ok,changes=strict_check(q)
  pref=score(p.loc[:day]);pd.testing.assert_frame_equal(full.loc[:day],pref,check_exact=True)
  poisoned=p.copy();mask=poisoned.index>day
  poisoned.loc[mask,"close"]*=np.linspace(100.,10000.,mask.sum())
  poisoned.loc[mask,"amount"]*=np.linspace(.001,1000.,mask.sum())
  poison=score(poisoned);pd.testing.assert_frame_equal(full.loc[:day],poison.loc[:day],check_exact=True)
  unit_errors={}
  for label,c,fac in [("price_x100","close",100.),("amount_x10000","amount",10000.)]:
   altered=p.loc[:day].copy();altered[c]*=fac;alt=score(altered)
   unit_errors[label]=float(np.nanmax(np.abs(alt[["u","b","e","E","score"]].to_numpy()-pref[["u","b","e","E","score"]].to_numpy())))
   assert unit_errors[label]<1e-9,unit_errors
  z=full.reindex(q.index).copy();z["amount_ratio"]=q.amount/z.amount_ref;z["abs_r_over_scale"]=np.abs(z.r/z.scale)
  z["price_base"]=z.u;z["amount_add"]=.5*z.u*z.u.abs()*z.b
  z["multiplier"]=1+.5*z.u.abs()*z.b
  z["tanh_abs_compression_ratio"]=z.u.abs()/z.abs_r_over_scale
  z["tanh_abs_compression_ratio"]=z.tanh_abs_compression_ratio.where(z.abs_r_over_scale.ne(0),1.)
  d=z.iloc[-21:].copy()
  assert np.isfinite(d[["u","b","e"]]).all(axis=None)
  assert np.isfinite(d[["E","score"]].iloc[-1]).all()
  d["lag"]=np.arange(20,-1,-1);d["weight_raw"]=weights_raw;d["fixed_denominator"]=den;d["weight"]=w
  d["numerator_total"]=weights_raw*d.e;d["numerator_price"]=weights_raw*d.price_base;d["numerator_amount"]=weights_raw*d.amount_add
  d["weighted_e"]=w*d.e;d["weighted_price"]=w*d.price_base;d["weighted_amount"]=w*d.amount_add
  d["positive_credit"]=d.weighted_e.clip(lower=0);d["negative_debit"]=d.weighted_e.clip(upper=0)
  d["normalized_denominator_contribution"]=w
  assert np.allclose(d.price_base+d.amount_add,d.e,rtol=0,atol=3e-16)
  E=float(full.loc[day,"E"]);sc=float(full.loc[day,"score"]);saved=float(pv.loc[(sid,day)])
  assert abs(sc-saved)<1e-9
  assert abs(d.weighted_e.sum()-E)<1e-15
  qs=score(q);q_error=abs(float(qs.loc[day,"score"])-sc)
  if known:assert q_error<1e-9
  pos=float(d.positive_credit.sum());neg=float(d.negative_debit.sum())
  out=dict(sid=sid,day=row.day,case_source=row.case_source,strict_known=known,strict_reason=reason,original_mechanical_known=True,
   raw_start=str(q.index[0].date()),raw_observations=85,score_original=sc,score_saved=saved,score_error=abs(sc-saved),score_85_common_error=q_error,
   E=E,numerator_total=float(d.numerator_total.sum()),fixed_denominator=den,E_price=float(d.weighted_price.sum()),E_amount=float(d.weighted_amount.sum()),
   positive_credit=pos,negative_debit=neg,positive_days=int(d.e.gt(0).sum()),negative_days=int(d.e.lt(0).sum()),
   amount_boost_up=float(d.loc[d.u.gt(0)&d.b.gt(0),"weighted_amount"].sum()),amount_dampen_down=float(d.loc[d.u.lt(0)&d.b.lt(0),"weighted_amount"].sum()),
   amount_boost_down=float(d.loc[d.u.lt(0)&d.b.gt(0),"weighted_amount"].sum()),amount_dampen_up=float(d.loc[d.u.gt(0)&d.b.lt(0),"weighted_amount"].sum()),
   amount_abs_fraction=float(d.weighted_amount.abs().sum()/d.weighted_e.abs().sum()),
   u_saturated_abs_ge095_n=int(d.u.abs().ge(.95).sum()),u_saturated_abs_ge095_positive_share=float(d.loc[d.u.ge(.95),"positive_credit"].sum()/pos),
   abs_r_over_scale_max=float(d.abs_r_over_scale.max()),score_display_derivative=100*(1-np.tanh(2*E)**2),
   ret_21=float(np.expm1(d.r.sum())),price_only_display=float(50+50*np.tanh(2*d.weighted_price.sum())),
   last_r=float(d.r.iloc[-1]),last_scale=float(d.scale.iloc[-1]),last_u=float(d.u.iloc[-1]),last_b=float(d.b.iloc[-1]),
   last_amount=float(q.amount.iloc[-1]),last_amount_ref=float(d.amount_ref.iloc[-1]),last_amount_ratio=float(d.amount_ratio.iloc[-1]))
  for n in [1,3,5]:
   recent=d.iloc[-n:];older=d.iloc[:-n]
   for tag,g in [(f"last{n}",recent),(f"older{n}",older)]:
    out[tag+"_E"]=float(g.weighted_e.sum());out[tag+"_price"]=float(g.weighted_price.sum());out[tag+"_amount"]=float(g.weighted_amount.sum())
    out[tag+"_positive"]=float(g.positive_credit.sum());out[tag+"_negative"]=float(g.negative_debit.sum())
    out[tag+"_positive_share"]=float(g.positive_credit.sum()/pos);out[tag+"_negative_share"]=float(g.negative_debit.sum()/neg) if neg<0 else np.nan
    out[tag+"_signed_net_fraction"]=float(g.weighted_e.sum()/E) if E else np.nan
   out[f"last{n}_ret"]=float(np.expm1(recent.r.sum()))
   out[f"old_positive_masks_recent{n}_negative"]=bool(older.weighted_e.sum()>0 and recent.weighted_e.sum()<0 and E>0)
  points.append(out)
  for v in [d,z]:v["sid"]=sid;v["signal_day"]=row.day;v["bar_day"]=v.index.strftime("%Y-%m-%d");v["strict_known"]=known;v["strict_reason"]=reason
  daily.append(d.reset_index(drop=True))
  raw=q.copy();raw.columns=["raw_input__"+c for c in raw.columns];raw["raw_row_strict_valid"]=ok
  raws.append(pd.concat([z,raw],axis=1).reset_index(drop=True))
  qas.append(dict(sid=sid,day=row.day,prefix_exact=True,future_close_amount_poison_exact=True,**unit_errors,score_saved_abs_error=abs(sc-saved),common85_score_abs_error=q_error,additive_E_abs_error=abs(d.weighted_e.sum()-E)))
  lineages.append(dict(sid=sid,day=row.day,strict_known=known,reason=reason,values=changes,factor_changes=[dict(day=str(k.date()),factor=float(v)) for k,v in q.adjustment_factor[q.adjustment_factor.ne(q.adjustment_factor.shift())].items()]))
point=pd.DataFrame(points).sort_values(["day","sid"]);dd=pd.concat(daily,ignore_index=True);rr=pd.concat(raws,ignore_index=True)
csv("case_POINT_FEATURES.csv",point);csv("case_DAILY_CONTRIBUTIONS.csv",dd);csv("case_RAW_TRAJECTORIES.csv",rr)
dump("case_FEATURE_SEAL.json",{"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"case_list_sha256":P["case_list_sha256"],"points":sha(O/"case_POINT_FEATURES.csv"),"daily":sha(O/"case_DAILY_CONTRIBUTIONS.csv"),"raw":sha(O/"case_RAW_TRAJECTORIES.csv"),"outcome_joined":False})
dump("case_LINEAGE_AUDIT.json",lineages);dump("case_CAUSAL_QA.json",qas)
# All features have been sealed before joining previously viewed existing economic context.
ctx=pd.read_csv(OLD/"FIXED_CASES_WITH_CONTEXT.csv")
keep=["sid","day","name","receipt","phase","E0","I","G","old_price_net","old_price_status","market_regime","close_size_check","open_size_check","historical_fill"]
point=point.merge(ctx[keep],on=["sid","day"],how="left",validate="one_to_one")
point["name"]=point.name.fillna(point.sid.map({"300666.SZ":"江丰电子"}))
point["context_class"]=np.where(point.old_price_status.eq("COMPLETE_CONDITIONAL_STOCK_ROUND"),np.where(point.old_price_net.lt(0),"EXISTING_COMPLETE_FEE_NET_LOSS","EXISTING_COMPLETE_FEE_NET_PROFIT"),"NO_EXACT_ORIGINAL_PRICE_ROUND")
point.loc[point.close_size_check.eq("Q0_MINIMUM_LOT_OR_RISK_NOFILL"),"context_class"]="Q0_NOT_TRADE_NOT_WINNER"
csv("case_FIXED_CASES_WITH_CONTEXT.csv",point)
# Pure deterministic controls. These are not learned, optimized or economic variants.
syn=[]
for x in [-4.,-1.,-.25,0.,.25,1.,4.]:
 for ratio in [.25,1.,4.]:
  u=float(np.tanh(x));b=float(np.tanh(np.log(ratio)));add=.5*u*abs(u)*b
  syn.append(dict(r_over_s=x,amount_ratio=ratio,u=u,b=b,price_base=u,amount_add=add,e=u+add,multiplier=1+.5*abs(u)*b))
csv("case_SYNTHETIC_DAILY.csv",pd.DataFrame(syn))
synqa={"half_life_observations":math.log(.5)/math.log(.9),"window":21,"denominator":den,"newest_weight":float(w[-1]),"oldest_weight":float(w[0]),"last1_weight":float(w[-1:].sum()),"last3_weight":float(w[-3:].sum()),"last5_weight":float(w[-5:].sum()),"older5_weight":float(w[:-5].sum()),"boundary_formula":"E_next=.9*E+(e_new-.9**21*e_dropped)/D. Dropping negative e raises E even with e_new=0. This is memory arithmetic, not fresh positive evidence."}
synqa["neutral_incoming_expiring_negative_E_increment"]=float(.9**21/den)
synqa["score_range_bound"]=[float(50+50*np.tanh(-3)),float(50+50*np.tanh(3))]
ix=pd.bdate_range("2000-01-03",periods=160);ret=np.tile([.01,-.01],80)
synth=pd.DataFrame({"close":100*np.exp(np.cumsum(ret)),"amount":np.ones(160)*1e8,"segment_id":0},index=ix)
base=score(synth);assert base.e.first_valid_index()==ix[64];assert base.score.first_valid_index()==ix[84]
synqa["first_e_zero_based"]=64;synqa["first_score_zero_based"]=84
for flag in ["price_eligible","observed_bar","is_observed_bar"]:
 broken=synth.copy();broken[flag]=True;broken.loc[ix[90],flag]=False;out=score(broken)
 assert out.loc[ix[90:],"score"].isna().all();synqa[flag+"_invalid_resets"]=True
broken=synth.copy();broken.loc[ix[90]:,"segment_id"]=1;out=score(broken);assert out.loc[ix[90:],"score"].isna().all();synqa["segment_change_resets"]=True
# Pure e-space 22-point boundary identity, independent of price generation.
es=np.linspace(-1,1,22);E0=float(np.dot(w,es[:21]));E1=float(np.dot(w,es[1:]))
assert abs(E1-(.9*E0+(es[-1]-.9**21*es[0])/den))<1e-15
synqa["boundary_identity_abs_error"]=abs(E1-(.9*E0+(es[-1]-.9**21*es[0])/den))
dump("case_SYNTHETIC_QA.json",synqa)
assert all(sha(p)==h for p,h in sources.items());dump("case_SOURCE_HASHES.json",sources)
summary={"case_n":len(point),"stock_n":point.sid.nunique(),"strict_known_n":int(point.strict_known.sum()),"strict_unknown_n":int((~point.strict_known).sum()),"original_mechanical_score_known_n":22,"max_saved_score_error":float(point.score_error.max()),"AST_exact_original_pair":True,"raw_rows":len(rr),"daily_contribution_rows":len(dd),"prefix_exact_n":len(qas),"future_poison_exact_n":len(qas),"max_unit_error":max(max(q["price_x100"],q["amount_x10000"]) for q in qas),"no_new_formula_applied":True,"account_runs":0,"consumer_runs":0,"parameter_searches":0,"context_counts":point.context_class.value_counts().to_dict(),"old_positive_masks_recent1_negative_n":int(point.old_positive_masks_recent1_negative.sum()),"old_positive_masks_recent3_negative_n":int(point.old_positive_masks_recent3_negative.sum()),"old_positive_masks_recent5_negative_n":int(point.old_positive_masks_recent5_negative.sum())}
dump("case_RESULT_SUMMARY.json",summary)
dump("case_OUTPUT_HASHES.json",{p.name:sha(p) for p in O.glob("case_*") if p.is_file() and p.name!="case_OUTPUT_HASHES.json"})
print(json.dumps(clean(summary),ensure_ascii=False,indent=2))
print(point[["sid","day","name","strict_known","score_original","E","E_price","E_amount","positive_credit","negative_debit","last5_E","older5_E","last5_ret","context_class","old_price_net"]].to_string(index=False))
