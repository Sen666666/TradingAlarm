"""Engineering-only first CLOSE physical-prefix and rank proof. No retained economic arms."""
from pathlib import Path
import sys,json,copy,gc,time,hashlib,inspect
from types import MappingProxyType
import pandas as pd
import run_bounded as B
E,C,A,N,J,L,IO=B.E,B.C,B.A,B.N,B.J,B.L,B.IO
O=B.O
def factor_source(shared,end):
 market=shared[1]
 return E.FactorSource({sid:E.OpenFactorTimeline(raw,market.actions.get(sid,[]),method=shared[0].series[sid].record["adjustment"]["method"],end=end) for sid,raw in market.raw.items() if not raw.empty})
def clear_memo():
 g=J.BP.A.eligibility.__globals__
 assert all(k in g for k in ("memo","memo_at","memo_counts"))
 g["memo"]={};g["memo_at"]=None;g["memo_counts"].clear()
def snapshot(r):
 p=E.payload(r)
 # Full-history episode start catalog is immutable derived metadata. Compare
 # exactly the current sector episode entries, not nonexistent future episodes.
 used={s.episode for a in r.accounts.values() for s in a.budget.sectors.values()}
 p["runner"]["episode_starts"]={k:v for k,v in p["runner"]["episode_starts"].items() if k in used}
 return E.digest(p)
def run():
 root=O/"close_prefix_engineering";root.mkdir(exist_ok=False)
 started=time.monotonic();B.verify_original()
 shared,receipts,cp,states,ir,identity=C.inputs()
 original_scores=N.SCORES
 features=pd.read_parquet(O/"ALL_WINDOW_DMI_FEATURES.parquet");feat={(x.sid,x.day):x.d for x in features.itertuples(index=False)}
 results=[]
 for window in B.WINDOWS:
  cut=B.WINDOWS[window][0];cutts=pd.Timestamp(cut)
  reference=None
  for physical in (False,True):
   dest=root/(window+("_physical" if physical else "_full"));dest.mkdir()
   if physical:
    sh=J.W.physical(shared,cut)
    rc={sid:{d:x for d,x in rr.items() if d<=cut} for sid,rr in receipts.items()}
    cc={sid:f.loc[:cut] for sid,f in cp.items()};ss={s:[x for x in rr if x["day"]<=cut] for s,rr in states.items()};ii={k:x for k,x in ir.items() if x["confirmed_day"]<=cut}
    score=copy.copy(original_scores);score.values=MappingProxyType({sid:MappingProxyType({d:v for d,v in mm.items() if d<=cut}) for sid,mm in original_scores.values.items()})
    score.dates=tuple(d for d in original_scores.dates if d<=cut);N.SCORES=score
    assert getattr(sh[2].row,"__self__",None) is sh[2] and getattr(sh[2].row,"__closure__",None) is None
    assert all(f.empty or f.index.max()<=cutts for f in sh[2].f.values())
    assert all(f.empty or f.index.max()<=cutts for f in sh[1].raw.values())
    assert sh[0]._h1_cache[0].max()<=cutts
    assert all(f.empty or f.index.max()<=cutts for f in cc.values())
   else:
    sh,rc,cc,ss,ii=shared,receipts,cp,states,ir;N.SCORES=original_scores
    clos=sh[2].row.__closure__;bound=[x.cell_contents for x in clos if inspect.ismethod(x.cell_contents)]
    assert any(fn.__self__ is sh[2] for fn in bound),"FULL_ROW_CLOSURE_NOT_SELF_BOUND"
   factors=factor_source(sh,cut if physical else C.END)
   r,m=B.make_runner(sh,rc,cc,ss,ii,factors,window,dest,physical=physical)
   with IO.atomic_runner_outputs(r,L,dest,canonicalize=B.canon):
    last,ds=B.initial(r,m,window,dest)
    if physical:
     before=r.episode_starts
     known={x["E0_episode"] for rr in ss.values() for x in rr if x["E0_valid"]}
     r.episode_starts={k:v for k,v in before.items() if k in known and v<=J.ordinal(cut)}
     used={s.episode for a in r.accounts.values() for s in a.budget.sectors.values()}
     assert used<=set(r.episode_starts)
     assert all(r.episode_starts[k]==before[k] for k in used)
     assert all(v<=J.ordinal(cut) for v in r.episode_starts.values())
    J.M.E.risk_policy.RECOVERY=pd.read_csv(J.M.O/"recovery.csv",index_col=0,parse_dates=True).loc[:cut]
    opens,closes,lo,hi=B.clock_events(m,window);closes={x for x in closes if str(x.date())==cut};opens={x for x in opens if str(x.date())==cut}
    acts={B.datetime.combine(B.datetime.fromisoformat(d).date(),B.dtime.min,J.M.N.TZ) for d in r.actions_by_date}
    action_lo=J.M.N.iso("2022-01-01T00:00:00+08:00") if window=="2022Jan" else last
    end=J.M.N.iso(cut+"T15:10:00+08:00")
    events=sorted(opens|closes|{x for x in acts if (action_lo<=x if window=="2022Jan" else action_lo<x) and x<=end})
    clear_memo()
    for at in events:E.event(r,m,at,opens,closes,None)
    native=snapshot(r);audit=[];B.reorder(r,end,feat,audit);ranked=snapshot(r)
    z=dict(window=window,physical=physical,cut=cut,native_sha256=native,after_DMI_sort_sha256=ranked,rank_audit_sha256=E.digest(audit),events=len(events),stocks_in_pending=len({i["sid"] for i in r.accounts["PVR"].pending}),roles=len(r.accounts["PVR"].pending),facts_maxdate_verified=physical,eligibility_global_memo_cleared=True,native_ledger_label="PVR",engineering_only=True,new_DMI_buy_events=0)
    B.save(dest/"RESULT.json",z)
    if reference is None:reference=z
    else:
     for k in ("native_sha256","after_DMI_sort_sha256","rank_audit_sha256","events","stocks_in_pending","roles"):assert z[k]==reference[k],("PHYSICAL_PREFIX_MISMATCH",window,k,z[k],reference[k])
     results.append(dict(window=window,passed=True,cut=cut,native_sha256=native,ranked_sha256=ranked,rank_rows=len(audit),known_source_prefix=True,memo_independent=True))
   del r,m,factors;gc.collect()
  N.SCORES=original_scores
 B.save(O/"CLOSE_PHYSICAL_PREFIX_QA.json",dict(passed=True,windows=results,seconds=time.monotonic()-started,source_sha256={str(p):B.sha(p) for p in [Path(__file__),O/"run_bounded.py",O/"PROTOCOL.json",O/"ALL_WINDOW_DMI_FEATURES.parquet"]},scope="First signal CLOSE in each fixed month, complete native economic state and original+DMI ranks exact between full-history source and actual truncated source. No retained DMI economic path."))
 print("CLOSE_PREFIX_PASS",results,flush=True)
if __name__=="__main__":run()
