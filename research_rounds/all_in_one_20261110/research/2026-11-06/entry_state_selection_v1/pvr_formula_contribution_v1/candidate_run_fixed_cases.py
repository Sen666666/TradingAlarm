"""One pre-frozen candidate, all22 cases, deterministic QA; no economic engine."""
from pathlib import Path
import ast, importlib.util, json, hashlib, math
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
S=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-current-v3-information-capital-20261101/original_score_function.py")
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
P=json.loads((O/"candidate_PROTOCOL.json").read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple,np.ndarray)):return [clean(x) for x in v]
 if isinstance(v,(np.bool_,)):return bool(v)
 if isinstance(v,(np.integer,)):return int(v)
 if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
 return v
def dump(n,v):
 with (O/n).open("x") as f:json.dump(clean(v),f,ensure_ascii=False,indent=2,allow_nan=False);f.write("\n")
def csv(n,v):
 assert not (O/n).exists()
 v.to_csv(O/n,index=False,float_format="%.17g")
assert sha(O/"candidate_score_function.py")==P["candidate_source_sha256"]
assert sha(S)==P["original_source_sha256"]
assert hashlib.sha256(json.dumps(P["cases"],ensure_ascii=False,separators=(",",":")).encode()).hexdigest()==P["case_list_sha256"]
ns={"np":np,"pd":pd};fn=next(x for x in ast.parse(S.read_text()).body if isinstance(x,ast.FunctionDef) and x.name=="score")
exec(compile(ast.Module(body=[fn],type_ignores=[]),str(S),"exec"),ns);old=ns["score"]
spec=importlib.util.spec_from_file_location("frozen_candidate",O/"candidate_score_function.py");mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);calc=lambda f:mod.candidate_score(f,old)
mp={x["symbol"]:x for x in json.loads(M.read_text())}
point0=pd.read_csv(O/"case_POINT_FEATURES.csv");raw0=pd.read_csv(O/"case_RAW_TRAJECTORIES.csv")
sources={str(x):sha(x) for x in [S,M,Path(__file__),O/"candidate_score_function.py",O/"candidate_PROTOCOL.json",O/"case_POINT_FEATURES.csv",O/"case_RAW_TRAJECTORIES.csv",O/"case_FIXED_CASES_WITH_CONTEXT.csv"]}
paths={s:next(k for k in mp[s]["source_sha256"] if k.endswith("/signal.parquet")) for s,_,_ in P["cases"]}
for s,path in paths.items():sources[path]=sha(path);assert sources[path]==mp[s]["source_sha256"][path]
dump("candidate_SOURCE_FREEZE.json",sources)
wraw=.9**np.arange(20,-1,-1);D=float(wraw.sum());w=wraw/D
daily=[];raw=[];points=[];qas=[]
for sid,rows in pd.DataFrame(P["cases"],columns=["sid","day","case_source"]).groupby("sid",sort=True):
 p=pd.read_parquet(paths[sid]);f=calc(p)
 for a in rows.itertuples(index=False):
  day=pd.Timestamp(a.day);base=point0[(point0.sid==sid)&(point0.day==a.day)].iloc[0]
  dates=pd.DatetimeIndex(pd.to_datetime(raw0[(raw0.sid==sid)&(raw0.signal_day==a.day)].bar_day))
  q=p.reindex(dates);z=f.reindex(dates).copy()
  assert np.isfinite(q.open).all() and q.open.gt(0).all()
  identity_error=float(np.nanmax(np.abs(z.r-z.n-z.d)));assert identity_error<1e-12
  pref=calc(p.loc[:day]);pd.testing.assert_frame_equal(f.loc[:day],pref,check_exact=True)
  poison=p.copy();future=poison.index>day
  for c,mul in [("close",np.linspace(.001,1000,future.sum())),("open",np.linspace(200,2000,future.sum())),("amount",np.linspace(1e-4,1e4,future.sum()))]:poison.loc[future,c]*=mul
  fp=calc(poison);pd.testing.assert_frame_equal(f.loc[:day],fp.loc[:day],check_exact=True)
  errs={}
  for name,cols,mul in [("price_C_O_x100",["close","open"],100.),("amount_x10000",["amount"],10000.)]:
   h=p.loc[:day].copy();h[cols]*=mul;hh=calc(h)
   colscheck=["n","d","q","v","e_new","E_new","score_new"]
   errs[name]=float(np.nanmax(np.abs(hh[colscheck].to_numpy()-pref[colscheck].to_numpy())))
   assert errs[name]<1e-8
  mirror=p.loc[:day].copy()
  mirror["close"]=10000/mirror.close;mirror["open"]=10000/mirror.open
  mm=calc(mirror);errs["mirror_score_error"]=float(np.nanmax(np.abs(mm.score_new+pref.score_new-100)))
  assert errs["mirror_score_error"]<1e-8
  zz=z.iloc[-21:].copy();assert np.isfinite(zz[["e","e_new","e_link","u"]]).all(axis=None)
  assert (zz.e_new.abs()<1).all()
  zz["lag"]=np.arange(20,-1,-1);zz["weight_raw"]=wraw;zz["fixed_denominator"]=D;zz["weight"]=w
  zz["weighted_old"]=w*zz.e;zz["weighted_new"]=w*zz.e_new;zz["weighted_price"]=w*zz.u
  zz["weighted_new_amount"]=w*zz.amount_new_minus_price
  zz["weighted_compression_delta"]=w*zz.compression_bridge_delta;zz["weighted_body_delta"]=w*zz.body_information_delta
  zz["new_numerator"]=wraw*zz.e_new
  Eold=float(zz.weighted_old.sum());Enew=float(zz.weighted_new.sum())
  assert abs(Eold-base.E)<1e-12 and abs(float(f.loc[day,"score"])-base.score_original)<1e-10
  bridge_error=abs(Enew-Eold-zz.weighted_compression_delta.sum()-zz.weighted_body_delta.sum());assert bridge_error<1e-15
  row=dict(sid=sid,day=a.day,case_source=a.case_source,strict_known=bool(base.strict_known),strict_reason=base.strict_reason,
   same_source_open_all85_positive=True,original_mechanical_known=True,original_score=base.score_original,new_score=float(f.loc[day,"score_new"]),score_delta=float(f.loc[day,"score_new"]-base.score_original),
   E_old=Eold,E_new=Enew,E_delta=Enew-Eold,E_price=float(zz.weighted_price.sum()),E_old_amount=float((zz.weighted_old-zz.weighted_price).sum()),E_new_amount=float(zz.weighted_new_amount.sum()),
   E_compression_delta=float(zz.weighted_compression_delta.sum()),E_body_delta=float(zz.weighted_body_delta.sum()),bridge_abs_error=bridge_error,
   original_numerator=float((wraw*zz.e).sum()),new_numerator=float(zz.new_numerator.sum()),fixed_denominator=D,
   old_positive=float(zz.weighted_old.clip(lower=0).sum()),old_negative=float(zz.weighted_old.clip(upper=0).sum()),new_positive=float(zz.weighted_new.clip(lower=0).sum()),new_negative=float(zz.weighted_new.clip(upper=0).sum()),
   last_n=float(zz.n.iloc[-1]),last_d=float(zz.d.iloc[-1]),last_q=float(zz.q.iloc[-1]),last_v=float(zz.v.iloc[-1]),last_b=float(zz.b.iloc[-1]),last_old_e=float(zz.e.iloc[-1]),last_new_e=float(zz.e_new.iloc[-1]),return_identity_max_abs_error=identity_error)
  for n in [1,3,5]:
   for tag,h in [(f"last{n}",zz.iloc[-n:]),(f"older{n}",zz.iloc[:-n])]:
    for label,c in [("old","weighted_old"),("new","weighted_new")]:
     row[f"{tag}_{label}_E"]=float(h[c].sum())
     row[f"{tag}_{label}_positive_share"]=float(h[c].clip(lower=0).sum()/zz[c].clip(lower=0).sum())
     denneg=zz[c].clip(upper=0).sum()
     row[f"{tag}_{label}_negative_share"]=float(h[c].clip(upper=0).sum()/denneg) if denneg else np.nan
    row[f"{tag}_compression_delta"]=float(h.weighted_compression_delta.sum());row[f"{tag}_body_delta"]=float(h.weighted_body_delta.sum())
  points.append(row)
  for frame in [z,zz]:frame["sid"]=sid;frame["signal_day"]=a.day;frame["bar_day"]=frame.index.strftime("%Y-%m-%d");frame["strict_known"]=bool(base.strict_known);frame["strict_reason"]=base.strict_reason
  zz["open"]=q.open.iloc[-21:].to_numpy();zz["close"]=q.close.iloc[-21:].to_numpy();zz["amount"]=q.amount.iloc[-21:].to_numpy()
  z["open"]=q.open;z["close"]=q.close;z["amount"]=q.amount
  raw.append(z.reset_index(drop=True));daily.append(zz.reset_index(drop=True))
  qas.append(dict(sid=sid,day=a.day,prefix_exact=True,future_C_O_A_poison_exact=True,r_n_plus_d_max_error=identity_error,**errs))
df=pd.DataFrame(points).sort_values(["day","sid"]);ds=pd.concat(daily,ignore_index=True);rs=pd.concat(raw,ignore_index=True)
csv("candidate_POINT_FEATURES.csv",df);csv("candidate_DAILY_CONTRIBUTIONS.csv",ds);csv("candidate_RAW_TRAJECTORIES.csv",rs)
dump("candidate_FEATURE_SEAL.json",{x:sha(O/x) for x in ["candidate_POINT_FEATURES.csv","candidate_DAILY_CONTRIBUTIONS.csv","candidate_RAW_TRAJECTORIES.csv"]})
# Existing labels only after sealed features. No new outcome computation.
ctx=pd.read_csv(O/"case_FIXED_CASES_WITH_CONTEXT.csv")
keep=["sid","day","name","receipt","phase","old_price_net","old_price_status","market_regime","close_size_check","open_size_check","historical_fill","context_class"]
df=df.merge(ctx[keep],on=["sid","day"],how="left",validate="one_to_one")
csv("candidate_FIXED_CASES_WITH_CONTEXT.csv",df);dump("candidate_CAUSAL_QA.json",qas)
# Fixed mathematical input controls, never formula-parameter search or case fitting.
ix=pd.bdate_range("2000-01-03",periods=180);ret=np.tile([.01,-.01],90)
toy=pd.DataFrame({"close":100*np.exp(np.cumsum(ret)),"amount":np.full(180,1e8),"segment_id":0},index=ix)
toy["open"]=toy.close.shift().fillna(toy.close.iloc[0]);toy["high"]=toy.close*1.1;toy["low"]=toy.close*.9
flat=calc(toy);known=flat.e.notna();b0error=float(np.max(np.abs(flat.e_new[known]-flat.u[known])));assert b0error==0
qa={"b_zero_exact_u":b0error==0,"new_kernel_bound":[-1,1],"new_score_open_bounds":[float(50+50*np.tanh(-2)),float(50+50*np.tanh(2))],"same_C_A_H_L_diff_O":{}}
test=toy.copy();test.loc[ix[-1],"amount"]=4e8
lo=test.copy();hi=test.copy();lo.loc[ix[-1],"open"]=test.close.iloc[-1]*.98;hi.loc[ix[-1],"open"]=test.close.iloc[-1]*1.02
a=calc(lo);b=calc(hi);assert a.score.iloc[-1]==b.score.iloc[-1] and a.score_new.iloc[-1]!=b.score_new.iloc[-1]
qa["same_C_A_H_L_diff_O"]={"old_equal":True,"old_score":float(a.score.iloc[-1]),"new_low_open":float(a.score_new.iloc[-1]),"new_high_open":float(b.score_new.iloc[-1]),"HL_close_input_methods_same_inputs_not_claiming_DMI_numeric_recheck":True}
nongap=calc(test);assert abs(nongap.e_new.iloc[-1]-nongap.e.iloc[-1])>1e-5
qa["no_gap_does_not_equal_old"]={"n":float(nongap.n.iloc[-1]),"old_e":float(nongap.e.iloc[-1]),"new_e":float(nongap.e_new.iloc[-1])}
gap=test.copy();gap.loc[ix[-1],"open"]=gap.close.iloc[-1];gg=calc(gap);assert gg.e_new.iloc[-1]==gg.u.iloc[-1]
qa["O_equals_C_body_zero_exact_price_only"]=True
for tag,column,value in [("zero_amount","amount",0.),("missing_O","open",np.nan),("new_segment","segment_id",1)]:
 h=test.copy();h.loc[ix[-1],column]=value;hh=calc(h);assert pd.isna(hh.score_new.iloc[-1]);qa[tag+"_unknown"]=True
mon=[]
for ratio in [.25,1.,4.]:
 for opening in [.97,1.,1.03]:
  values=[]
  for shock in [-5.,-1.,-.5,0.,.5,1.,5.]:
   h=toy.copy();s=float(flat.scale.iloc[-1]);h.loc[ix[-1],"amount"]=1e8*ratio;h.loc[ix[-1],"open"]=toy.close.iloc[-2]*opening;h.loc[ix[-1],"close"]=toy.close.iloc[-2]*np.exp(shock*s)
   hh=calc(h);values.append(float(hh.score_new.iloc[-1]))
  assert np.all(np.diff(values)>0)
  mon.append(dict(amount_ratio=ratio,open_over_prevC=opening,min_successive_score_delta=float(np.diff(values).min())))
qa["current_C_monotone_controls"]=mon
epsilon=1e-6;bv=float(np.tanh(np.log(4.)));u=float(np.tanh(epsilon))
qa["small_q_no_gap_first_order"]={"q":epsilon,"b":bv,"new_e_over_q":float(np.tanh(epsilon+.5*bv*u)/epsilon),"old_e_over_q":float((u+.5*u*abs(u)*bv)/epsilon),"new_limit":1+.5*bv,"old_limit":1.}
syn=[]
for qv in [-2.,-.2,0.,.2,2.]:
 for dv in [-1.,0.,1.]:
  for bv in [-.8,0.,.8]:
   uv=float(np.tanh(qv));vv=float(np.tanh(dv));en=float(np.tanh(qv+.5*bv*vv));eo=uv*(1+.5*abs(uv)*bv)
   if abs(qv)>.5:assert np.sign(en)==np.sign(qv)
   derivative=(1-en*en)*(1+.5*bv*(1-vv*vv))
   assert derivative>0
   syn.append(dict(q=qv,d_over_s=dv,b=bv,old_e=eo,new_e=en,scaled_current_C_log_derivative=derivative))
csv("candidate_SYNTHETIC_KERNEL.csv",pd.DataFrame(syn));dump("candidate_SYNTHETIC_QA.json",qa)
assert all(sha(k)==v for k,v in sources.items())
summary={"cases":22,"stocks":19,"strict_known":18,"strict_unknown":4,"mechanically_computed":22,"prefix_exact_n":22,"future_C_O_A_poison_exact_n":22,"max_return_decomposition_error":max(q["r_n_plus_d_max_error"] for q in qas),"max_unit_error":max(max(q["price_C_O_x100"],q["amount_x10000"]) for q in qas),"max_mirror_error":max(q["mirror_score_error"] for q in qas),"max_bridge_error":float(df.bridge_abs_error.max()),"score_rises_n":int(df.score_delta.gt(0).sum()),"score_falls_n":int(df.score_delta.lt(0).sum()),"no_winrate_or_PnL_computed":True,"new_formula_count":1,"parameter_searches":0,"account_runs":0,"consumer_runs":0,"sources_unchanged":True}
dump("candidate_RESULT_SUMMARY.json",summary);dump("candidate_OUTPUT_HASHES.json",{f.name:sha(f) for f in O.glob("candidate_*") if f.is_file() and f.name!="candidate_OUTPUT_HASHES.json"})
print(json.dumps(clean(summary),ensure_ascii=False,indent=2))
print(df[["sid","day","name","strict_known","original_score","new_score","E_old","E_new","E_compression_delta","E_body_delta","context_class"]].to_string(index=False))
