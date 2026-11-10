"""Independent verification only: no market full-universe rerun and no account actions."""
from pathlib import Path
import ast,sys,json,hashlib,contextlib,io
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O))
import engine
from fast_core import simulate as fast
P=engine.P
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def verify_hashes(name):
 m=load(O/name);bad=[];excluded=[]
 for key,h in m.items():
  if name=="OUTPUT_HASHES.json" and (Path(key).name.startswith("independent_") or Path(key).name.startswith("INDEPENDENT_")):excluded.append(key);continue
  path=Path(key) if Path(key).is_absolute() else O/key
  if not path.is_file() or sha(path)!=h:bad.append(str(path))
 return dict(files=len(m)-len(excluded),mismatches=bad,excluded_independent_review_files=excluded)
def core_checks():
 n={};exec((P/"core.py").read_text(),n);orig=n["simulate"]
 tr=load(O/"TRANSLATION.json");s=(P/"core.py").read_text();f=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name=="simulate");s=ast.get_source_segment(s,f)
 for a,b in tr["exact_replacements"]:
  assert s.count(a)==1;s=s.replace(a,b)
 expected='"""Mechanically translated frozen core; only access/iteration optimized."""\nimport numpy as np\nimport pandas as pd\n\n'+s+"\n"
 assert (O/"fast_core.py").read_text()==expected
 calls=[]
 def parity(q):
  a=orig(q);b=fast(q);pd.testing.assert_frame_equal(a,b,check_exact=True);calls.append(len(q));return b
 syn=(P/"independent_synthetic_audit.py").read_text().replace('simulate=ns["simulate"];perm=ns["execution_permission"]','simulate=parity;perm=ns["execution_permission"]')
 ns={"parity":parity}
 with contextlib.redirect_stdout(io.StringIO()):exec(compile(syn,"independent_synthetic_parity","exec"),ns)
 ids=sorted(engine.manifest);chosen=[ids[j] for j in [0,167,511,854,1024,1281,1537,1708]]
 results=[]
 for sid in chosen:
  q=engine.data(sid);a=orig(q);b=fast(q);pd.testing.assert_frame_equal(a,b,check_exact=True)
  saved=pd.read_parquet(O/"DAILY_STATES.parquet",filters=[("sid","=",sid)]).set_index("day")
  pd.testing.assert_frame_equal(saved[a.columns].assign(receipt_id=saved.receipt_id.str.replace(sid+"|","",regex=False)),a.loc[saved.index],check_exact=True,check_dtype=False,check_names=False)
  cuts=[]
  for cut in ["2022-01-01","2022-12-31","2024-09-01","2024-12-31","2026-01-01","2026-06-30"]:
   z=fast(engine.data(sid,pd.Timestamp(cut)));pd.testing.assert_frame_equal(b.loc[z.index],z,check_exact=True,check_dtype=False);cuts.append(dict(cut=cut,rows=len(z)))
  results.append(dict(sid=sid,rows=len(q),births=int(a.born.sum()),receipts=int(a.receipt.sum()),prefix_cuts=cuts,saved_all_columns_exact=True))
 return dict(mechanical_translation_exact=True,synthetic_passed=len(ns["checks"]),synthetic_parity_calls=len(calls),synthetic_parity_rows=sum(calls),independent_stock_selection="indices 0,167,511,854,1024,1281,1537,1708 of sorted1709 fixed before results",fullwarm_exact=results)
def aggregate_checks():
 cols=["sid","day","window","valid","amount_valid","born","failed","root_unknown","root_day","active","receipt","receipt_id","new_frontier","confirmed_now","phase","S_old","S_new","C","e0_raised","E0","I","i_buy","CP","e0_ready","e0_floor","identity","Q","F","R","a_day","U","B","sector"]
 d=pd.read_parquet(O/"DAILY_STATES.parquet",columns=cols)
 c=pd.read_csv(O/"COVERAGE.csv",dtype={"window":str})
 assert len(d)==1709*(242+80+116) and not d.duplicated(["sid","day"]).any()
 assert set(d.sid)==set(engine.manifest) and len(c)==1709*3 and not c.duplicated(["sid","window"]).any()
 g=d.groupby(["sid","window"])
 calc=g.agg(days=("sid","size"),price_known=("valid","sum"),amount_known=("amount_valid","sum"),births=("born","sum"),receipts=("receipt","sum"),failures=("failed","sum"),root_unknown=("root_unknown","sum"),active_days=("active","sum"),confirmations=("confirmed_now","sum"))
 calc["price_unknown"]=calc.days-calc.price_known;calc["amount_unknown"]=calc.days-calc.amount_known
 compare=c.set_index(["sid","window"]).sort_index();calc=calc.sort_index()
 for col in calc:np.testing.assert_array_equal(calc[col],compare[col])
 assert not (d.born&(~d.receipt|~d.active|~d.new_frontier)).any()
 assert d.receipt.equals(d.new_frontier)
 assert not (d.failed&(d.active|d.receipt|d.born|d.root_unknown)).any()
 assert not (d.root_unknown&(d.active|d.receipt|d.born|d.failed)).any()
 assert (d.loc[d.failed,"C"]<=d.loc[d.failed,"S_old"]).all()
 raises=d[d.e0_raised]
 assert raises.e0_ready.eq(1).all() and raises.E0.eq(1).all()
 assert np.isfinite(raises.e0_floor).all() and raises.e0_floor.gt(0).all() and raises.e0_floor.lt(raises.C).all()
 np.testing.assert_array_equal(raises.S_new,np.maximum(raises.S_old,raises.e0_floor))
 a=d[d.active];assert np.isfinite(a.S_new).all() and a.S_new.lt(a.C).all()
 both=a.S_old.notna();assert a.loc[both,"S_new"].ge(a.loc[both,"S_old"]).all()
 r=d[d.receipt];assert r.receipt_id.is_unique
 expected=r.sid+"|"+r.root_day.dt.strftime("%Y-%m-%d")+"|"+r.day.dt.strftime("%Y-%m-%d")
 assert expected.eq(r.receipt_id).all()
 full=pd.read_parquet(O/"FULL_WARM_BIRTHS.parquet",columns=["sid","day","root_day","born"])
 assert full.born.all() and full.day.eq(full.root_day).all() and not full.duplicated(["sid","root_day"]).any()
 keys=pd.MultiIndex.from_frame(full[["sid","root_day"]])
 assert pd.MultiIndex.from_frame(d[d.root_day.notna()][["sid","root_day"]]).isin(keys).all()
 carries=d.sort_values(["sid","window","day"]).groupby(["sid","window"],sort=True).first()
 carry=(carries.active&~carries.born&carries.root_day.notna()&carries.root_day.lt(carries.day)).rename("carried")
 np.testing.assert_array_equal(carry.sort_index(),compare.carried_root_at_start)
 nh={sid for sid,m in engine.manifest.items() if m["status"]!="complete"}
 assert len(nh)==22
 nd=d[d.sid.isin(nh)];assert len(nd)==22*438
 assert not nd[["valid","amount_valid","born","failed","root_unknown","active","receipt","confirmed_now"]].any().any()
 assert nd.phase.eq("NO_ROOT").all()
 assert c[c.sid.isin(nh)].coverage_status.eq("NO_LOCAL_HISTORY_BY_END").all()
 for name,mask in [("RECEIPTS",d.receipt),("BIRTHS",d.born),("FAILURES_UNKNOWN",d.failed|d.root_unknown),("MARKET_EVENTS",d.born|d.receipt|d.failed|d.root_unknown|d.confirmed_now|d.e0_raised)]:
  x=pd.read_parquet(O/(name+".parquet"),columns=["sid","day"])
  expected=d.loc[mask,["sid","day"]]
  pd.testing.assert_frame_equal(x.reset_index(drop=True),expected.reset_index(drop=True))
 so=pd.read_parquet(O/"SEMICONDUCTOR_2026_DAILY.parquet",columns=cols)
 expected=d[d.window.eq("2026H1")&d.sector.eq("URFI881121")]
 pd.testing.assert_frame_equal(so.reset_index(drop=True),expected.reset_index(drop=True))
 no=pd.read_parquet(O/"NEXT_OPEN_OBSERVATIONS.parquet")
 assert no.receipt_id.is_unique and set(no.receipt_id)==set(r.receipt_id)
 assert no.historical_fill.eq("UNKNOWN_NOT_SIMULATED").all()
 positions=engine.full_cal.get_indexer(no.day)
 np.testing.assert_array_equal(no.next_common_open_day.to_numpy(),engine.full_cal[positions+1].to_numpy())
 np.testing.assert_array_equal(no.earliest_sale_open_day.to_numpy(),engine.full_cal[positions+2].to_numpy())
 rows=[]
 for w,z in d.groupby("window"):
  b=z[z.born];rr=z[z.receipt];m=c[c.window.eq(w)]
  rows.append(dict(window=w,stocks=z.sid.nunique(),rows=len(z),covered_stocks=int((m.price_known>0).sum()),no_local_history_by_end=22,price_known=int(z.valid.sum()),price_unknown=int((~z.valid).sum()),amount_known=int(z.amount_valid.sum()),births=int(z.born.sum()),receipts=int(z.receipt.sum()),failures=int(z.failed.sum()),root_unknown=int(z.root_unknown.sum()),active_days=int(z.active.sum()),carried_roots_at_start=int(m.carried_root_at_start.sum()),confirmations=int(z.confirmed_now.sum()),birth_E0_off=int(b.E0.eq(0).sum()),birth_I_off=int(b.I.eq(0).sum()),birth_i_buy_off=int(b.i_buy.eq(0).sum()),birth_CP_off=int(b.CP.eq(0).sum()),distinct_receipt_roots=len(rr[["sid","root_day"]].drop_duplicates())))
 summary=pd.read_csv(O/"WINDOW_SUMMARY.csv",dtype={"window":str}).set_index("window")
 for row in rows:
  for col in summary.columns:assert row[col]==summary.loc[row["window"],col],(row["window"],col)
 unknown_summary=[dict(window=str(w),day=str(day.date()),valid_price=bool(valid),count=len(z)) for (w,day,valid),z in d[d.root_unknown].groupby(["window","day","valid"])]
 return dict(root_unknown_by_date_validity=unknown_summary,daily_rows=len(d),coverage_rows=len(c),receipt_rows=len(r),full_warm_births=len(full),no_history_stocks=sorted(nh),no_history_daily_rows=len(nd),windows=rows,semiconductor2026=dict(stocks=so.sid.nunique(),rows=len(so),births=int(so.born.sum()),receipts=int(so.receipt.sum()),failures=int(so.failed.sum()),root_unknown=int(so.root_unknown.sum()),carried_roots_at_start=int(c[c.window.eq("2026H1")&c.sector.eq("URFI881121")].carried_root_at_start.sum())),one_price_next_open_observations=int(no.all_day_one_price.fillna(False).sum()),next_open_statuses=no.observation_status.value_counts().to_dict())
def main():
 qa=load(O/"QA.json");assert qa.get("status","").startswith("COMPLETE"),qa
 h={n:verify_hashes(n) for n in ["INPUT_HASHES.json","SOURCE_HASHES.json","OUTPUT_HASHES.json"]}
 for n,v in h.items():assert not v["mismatches"],(n,v["mismatches"])
 result=dict(status="MARKET_CHECKS_PASS_OVERLAP_REVIEW_PENDING",scope="Independent read-only source/outputs review, eight-stock replay and exact prefix testing. No full-universe raw-market rerun; no account, order, fill or economic return run.",hash_checks=h,core_checks=core_checks(),aggregate_checks=aggregate_checks(),source_sha256={n:sha(O/n) for n in ["engine.py","fast_core.py","run_full.py","build_and_verify.py","PROTOCOL.md","INPUT_HASHES.json","SOURCE_HASHES.json","OUTPUT_HASHES.json","QA.json",Path(__file__).name]},immutable_original_core_sha256=sha(P/"core.py"),limitations=["Five original cases and all study windows are previously researched development data, not new OOS.","Stored upstream prices/factors/E0/I/CP causality and PIT corporate-action publication were not re-audited.","Current fixed roster is not historical PIT membership; no-history names are retained as unavailable, not negative signals.","Receipts are market-state observations, not executed trades. Earlier/more receipts do not establish positive economic expectancy.","Native Q, legacy held/pending/unknown classification, and conditional sizing overlap are reviewed separately before final disposition."])
 (O/"INDEPENDENT_FULL_AUDIT_MARKET.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,"item") else str(x))+"\n")
 print(json.dumps(result["aggregate_checks"],ensure_ascii=False,indent=2))
if __name__=="__main__":main()
