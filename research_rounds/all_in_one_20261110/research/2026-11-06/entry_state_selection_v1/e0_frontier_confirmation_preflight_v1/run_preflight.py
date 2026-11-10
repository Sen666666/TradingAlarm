from pathlib import Path
import sys,math,json,hashlib,time,importlib.util
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
MR=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds")
B5=MR/"pv-strength-b5-20261025/code";G1=MR/"b5-g1-20261025/code";DU=MR/"pv-participation-response-20261020/code"
K=MR/"strict-entry-capacity-20261027/code/entry_kernel.py";CP=MR/"continuous-protection-lines-20261028/code/model.py"
for p in [DU,B5,G1]:sys.path.insert(0,str(p))
from data_utils import eligible_prices
from evidence import build_evidence,EVENT_COLUMNS,EVENT_DATE_COLUMNS
import evidence
from arithmetic import compare,log_ratio
from policy import e0_policy
from grade import classify
from policies_g1 import project
spec=importlib.util.spec_from_file_location("frozen_original_cp",CP);cpm=importlib.util.module_from_spec(spec);spec.loader.exec_module(cpm)
env=dict(evidence.__dict__);exec(compile(K.read_text(),str(K),"exec"),env);base_events=env["entry_events"]
src=K.read_text();needle="if compare(max(confirmation, 0.0), 1.0) >= 0:"
assert src.count(needle)==1
replacement="if compare(max(confirmation, 0.0), 1.0) >= 0 and ((direction == -1 and compare(prices[t], max(prices[ext:t])) > 0) or (direction == 1 and compare(prices[t], min(prices[ext:t])) < 0)):"
guard_src=src.replace("def entry_events(","def guarded_events(").replace(needle,replacement)
exec(compile(guard_src,"guarded_exact_kernel","exec"),env);guard_events=env["guarded_events"]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,(pd.Timestamp,Path)):return str(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 return x
def dump(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2)+"\n")
def policies(e):
 e=e.copy();e["decline_candidate"]=False;b,_=e0_policy(e);g,_=classify(e);i=project(e,b,g,"G1_I");return b,g,i
def candidate(e):
 q=e.copy()
 for seg,g in e.groupby("segment_id",sort=False):
  z,_=guard_events(g,1.0)
  for c in EVENT_COLUMNS:q.loc[g.index,c]=z[c]
 return q
def cpinput(old,ev,ip):
 x=old.copy();x["i_target"]=ip.target.reindex(x.index);x["i_floor"]=ip.floor.reindex(x.index)
 assert x.i_target.notna().all()
 x["e0_valid"]=x.i_target.astype(bool);x["e0_down"]=ev.event.reindex(x.index).eq(-1)
 return x
def trace(e,f):
 out=[]
 for seg,g in f.groupby("segment_id",sort=False):
  d=g.loc[g[["close","volume"]].gt(0).all(axis=1)&np.isfinite(g[["close","volume"]]).all(axis=1)]
  p=d.close.to_numpy(float);v=d.volume.to_numpy(float);ret=[math.nan]+[log_ratio(p[j],p[j-1]) for j in range(1,len(p))];bl=d.volume.shift().rolling(21).median()
  sig=np.full(len(p),np.nan)
  for j in range(64,len(p)):sig[j]=max(math.sqrt(math.fsum(x*x for x in ret[j-63:j])/63),1e-8)
  for j,t in enumerate(d.index):
   z=e.loc[t];row=dict(day=t,event=z.event,frontier_current=None,ext_day=None,age=None,sigma_ext=None,volume_baseline_ext=None,mean_volume_after_ext=None,activity=None,opposite_displacement=None,price_threshold=None,calc_confirmation=None,current_return=ret[j],volume_today=v[j],previous_reverse_frontier=None)
   if not np.isfinite(z.leg_direction):out.append(row);continue
   if z.event!=0:ex=pd.Timestamp(z.confirmed_pivot_date);direction=-z.event
   else:ex=pd.Timestamp(z.developing_extreme_date);direction=z.leg_direction
   k=d.index.get_loc(ex);row.update(ext_day=ex,age=j-k,sigma_ext=sig[k],volume_baseline_ext=float(bl.iloc[k]))
   if j>k:
    mv=math.fsum(float(x) for x in v[k+1:j+1])/(j-k);ac=min(max(math.sqrt(mv/bl.iloc[k]),.5),2)
    disp=(-direction)*log_ratio(p[j],p[k]);past=max(p[k:j]) if direction==-1 else min(p[k:j]);fresh=compare(p[j],past)>0 if direction==-1 else compare(p[j],past)<0
    cf=disp*ac/(math.sqrt(5)*sig[k]);assert np.isclose(cf,z.confirmation,rtol=1e-13,atol=1e-13)
    row.update(frontier_current=fresh,mean_volume_after_ext=mv,activity=ac,opposite_displacement=disp,price_threshold=math.sqrt(5)*sig[k]/ac,calc_confirmation=cf,previous_reverse_frontier=past)
   out.append(row)
 return pd.DataFrame(out).set_index("day").reindex(f.index)
def makepanel(fr,e,b,g,i,cp,tag):
 p=fr[["open","high","low","close","volume","raw_open","raw_high","raw_low","raw_close","amount","raw_volume","adjustment_factor","segment_id"]].copy()
 d=trace(e,fr)
 for c in ["event","confirmed_pivot_price","confirmed_pivot_date","pivot_age","developing_extreme_price","developing_extreme_date","confirmation"]:p[tag+"_"+c]=e[c]
 for c in d:p[tag+"_trace_"+c]=d[c]
 for k,v in [("E0",b),("I",i)]:
  for c in ["target","floor","entered","exited"]:p[tag+"_"+k+"_"+c]=v[c]
 p[tag+"_i_buy"]=i.buy_event
 for c in ["grade","proposal","fresh_up","up_reasons","phase","ready"]:p[tag+"_G_"+c]=g[c]
 for c in ["receipt","anchor","scale","credit","displacement","candidate","delta_frontier","reset_reason"]:p[tag+"_CP_"+c]=cp[c].reindex(p.index)
 return p
def synthetic():
 a=.03/math.sqrt(5);prices=[100*math.exp(a if j%2 else 0) for j in range(65)]+[102.,101.8,102.1]
 f=pd.DataFrame(dict(close=prices,volume=[1.]*66+[7.,1.]),index=pd.bdate_range("2000-01-03",periods=68))
 old,_=base_events(f,1.0);new,_=guard_events(f,1.0)
 assert old.event.iloc[66]==1 and new.event.iloc[66]==0 and new.event.iloc[67]==1
 for cp,vp in [(7.3,1),(1,1000)]:
  q=f.copy();q.close*=cp;q.volume*=vp;z,_=guard_events(q,1.0);assert z.event.equals(new.event)
 return [dict(day=t,close=f.loc[t,"close"],volume=f.loc[t,"volume"],old_event=old.loc[t,"event"],new_event=new.loc[t,"event"],old_confirmation=old.loc[t,"confirmation"],new_confirmation=new.loc[t,"confirmation"]) for t in f.index[-3:]]
def main():
 assert not (O/"CASE_STATES_PRELABEL.csv").exists()
 start=time.perf_counter();cases=json.loads((R/"direction_change_channel_preflight_v1/PROTOCOL.json").read_text())["cases"];mp={r["symbol"]:r for r in json.loads(M.read_text())}
 sources={str(p):sha(p) for p in [M,K,CP,B5/"arithmetic.py",B5/"evidence.py",B5/"policy.py",G1/"grade.py",G1/"policies_g1.py",DU/"data_utils.py",MR/"pv-strength-b4-20261025/code/model.py",O/"PROTOCOL.json",Path(__file__)]}
 dump("SYNTHETIC_QA.json",synthetic());(O/"EXACT_GUARDED_KERNEL.py").write_text(guard_src)
 cache={};reg=[]
 for sid in sorted(set(x[0] for x in cases)):
  rec=mp[sid];sp=next(p for p in rec["source_sha256"] if p.endswith("/signal.parquet"));assert sha(sp)==rec["source_sha256"][sp]
  for p in [sp,rec["refs"]["facts"],rec["refs"]["CP1_input"],rec["refs"]["CP1"]]:sources[p]=sha(p)
  raw=pd.read_parquet(sp);f=eligible_prices(raw);casewindows={}
  for _,ds,_ in [x for x in cases if x[0]==sid]:
   t=pd.Timestamp(ds);j=f.index.get_loc(t);casewindows[ds]=f.index[max(0,j-63):min(len(f),j+22)]
  end=max(v[-1] for v in casewindows.values());fr=f.loc[:end].copy();inp=fr[["open","high","low","close","volume","segment_id"]].copy();inp["valid_price_observation"]=True;inp["valid_strength_observation"]=np.isfinite(inp.volume)&inp.volume.gt(0)
  e,_=build_evidence(inp);b,g,i=policies(e);ff=pd.read_parquet(rec["refs"]["facts"]).reindex(fr.index)
  for c,new in [("e0_target",b.target),("e0_floor",b.floor),("i_target",i.target),("i_floor",i.floor),("i_buy",i.buy_event),("g_grade",g.grade),("g_fresh_up",g.fresh_up),("g_ready",g.ready)]:
   np.testing.assert_allclose(new.astype(float),ff[c].astype(float),rtol=0,atol=1e-8,equal_nan=True,err_msg=sid+c)
  for seg,q in e.groupby("segment_id",sort=False):
   z,_=base_events(q,1.0)
   for c in EVENT_COLUMNS:
    if c in EVENT_DATE_COLUMNS:assert z[c].fillna("").astype(str).equals(q[c].fillna("").astype(str)),(sid,c)
    else:np.testing.assert_allclose(z[c],q[c],rtol=0,atol=0,equal_nan=True,err_msg=sid+c)
  ci=pd.read_parquet(rec["refs"]["CP1_input"]).loc[:end];co=pd.read_parquet(rec["refs"]["CP1"]).reindex(ci.index)
  assert ci.e0_valid.equals(i.target.reindex(ci.index).astype(bool));assert ci.e0_down.equals(e.event.reindex(ci.index).eq(-1))
  cp=cpm.calculate(ci);assert cp.receipt.equals(co.receipt)
  for c in ["anchor","scale","credit","displacement","delta_frontier","candidate","next_anchor"]:np.testing.assert_allclose(cp[c],co[c],rtol=0,atol=1e-12,equal_nan=True,err_msg=sid+"CP"+c)
  cache[sid]=(fr,inp,e,b,g,i,ci,cp,casewindows);reg.append(dict(sid=sid,rows=len(fr),cp_rows=len(ci),baseline_exact=True))
  print("baseline",sid,len(fr),round(time.perf_counter()-start,2),flush=True)
 dump("BASELINE_QA.json",reg)
 panels=[];caseout=[];prefix=[];counts=[]
 for sid,(fr,inp,e,b,g,i,ci,cp,windows) in cache.items():
  en=candidate(e);bn,gn,inn=policies(en);cin=cpinput(ci,en,inn);cpn=cpm.calculate(cin)
  oldp=makepanel(fr,e,b,g,i,cp,"old");newp=makepanel(fr,en,bn,gn,inn,cpn,"new")
  panel=oldp.join(newp.filter(regex="^new_"));want=sorted(set(t for win in windows.values() for t in win));panel=panel.loc[want];panel["sid"]=sid;panel["day"]=panel.index;panels.append(panel.reset_index(drop=True))
  for ds,win in windows.items():
   t=pd.Timestamp(ds);ep,_=build_evidence(inp.loc[:t]);np.testing.assert_allclose(ep[["event","strength_mu5","strength_mu21"]],e.loc[:t,["event","strength_mu5","strength_mu21"]],rtol=0,atol=0,equal_nan=True)
   enp=candidate(ep);bp,gp,ip=policies(enp);cpi=cpm.calculate(cpinput(ci.loc[:t],enp,ip))
   for v,full in [(enp,en.loc[:t]),(bp,bn.loc[:t]),(gp,gn.loc[:t]),(ip,inn.loc[:t]),(cpi,cpn.loc[:t])]:pd.testing.assert_frame_equal(v,full,check_exact=True)
   prefix.append(dict(sid=sid,day=ds,full_pipeline_exact=True))
   point=panel.loc[t].to_dict();point["day"]=ds
   for pre,ev,bb,ii in [("old",e,b,i),("new",en,bn,inn)]:
    for key,mask in [("last_up_event",ev.event.eq(1)),("last_E0_birth",bb.entered.eq(1)),("last_I_birth",ii.entered.eq(1))]:
     xs=ev.index[(ev.index<=t)&mask];point[pre+"_"+key]=str(xs[-1].date()) if len(xs) else None
   caseout.append(point)
   w=panel.loc[win];z=dict(sid=sid,case_day=ds,rows=len(w),old_up=int(w.old_event.eq(1).sum()),new_up=int(w.new_event.eq(1).sum()),old_down=int(w.old_event.eq(-1).sum()),new_down=int(w.new_event.eq(-1).sum()),original_nonfrontier_up=int((w.old_event.eq(1)&w.old_trace_frontier_current.eq(False)).sum()),original_nonfrontier_down=int((w.old_event.eq(-1)&w.old_trace_frontier_current.eq(False)).sum()),E0_changed=int(w.old_E0_target.ne(w.new_E0_target).sum()),I_changed=int(w.old_I_target.ne(w.new_I_target).sum()),i_buy_changed=int(w.old_i_buy.ne(w.new_i_buy).sum()),CP_changed=int(w.old_CP_receipt.ne(w.new_CP_receipt).sum()))
   counts.append(z)
  print("candidate",sid,round(time.perf_counter()-start,2),flush=True)
 p=pd.concat(panels);p.to_parquet(O/"FIXED_WINDOWS_DAILY_PRELABEL.parquet",index=False);c=pd.DataFrame(caseout);c.to_csv(O/"CASE_STATES_PRELABEL.csv",index=False);pd.DataFrame(counts).to_csv(O/"CASE_WINDOW_COUNTS.csv",index=False)
 events=p[p.old_event.ne(0)|p.new_event.ne(0)].copy();events.to_csv(O/"ALL_WINDOW_EVENT_TRACES.csv",index=False)
 dump("PREFIX_QA.json",prefix);dump("FEATURE_SEAL.json",{n:sha(O/n) for n in ["FIXED_WINDOWS_DAILY_PRELABEL.parquet","CASE_STATES_PRELABEL.csv","CASE_WINDOW_COUNTS.csv","ALL_WINDOW_EVENT_TRACES.csv"]})
 ctx=R/"price_wide_structure_preflight_v1/FIXED_CASES_WITH_CONTEXT.csv";sources[str(ctx)]=sha(ctx);labels=pd.read_csv(ctx)[["sid","day","name","old_price_net","old_price_status","receipt","phase","close_size_check","open_size_check"]]
 c=c.merge(labels,on=["sid","day"],how="left",validate="one_to_one");c.to_csv(O/"FIXED_CASES_WITH_CONTEXT.csv",index=False)
 qa=dict(stocks=len(cache),case_points=len(c),baseline_rows=sum(v["rows"] for v in reg),cp_baseline_rows=sum(v["cp_rows"] for v in reg),unique_window_stockdays=len(p),prefixes=len(prefix),original_up=int(p.old_event.eq(1).sum()),original_nonfrontier_up=int((p.old_event.eq(1)&p.old_trace_frontier_current.eq(False)).sum()),original_down=int(p.old_event.eq(-1).sum()),original_nonfrontier_down=int((p.old_event.eq(-1)&p.old_trace_frontier_current.eq(False)).sum()),new_up=int(p.new_event.eq(1).sum()),new_down=int(p.new_event.eq(-1).sum()),changed_case_i_buy=int(c.old_i_buy.ne(c.new_i_buy).sum()),changed_case_E0=int(c.old_E0_target.ne(c.new_E0_target).sum()),changed_case_I=int(c.old_I_target.ne(c.new_I_target).sum()),changed_case_CP=int(c.old_CP_receipt.ne(c.new_CP_receipt).sum()),elapsed_seconds=time.perf_counter()-start,new_economic_runs=0)
 assert all(sha(p)==h for p,h in sources.items());dump("SOURCE_HASHES.json",sources);dump("FINAL_QA.json",qa);dump("OUTPUT_HASHES.json",{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!="OUTPUT_HASHES.json"})
 print(json.dumps(clean(qa),ensure_ascii=False),flush=True)
 print(c[["sid","day","name","old_E0_target","new_E0_target","old_i_buy","new_i_buy","old_CP_receipt","new_CP_receipt","old_last_up_event","new_last_up_event","old_price_net"]].to_string(index=False),flush=True)
if __name__=="__main__":main()
