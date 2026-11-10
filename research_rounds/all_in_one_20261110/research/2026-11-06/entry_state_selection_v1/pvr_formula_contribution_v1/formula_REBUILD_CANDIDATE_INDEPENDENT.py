import pandas as pd,numpy as np,json,hashlib,pathlib
P=pathlib.Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/pvr_formula_contribution_v1")
raw=pd.read_csv(P/"candidate_RAW_TRAJECTORIES.csv",float_precision="round_trip")
daily=pd.read_csv(P/"candidate_DAILY_CONTRIBUTIONS.csv",float_precision="round_trip")
points=pd.read_csv(P/"candidate_FIXED_CASES_WITH_CONTEXT.csv",float_precision="round_trip")
old=pd.read_csv(P/"case_FIXED_CASES_WITH_CONTEXT.csv",float_precision="round_trip")
pr=json.loads((P/"candidate_PROTOCOL.json").read_text())
manifest=json.loads(pathlib.Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json").read_text())
sources=json.loads((P/"candidate_SOURCE_FREEZE.json").read_text())
hashbad=[p for p,h in sources.items() if hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()!=h]
outs=json.loads((P/"candidate_OUTPUT_HASHES.json").read_text())
outbad=[p for p,h in outs.items() if hashlib.sha256((P/p).read_bytes()).hexdigest()!=h]
assert not hashbad and not outbad
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
assert sha(P/"candidate_score_function.py")==pr["candidate_source_sha256"]
assert hashlib.sha256(json.dumps(pr["cases"],ensure_ascii=False,separators=(",",":")).encode()).hexdigest()==pr["case_list_sha256"]
expected=set(tuple(x[:2]) for x in pr["cases"])
assert set(zip(points.sid,points.day))==expected==set(zip(old.sid,old.day))
keys=["sid","day"];shared=["strict_known","strict_reason","old_price_net","old_price_status","historical_fill","context_class","receipt","phase","case_source"]
ctx=points[keys+shared].merge(old[keys+shared],on=keys,suffixes=("_n","_o"),validate="one_to_one")
for c in shared:
 assert ctx[c+"_n"].fillna("__NA__").equals(ctx[c+"_o"].fillna("__NA__")),c
wraw=np.power(.9,np.arange(20,-1,-1));D=wraw.sum();w=wraw/D
errs={};rows=[]
def err(name,a,b):
 a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
 assert a.shape==b.shape,(name,a.shape,b.shape)
 assert np.array_equal(np.isnan(a),np.isnan(b)),("null mismatch",name)
 e=float(np.nanmax(np.abs(a-b))) if np.isfinite(a-b).any() else 0.
 errs[name]=max(errs.get(name,0.),e)
 assert e<1e-9,(name,e)
for (sid,day),r in raw.groupby(["sid","signal_day"],sort=True):
 r=r.sort_values("bar_day");g=daily[(daily.sid==sid)&(daily.signal_day==day)].sort_values("bar_day")
 assert len(r)==85 and len(g)==21
 assert g.bar_day.tolist()==r.bar_day.iloc[-21:].tolist()
 q=r.r.to_numpy()/r.scale.to_numpy()
 d=np.log(r.close.to_numpy()/r.open.to_numpy())
 bv=np.tanh(np.log(r.amount.to_numpy()/r.amount_ref.to_numpy()))
 v=np.tanh(d/r.scale.to_numpy())
 u=np.tanh(q);eo=u*(1+.5*np.abs(u)*bv)
 en=np.tanh(q+.5*bv*v);el=np.tanh(q+.5*bv*np.tanh(q))
 err("b_from_A",bv,r.b);err("d_from_OC",d,r.d);err("e_original_from_r_s_b",eo,r.e);err("e_new_from_r_s_A_OC",en,r.e_new);err("e_link_independent",el,r.e_link)
 err("r=n+d",r.r,r.n+d)
 sub=points[(points.sid==sid)&(points.day==day)].iloc[0]
 Eold=w@eo[-21:];Enew=w@en[-21:];Ecomp=w@(el[-21:]-eo[-21:]);Ebody=w@(en[-21:]-el[-21:])
 for name,a,b in [("Eold",Eold,sub.E_old),("Enew",Enew,sub.E_new),("score_new",50+50*np.tanh(2*Enew),sub.new_score),("compression_bridge",Ecomp,sub.E_compression_delta),("body_bridge",Ebody,sub.E_body_delta),("bridge_identity",Enew-Eold,Ecomp+Ebody),("weights",w,g.weight),("weighted_new",w*en[-21:],g.weighted_new),("weighted_compression",w*(el[-21:]-eo[-21:]),g.weighted_compression_delta),("weighted_body",w*(en[-21:]-el[-21:]),g.weighted_body_delta)]:
  err(name,np.atleast_1d(a),np.atleast_1d(b))
 assert np.all(np.abs(en[np.isfinite(en)])<=1) and np.all(np.sign(en[np.abs(q)>=.5])==np.sign(q[np.abs(q)>=.5]))
 for lag in [1,3,5]:
  err("recent_E",np.atleast_1d(np.dot(w[-lag:],en[-lag:])),np.atleast_1d(sub["last%d_new_E"%lag]))
 rows.append({"sid":sid,"day":day,"name":sub["name"],"known":bool(sub.strict_known),"Ecomp":Ecomp,"Ebody":Ebody,"Edelta":Enew-Eold,"score_delta":float(sub.score_delta),"context":sub.context_class})
out=pd.DataFrame(rows)
def agg(f):
 c=f.Ecomp.abs();b=f.Ebody.abs()
 return {"n":len(f),"comp_abs_gt_body":int((c>b).sum()),"body_abs_gt_comp":int((b>c).sum()),"negative_compression_n":int(f.Ecomp.lt(0).sum()),"positive_body_n":int(f.Ebody.gt(0).sum()),"negative_body_n":int(f.Ebody.lt(0).sum()),"sum_abs_comp":float(c.sum()),"sum_abs_body":float(b.sum()),"sum_abs_comp_fraction":float(c.sum()/(c.sum()+b.sum())),"rises":int(f.score_delta.gt(0).sum()),"falls":int(f.score_delta.lt(0).sum())}
result={"sources_verified_n":len(sources),"outputs_verified_n":len(outs),"hash_mismatches":[],"raw_rows":len(raw),"daily_rows":len(daily),"case_count":len(points),"strict_known":int(points.strict_known.sum()),"strict_unknown":int((~points.strict_known).sum()),"all_original_context_columns_equal":True,"reconstruction_max_errors":errs,"all22":agg(out),"strict18":agg(out[out.known]),"contexts":points.context_class.value_counts().to_dict(),"unknown_rows":out[~out.known].to_dict("records"),"all_case_bridge":out.to_dict("records")}
print(json.dumps(result,ensure_ascii=False,indent=2))


import numpy as np,pandas as pd,pathlib,json
P=pathlib.Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/pvr_formula_contribution_v1")
raw=pd.read_csv(P/"candidate_RAW_TRAJECTORIES.csv",float_precision="round_trip"); daily=pd.read_csv(P/"candidate_DAILY_CONTRIBUTIONS.csv",float_precision="round_trip"); points=pd.read_csv(P/"candidate_FIXED_CASES_WITH_CONTEXT.csv",float_precision="round_trip")
M=json.loads(pathlib.Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json").read_text()); mp={r["symbol"]:r for r in M}
w=.9**np.arange(20,-1,-1);w/=w.sum()
def reconstruct(f):
 # Fresh implementation. Do not execute either the original or candidate source.
 valid=np.isfinite(f.close)&f.close.gt(0)&np.isfinite(f.amount)&f.amount.gt(0)
 for c in ["price_eligible","observed_bar","is_observed_bar"]:
  if c in f:valid &= f[c].fillna(False).astype(bool)
 for c in ["source_invalid","synthetic_event_bar"]:
  if c in f:valid &= ~f[c].fillna(True).astype(bool)
 seg=f.segment_id if "segment_id" in f else pd.Series(0,index=f.index)
 blocks=((~valid)|(~valid.shift(fill_value=False))|seg.ne(seg.shift())).cumsum()
 z=pd.DataFrame(np.nan,index=f.index,columns=["r","scale","amount_ref","u","b","e","e_new","e_link","E","E_new","score","score_new","d","n"])
 for _,g in f[valid].groupby(blocks[valid],sort=False):
  ret=np.log(g.close).diff()
  s=ret.abs().shift(1).rolling(63,min_periods=63).median()*1.4826;s=s.clip(lower=1e-8)
  ar=g.amount.shift(1).rolling(21,min_periods=21).median()
  q=ret/s;u=np.tanh(q);b=np.tanh(np.log(g.amount/ar))
  d=np.log(g.close/g.open).where(g.open.gt(0)&np.isfinite(g.open))
  n=np.log(g.open/g.close.shift(1)).where(g.open.gt(0)&np.isfinite(g.open))
  e=u*(1+.5*u.abs()*b); en=np.tanh(q+.5*b*np.tanh(d/s));link=np.tanh(q+.5*b*np.tanh(q))
  E=e.rolling(21,min_periods=21).apply(lambda x:sum(x*w),raw=True)
  En=en.rolling(21,min_periods=21).apply(lambda x:sum(x*w),raw=True)
  vals=[ret,s,ar,u,b,e,en,link,E,En,50+50*np.tanh(2*E),50+50*np.tanh(2*En),d,n]
  z.loc[g.index,:]=np.column_stack(vals)
 return z
maxerr={};results=[];tests={"physical_prefix_exact":0,"future_poison_exact":0,"unit_price":0.,"unit_amount":0.,"mirror":0.,"power":0.,"C_monotonic_min_delta":1e99}
cache={}
for (sid,day),g in raw.groupby(["sid","signal_day"],sort=True):
 g=g.sort_values("bar_day"); dates=pd.DatetimeIndex(g.bar_day)
 if sid not in cache:
  path=next(p for p in mp[sid]["source_sha256"] if p.endswith("/signal.parquet"));cache[sid]=pd.read_parquet(path)
 full=cache[sid]; f=full.reindex(dates)
 assert np.array_equal(f[["open","close","amount"]].to_numpy(),g[["open","close","amount"]].to_numpy())
 zz=reconstruct(f);tail=zz.iloc[-21:]
 for col in ["r","scale","amount_ref","u","b","e","e_new","e_link"]:
  a=tail[col].to_numpy();b=g[col].to_numpy()[-21:];err=float(np.nanmax(np.abs(a-b)));maxerr[col]=max(maxerr.get(col,0.),err);assert err<1e-12,(sid,day,col,err)
 ss=float(zz.score_new.iloc[-1]);point=points[(points.sid==sid)&(points.day==day)].iloc[0]
 assert abs(ss-point.new_score)<1e-12
 maxerr["final_score"]=max(maxerr.get("final_score",0.),abs(ss-point.new_score))
 # Inputs outside the 85 physical rows cannot affect this formula's final score.
 pref=reconstruct(full.loc[:pd.Timestamp(day)]);at=reconstruct(full).loc[pd.Timestamp(day)]
 assert np.array_equal(pref.iloc[-1].to_numpy(),at.to_numpy(),equal_nan=True);tests["physical_prefix_exact"]+=1
 po=full.copy();future=po.index>pd.Timestamp(day)
 po.loc[future,"close"]*=100.;po.loc[future,"open"]*=.01;po.loc[future,"amount"]*=173.
 px=reconstruct(po).loc[pd.Timestamp(day)]
 assert np.array_equal(px.to_numpy(),at.to_numpy(),equal_nan=True);tests["future_poison_exact"]+=1
 for tag,k,a,amount in [("unit_price",73.,1.,1.),("unit_amount",1.,1.,19.),("mirror",10000.,-1.,1.),("power",73.,3.,1.)]:
  h=f.copy();h["close"]=k*h.close**a;h["open"]=k*h.open**a;h["amount"]*=amount
  val=float(reconstruct(h).score_new.iloc[-1]);target=100-ss if tag=="mirror" else ss;tests[tag]=max(tests[tag],abs(val-target));assert abs(val-target)<1e-8
 # Current C moves with past, O and A held fixed. No score-selection or alternate formula.
 scores=[]
 for delta in [-1e-4,0.,1e-4]:
  h=f.copy();h.loc[h.index[-1],"close"]*=np.exp(delta);scores.append(float(reconstruct(h).score_new.iloc[-1]))
 tests["C_monotonic_min_delta"]=min(tests["C_monotonic_min_delta"],min(np.diff(scores)))
 assert min(np.diff(scores))>=0
 results.append({"sid":sid,"day":day,"source_OCA_exact":True,"reconstructed_score":ss})
# Missing O does not alter price/amount preparation; only new output fails for its 21-row membership.
sample=cache["600100.SH"].loc[:"2022-01-04"].copy();base=reconstruct(sample)
h=sample.copy();h.loc[h.index[-1],"open"]=np.nan;bad=reconstruct(h)
assert np.array_equal(base[["r","scale","amount_ref","b","e","score"]].to_numpy(),bad[["r","scale","amount_ref","b","e","score"]].to_numpy(),equal_nan=True)
assert np.isnan(bad.score_new.iloc[-1])
for c,v in [("amount",0.),("segment_id",999)]:
 h=sample.copy();h.loc[h.index[-1],c]=v;bad=reconstruct(h);assert np.isnan(bad.score_new.iloc[-1])
tests["missing_open_old_clock_unchanged"]=True;tests["missing_open_new_unknown"]=True;tests["invalid_amount_reset_unknown"]=True;tests["new_segment_reset_unknown"]=True
print(json.dumps({"raw_source_exact_n":len(results),"raw_reconstruction_max_errors":maxerr,"independent_invariants":tests},indent=2))
for sid,day in [("600100.SH","2022-01-04"),("688248.SH","2022-05-12"),("002583.SZ","2024-09-25"),("300666.SZ","2026-01-05")]:
 g=daily[(daily.sid==sid)&(daily.signal_day==day)].copy();g["delta_E"]=g.weighted_new-g.weighted_old
 union=pd.concat([g.loc[g.delta_E.abs().nlargest(3).index],g.sort_values("bar_day").tail(3)]).drop_duplicates(["bar_day"]).sort_values("bar_day")
 print("\nKEY_DAILY",sid,day);print(union[["bar_day","n","d","b","e","e_new","weight","delta_E","weighted_compression_delta","weighted_body_delta"]].to_string(index=False,float_format=lambda v:"%.9f"%v))
