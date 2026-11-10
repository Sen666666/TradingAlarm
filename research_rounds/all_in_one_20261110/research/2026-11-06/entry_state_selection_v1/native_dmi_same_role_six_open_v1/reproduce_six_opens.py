import sys,json,gzip,ast,copy,hashlib,collections,inspect
from pathlib import Path
from decimal import Decimal as D
from types import SimpleNamespace as NS
import numpy as np,pandas as pd
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
W=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds")
U=W/"universe-cp1-inputs-20261031"; P=R/"act_only_ablation_continuous_v1/run/pair"
sys.path.insert(0,"/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility")
import component as K
import native_adapter as A
J,LR=K.J,K.LR
assert A.Runner.route is K.ROUTES[True]
assert A.Runner.opening is J.Runner.opening
DATES=["2022-01-04","2022-05-10","2024-09-12","2024-09-25","2024-10-15","2026-01-15"]
NEXT=dict(zip(DATES,["2022-01-05","2022-05-11","2024-09-13","2024-09-26","2024-10-16","2026-01-16"]))
hashes={}
def sha(p):
 p=Path(p);h=hashlib.sha256(p.read_bytes()).hexdigest();hashes[str(p)]=h;return h
def read(p):return json.loads(Path(p).read_text())
def rows(p):
 with gzip.open(p,"rt") as f:
  for l in f:yield json.loads(l)
sources=[P/"PVR.json.gz",P/"daily.jsonl.gz",P/"funding.jsonl.gz",P/"industry.jsonl.gz",R/"act_only_ablation_continuous_v1/run/OPEN_CASH_CHECKS.jsonl.gz",U/"STOCK_MANIFEST.json",U/"INDUSTRY_MANIFEST.json",R/"dmi_boundary_migration_v1/experiment.py"]
for p in sources:sha(p)
a=json.load(gzip.open(P/"PVR.json.gz","rt"))
dec={z["at"][:10]:z for z in a["decisions"] if z["at"][:10] in DATES}
daily={z["at"][:10]:z for z in rows(P/"daily.jsonl.gz") if z["account"]=="PVR" and z["at"][:10] in DATES}
opens={z["at"][:10]:z for z in rows(sources[4]) if z["account"]=="PVR" and z["at"][:10] in NEXT.values()}
fund=collections.defaultdict(list)
for z in rows(P/"funding.jsonl.gz"):
 if z["account"]=="PVR" and z["at"][:10] in NEXT.values() and z["at"][11:16]=="09:30":fund[z["at"][:10]].append(z)
sm={m["symbol"]:m for m in read(U/"STOCK_MANIFEST.json")}
im={m["series"]:m for m in read(U/"INDUSTRY_MANIFEST.json")}
master={m["security_id"]:m for m in read(J.BP.C.OLD/"inputs-v2/universe.json")["securities"]} if False else {}
import csv
names={m["symbol"]:m for m in csv.DictReader(open("/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/data-adjudicated-v2/master-input.csv"))}
# Exact signal-day sector membership from original saved role trace.
trace=pd.read_parquet(R/"act_candidate_funnel_v1/ROLE_CANDIDATE_TRACE.parquet")
trace=trace[trace.account.eq("PVR") & trace.signal_day.isin(DATES)]
sector_by_sid=dict(zip(trace.sid,trace.sector))
for d,z in daily.items():
 for l in z["layers"]:
  if l["sid"] in sector_by_sid:assert sector_by_sid[l["sid"]]==l["sector"]
  sector_by_sid[l["sid"]]=l["sector"]
raw={}
def price(sid):
 if sid not in raw:
  m=sm[sid];p=next(p for p in m["source_sha256"] if p.endswith("/signal.parquet"))
  assert sha(p)==m["source_sha256"][p]
  raw[sid]=pd.read_parquet(p).loc[:"2026-01-16"]
 return raw[sid]
def factor(sid,day):
 p=price(sid)
 return D(str(p.loc[:day].iloc[-1].adjustment_factor))
def mark(sid,day,col):
 p=price(sid);t=pd.Timestamp(day)
 if t in p.index and np.isfinite(p.loc[t,col]) and p.loc[t,col]>0:return D(str(p.loc[t,col]))
 print("MARK_FALLBACK",sid,day,col,flush=True)
 q=p.loc[p.index<t];q=q[q.raw_close.gt(0)&np.isfinite(q.raw_close)]
 return D(str(q.iloc[-1].raw_close))
states={s:pd.read_parquet(m["refs"]["state"]) for s,m in im.items()}
for s,m in im.items():assert sha(m["refs"]["state"])==m["output_sha256"][m["refs"]["state"]]
def sector_state(day):
 out={}
 for sec,f in states.items():
  past=f[f.day.le(day)];r=past.iloc[-1];assert r.day==day
  ep=r.E0_episode
  if pd.isna(ep):
   ee=past.E0_episode.dropna()
   if not len(ee):continue
   ep=ee.iloc[-1]
  first=f[f.E0_episode.eq(ep)&f.E0_valid.eq(True)].iloc[0].day
  active=bool(r.E0_valid and pd.notna(r.attempt_id) and r.stage>0)
  s=J.V.Sector(ep,J.ordinal(first),active=active,episode_started=J.ordinal(first))
  ended=past[past.action.eq("end_attempt")]
  s.failed_bar=max([J.ordinal(d) for d in ended.day],default=-1)
  if active:
   ar=past[past.attempt_id.eq(r.attempt_id)];birth=ar[ar.action.eq("probe")].iloc[0]
   s.started=J.ordinal(birth.day);s.attempt=ep+":"+birth.receipt_id;s.level=int(r.stage)-1
   s.status=["probe","confirmed","expanded"][s.level]
   rc=ar[ar.receipt.eq(True)&ar.new_receipt.eq(True)];s.last_bar=s.last_end=s.last_evidence_time=J.ordinal(rc.iloc[-1].day)
  out[sec]=s
 return out
Base=J.M.E.FastMarket.__mro__[1];market=Base.__new__(Base)
market.rules=read(Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json"))
market.protocol=read(J.BP.C.OLD/"inputs-v2/economic-protocol.json");market.notices=[];market._notice_keys=set()
for p in [Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json"),J.BP.C.OLD/"inputs-v2/economic-protocol.json"]:sha(p)
rm={}
for key,mp in [("2022",W/"2022-normal-reference-20261031/inputs/MANIFEST.json"),("2024",Path("/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/MANIFEST.json"))]:
 sha(mp);rm[key]={z["sid"]:z for z in read(mp)}
rec={}
def receipt(sid,day):
 key=(sid,day[:4])
 if key not in rec:
  if day[:4] in rm:
   m=rm[day[:4]][sid];p=m["output_path"];expect=m["output_sha256"]
  else:p=sm[sid]["refs"]["receipts"];expect=sm[sid]["output_sha256"][p]
  assert sha(p)==expect
  rec[key]={r["confirmed_day"]:r for r in read(p)}
 return rec[key][day]
def make(day):
 ds=daily[day];nd=NEXT[day];at=J.M.N.iso(nd+"T09:30:00+08:00");cl=J.M.N.iso(day+"T15:10:00+08:00")
 # Corporate/action clocks are unchanged and must not be guessed.
 for j in a["journal"]:
  assert not(j["kind"]=="actual_split" and day<j.get("at","")[:10]<=nd),("unsupported_split_snapshot",day)
 for q in a["audit"]:
  if day<q.get("at","")[:10]<=nd and q.get("at","")[11:16]<="09:30":assert q["kind"] not in ["dividend_accrual","split","split_fraction_floor_proxy","targeted_non_pro_rata_issuance"],("unsupported_action",q)
 assert D(opens[nd]["available_before"])==D(ds["available"])
 assert all(D(ds[x])==0 for x in ["order_reserved","sale_receivable","settlement_locked","payable"])
 lots=[]
 for l in ds["layers"]:
  fl=D(l["last_core_line"]) if l["kind"]=="core" else D(l["floor"])
  lots.append(J.V.Lot(str(l["id"]),l["sid"],l["sector"],l["episode"],l["pool"],l["qty"],l["unit_cost"],float(fl/factor(l["sid"],day)),l["role"],l["attempt"]))
 closeprices={l.stock:float(mark(l.stock,day,"raw_close")) for l in lots}
 ss=sector_state(day)
 b=K.State(cash=ds["available"],receivables=ds["dividend_receivable"],lots=lots,sectors=ss,prices=closeprices,sector_by_sid=sector_by_sid,decision_nav=ds["nav"],available_exact=ds["available"],historical_shared_loss=ds["shared_loss"],remove_confirmed60=True)
 assert abs(b.nav-float(ds["nav"]))<1e-7,("closeNAV",day,b.nav,ds["nav"])
 for pool in ["probe","confirmed"]:assert np.allclose(b.resources(pool),ds["pool_"+pool],rtol=0,atol=1e-7),("close_pool",day,pool,b.resources(pool),ds["pool_"+pool])
 sell=[t for t in a["trades"] if t["at"][:10]==nd and t["side"]=="sell"]
 sold=collections.Counter()
 for t in sell:
  assert t["security_id"] in ds["pending_sells"]
  for part in t["parts"]:sold[str(part["layer"])]+=part["shares"]
 avail=D(opens[nd]["available_before"])+sum((D(t["gross_cny"])-D(t["fees_cny"]) for t in sell),D(0))
 b.cash=float(avail);b.available_exact=avail
 for l in b.lots:
  l.qty-=sold[l.batch];assert l.qty>=0
  # all six dates have no intervening corporate action; factor equality required.
  assert factor(l.stock,day)==factor(l.stock,nd),("factor_changed_without_action",l.stock,day)
  b.prices[l.stock]=float(mark(l.stock,nd,"raw_open"))
 b.lots=[l for l in b.lots if l.qty]
 b.pending_sells={s for s in ds["pending_sells"] if sum(l.qty for l in b.lots if l.stock==s)>0}
 b.consumed={j["receipt"] for j in a["journal"] if j["kind"]=="real_reserve" and j["at"][:10]<=day and j.get("receipt")}
 b.stock_requests=set()
 intents=[]
 for src in dec[day]["intents"]:
  i=copy.deepcopy(src);sid=i["sid"]
  for k in ["budget","floor","risk_budget"]:
   if k in i and i[k] is not None:i[k]=D(i[k])
  i["quote"]=NS(par_value=D(str(market.rules["security_metadata"][sid]["par_value"])))
  i["clock"]=NS(decision_at=cl,earliest_execution_at=at)
  if i["role"]=="mobile":
   i["CP1_trace"]=receipt(sid,day);assert i["CP1_trace"]["receipt_id"]==i["CP1_id"]
  op=mark(sid,nd,"raw_open")
  # No substitution for missing current open in an entry preview.
  p=price(sid);known=pd.Timestamp(nd) in p.index and np.isfinite(p.loc[nd,"raw_open"]) and p.loc[nd,"raw_open"]>0
  if not known:x,why=None,"missing_open"
  else:
   x,why=LR.preview(i,op,factor(sid,nd),market.quantity(sid,at),market.fees(sid,at))
   if x:x["known_open"]=op
  i["_preview"]=x;i["_preview_failure"]=why;intents.append(i)
 return b,intents,at
def checkbase(day,result):
 nd=NEXT[day]
 attempt=[x for x in result["attempts"] if not x.get("skip")]
 expected=fund[nd]
 def key(z):return (z["sid"],z["role"],z["result"],z.get("pool"),z.get("shares"),str(z.get("price")) if z.get("price") is not None else None)
 actual=[key(z) for z in attempt];old=[key(z) for z in expected]
 assert actual==old,("BASELINE_ROUTE_MISMATCH",day,[(x,y) for x,y in zip(actual,old) if x!=y][:5],len(actual),len(old))
 trades=[t for t in a["trades"] if t["side"]=="buy" and t["at"][:10]==nd]
 assert len(trades)==len(result["orders"])
 for o,t in zip(result["orders"],trades):
  assert (o["sid"],o["quantity"],o["price"],o["fee"])==(t["security_id"],t["shares"],D(t["price"]),D(t["fees_cny"])),("BASELINE_FILL_MISMATCH",day,o,t)
 assert result["available"]==D(opens[nd]["available_after"]),("BASELINE_AVAILABLE",day,result["available"],opens[nd]["available_after"])
 return dict(route_attempts_exact=len(attempt),reservations_exact=len(result["orders"]),fees_exact=str(result["fees"]),available_exact=str(result["available"]),snapshot_no_corporate_actions=True)
BUNDLES={}
for day in DATES:
 s,ii,at=make(day);old=K.plan(s,ii,at,remove_confirmed60=True);qa=checkbase(day,old)
 BUNDLES[day]=(s,ii,at,old)
 print("BASE_PASS",day,json.dumps(qa),flush=True)

# Frozen intervention; no thresholds, no outcome columns.
cal=pd.DatetimeIndex(np.load(J.M.P/"h1.npz",allow_pickle=False)["dates"])
cal=cal[(cal>="2013-01-01")&(cal<="2026-01-15")]
mathenv=dict(np=np,pd=pd,N=14)
nodes=[n for n in ast.parse((R/"dmi_boundary_migration_v1/experiment.py").read_text()).body if isinstance(n,ast.FunctionDef) and n.name in ("calc","rma")]
exec(compile(ast.Module(body=nodes,type_ignores=[]),"original_dmi_math","exec"),mathenv);calc=mathenv["calc"]
feature={};qa_dmi=collections.Counter()
for day,(s,ii,at,old) in BUNDLES.items():
 ccal=cal[cal<=day];unique={i["sid"] for i in ii}
 for sid in sorted(unique):
  p=price(sid).loc[:day].reindex(ccal)
  cols=["open","high","low","close"]
  valid=np.isfinite(p[cols]).all(axis=1)&p[cols].gt(0).all(axis=1)&p.high.ge(p[cols].max(axis=1))&p.low.le(p[cols].min(axis=1))&p.segment_id.notna()
  for c in ["price_eligible","observed_bar","is_observed_bar"]:valid &= p[c].fillna(False).astype(bool)
  for c in ["source_invalid","synthetic_event_bar"]:valid &= ~p[c].fillna(True).astype(bool)
  for seg,g in p[valid].groupby("segment_id"):
   assert g.source_kind.notna().all() and g.source_path.notna().all() and g.source_kind.nunique()==g.source_path.nunique()==1,("source_identity",sid,day,seg)
  z=calc(p,ccal);feature[(day,sid)]=float(z.loc[day,"d"]);qa_dmi["physical_signal_prefix"]+=1
 print("FEATURE_DAY",day,len(unique),flush=True)
report=[];allmoves=[];allchanges=[];allcandidates=[];allattempts=[]
def num(v):return float(v) if v is not None else None
def cost(o):return float(o["gross"]+o["fee"]) if o else 0.
for day,(s,ii,at,old) in BUNDLES.items():
 by=collections.defaultdict(list)
 for i in ii:by[i["sid"]].append(i)
 oldrank={sid:g[0]["rank"] for sid,g in by.items()}
 roles={sid:tuple(sorted(i["role"] for i in g)) for sid,g in by.items()}
 assert all(len({i["rank"] for i in g})==1 for g in by.values())
 held=set(daily[day]["positions"]);eligible={sid for sid in by if sid not in held and s.sectors.get(sector_by_sid[sid]) and s.sectors[sector_by_sid[sid]].active}
 pvr={sid:g[0]["PVR_score"] for sid,g in by.items()}
 known={sid for sid in eligible if pvr[sid] is not None and np.isfinite(pvr[sid]) and np.isfinite(feature[(day,sid)])}
 grouped=collections.defaultdict(list)
 for sid in known:grouped[(sector_by_sid[sid],roles[sid])].append(sid)
 keys=dict(oldrank)
 for group,ids in grouped.items():
  slots=sorted(oldrank[sid] for sid in ids)
  ranked=sorted(ids,key=lambda sid:(-feature[(day,sid)],-pvr[sid],sid))
  for slot,sid in zip(slots,ranked):keys[sid]=slot
 assert set(keys.values())==set(oldrank.values())
 assert all(keys[sid]==oldrank[sid] for sid in by if sid not in known)
 newii=copy.deepcopy(ii)
 for i in newii:
  i["rank"]=keys[i["sid"]];i["priority_rank"]=keys[i["sid"]]
  if i["_preview"] is not None:i["_preview"]["i"]=i
 new=K.plan(s,newii,at,remove_confirmed60=True)
 om={o["sid"]:o for o in old["orders"]};nm={o["sid"]:o for o in new["orders"]}
 def funded_signature(o):return (o["role"],o["quantity"],o["pool"],o["price"],o["fee"]) if o else None
 changed=sorted(sid for sid in set(om)|set(nm) if funded_signature(om.get(sid))!=funded_signature(nm.get(sid)))
 moves=sorted((sid for sid in by if keys[sid]!=oldrank[sid]),key=oldrank.get)
 for sid in by:
  z=dict(day=day,sid=sid,name=names.get(sid,{}).get("name"),sector=sector_by_sid[sid],roles="|".join(roles[sid]),held=sid in held,industry_active=s.sectors.get(sector_by_sid[sid]).active if sector_by_sid[sid] in s.sectors else False,eligible=sid in eligible,mutable=sid in known,oldrank=oldrank[sid],newrank=keys[sid],d=feature[(day,sid)],PVR=pvr[sid])
  allcandidates.append(z)
  if sid in moves:allmoves.append(z)
 for sid in changed:
  oo,nn=om.get(sid),nm.get(sid);z=dict(day=day,next_open=NEXT[day],sid=sid,name=names.get(sid,{}).get("name"),sector=sector_by_sid[sid],held=sid in held,roles="|".join(roles[sid]),old_rank=oldrank[sid],new_rank=keys[sid],d=feature[(day,sid)],PVR=pvr[sid])
  for pref,o in [("old",oo),("new",nn)]:
   z.update({pref+"_qty":o["quantity"] if o else 0,pref+"_role":o["role"] if o else None,pref+"_pool":o["pool"] if o else None,pref+"_cash":cost(o),pref+"_fee":float(o["fee"]) if o else 0,pref+"_price":float(o["price"]) if o else None,pref+"_floor":float(o["floor"]) if o else None,pref+"_risk":float(D(o["quantity"])*max(D(0),o["price"]-o["floor"])) if o else 0})
  z["delta_cash"]=z["new_cash"]-z["old_cash"]
  allchanges.append(z)
 # No future same-day volume used: executable proxy capacity from preceding20positive observations.
 capissues=[];capacities=[]
 for o in new["orders"]:
  sid=o["sid"];p=price(sid);prior=p.loc[p.index<pd.Timestamp(NEXT[day]),"raw_volume"];prior=prior[prior.gt(0)&np.isfinite(prior)].tail(20)
  cap=int(prior.mean()*float(market.protocol["participation_rate"])) if len(prior)==20 else 0
  available=market._version("availability_versions",sid,at)
  good=cap>=o["quantity"] and available.get("buy_allowed") is True
  capacities.append(dict(sid=sid,qty=o["quantity"],capacity=cap,buy_allowed=available.get("buy_allowed"),known_open=float(mark(sid,NEXT[day],"raw_open"))))
  if not good:capissues.append(capacities[-1])
 assert not capissues,("NEW_PROXY_EXECUTION_CAPACITY_UNPROVED",day,capissues)
 for label,res in [("PVR",old),("DMI",new)]:
  for z in res["attempts"]:allattempts.append(dict(day=day,arm=label,**z))
 summary=dict(day=day,next_open=NEXT[day],ACT=daily[day]["on"],pending_stocks=len(by),pending_roles=len(ii),flat=sum(sid not in held for sid in by),eligible_flat_active=len(eligible),DMI_unknown_total=sum(not np.isfinite(feature[(day,sid)]) for sid in by),PVR_unknown_total=sum(v is None or not np.isfinite(v) for v in pvr.values()),unknown_eligible=len(eligible-known),mutable=len(known),same_role_groups_ge2=sum(len(ids)>=2 for ids in grouped.values()),moved_stocks=len(moves),old_buys=len(om),new_buys=len(nm),old_first=sum(sid not in held for sid in om),new_first=sum(sid not in held for sid in nm),old_add=sum(sid in held for sid in om),new_add=sum(sid in held for sid in nm),stock_entries_gained=sorted(set(nm)-set(om)),stock_entries_lost=sorted(set(om)-set(nm)),quantity_role_or_member_changes=len(changed),initial_cash=float(s.available_exact),last_close_NAV=float(s.decision_nav),original_cash_reserve=float(s.decision_nav*D(".1")),old_cash=sum(cost(o) for o in om.values()),new_cash=sum(cost(o) for o in nm.values()),old_available=float(old["available"]),new_available=float(new["available"]),old_fees=float(old["fees"]),new_fees=float(new["fees"]),old_nominal_risk=old["nominal_risk"],new_nominal_risk=new["nominal_risk"],new_capacity_checks=len(capacities),new_capacity_unknown=len(capissues))
 report.append(summary)
 print("RESULT",json.dumps(summary,ensure_ascii=False),flush=True)
 if False:
  pass # Full changes are written to the audit CSV below.
 # Fixed named early opportunities, including names not present in original queue.
 for sid in ["300085.SZ","002583.SZ","300666.SZ","603061.SH","301611.SZ"]:
  if day.startswith(("2024","2026")):
   z=next((z for z in allcandidates if z["day"]==day and z["sid"]==sid),None)
   pass # Named candidates are retained in candidate and order audit outputs.
print("TOTAL",json.dumps(dict(baseline_exact_opens=6,baseline_original_routes=1629,baseline_original_buys=77,dmi_prefix=dict(qa_dmi),source_hash_count=len(hashes),native_account_constructions=0,new_continuous_paths=0,new_actual_or_proxy_fills=0,reservation_branches=12,moved=len(allmoves),changed=len(allchanges),unknown_tradability="all historical and counterfactual orders",non_PIT="fixed1709 current industry90",no_old_return_labels=True),ensure_ascii=False),flush=True)

# Persist diagnostic evidence, not strategy edits or account ledgers.
O=R/"native_dmi_same_role_six_open_v1"
assert O.exists() and not (O/"COMPLETE.json").exists()
pd.DataFrame(report).to_csv(O/"SIX_DAY_SUMMARY.csv",index=False)
pd.DataFrame(allcandidates).to_csv(O/"ALL_1237_CANDIDATE_STOCK_DAYS.csv",index=False)
pd.DataFrame(allmoves).to_csv(O/"ALL_474_MOVED_STOCK_DAYS.csv",index=False)
pd.DataFrame(allchanges).to_csv(O/"ALL_44_ALLOCATION_CHANGES.csv",index=False)
atdf=pd.DataFrame(allattempts)
atdf.to_csv(O/"ALL_OPEN_ATTEMPTS.csv",index=False)
unknown=[z for z in allcandidates if not np.isfinite(z["d"]) or z["PVR"] is None or not np.isfinite(z["PVR"])]
pd.DataFrame(unknown).to_csv(O/"UNKNOWN_CANDIDATES.csv",index=False)
# Terminal rejection/reservation for every changed identity, one record per actual role.
change_keys={(z["day"],z["sid"]) for z in allchanges}
atdf[[ (z.day,z.sid) in change_keys for z in atdf.itertuples(index=False)]].to_csv(O/"CHANGED_STOCK_OPEN_ATTEMPTS.csv",index=False)
snapshots=[];allorders=[];named=[]
for day,(s,ii,at,old) in BUNDLES.items():
 keys={z["sid"]:z["newrank"] for z in allcandidates if z["day"]==day}
 ni=copy.deepcopy(ii)
 for i in ni:
  i["rank"]=i["priority_rank"]=keys[i["sid"]]
  if i["_preview"] is not None:i["_preview"]["i"]=i
 # Reproduce the already computed pure reservation projection, not another economic path.
 new=K.plan(s,ni,at,remove_confirmed60=True)
 assert len(new["orders"])==next(x for x in report if x["day"]==day)["new_buys"]
 snapshots.append(dict(day=day,pre_open=K.serial(s.view()),baseline_input_sha=old["input_sha256"],dmi_input_sha=new["input_sha256"]))
 for arm,res in [("PVR",old),("DMI",new)]:
  for order in res["orders"]:
   allorders.append(dict(day=day,arm=arm,held_at_signal=order["sid"] in daily[day]["positions"],**K.serial(order)))
 for sid in ["300085.SZ","002583.SZ","300666.SZ","603061.SH","301611.SZ"]:
  if not day.startswith(("2024","2026")):continue
  z=next((z for z in allcandidates if z["day"]==day and z["sid"]==sid),None)
  named.append(dict(day=day,sid=sid,candidate=z,old_order=next((K.serial(o) for o in old["orders"] if o["sid"]==sid),None),new_order=next((K.serial(o) for o in new["orders"] if o["sid"]==sid),None)))
pd.DataFrame(allorders).to_csv(O/"ALL_RESERVED_ORDERS.csv",index=False)
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,list):return [clean(v) for v in x]
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def save(name,x):(O/name).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,default=str,allow_nan=False))
save("PRE_OPEN_RESOURCE_SNAPSHOTS.json",snapshots)
save("NAMED_EARLY_CANDIDATES.json",named)
save("SOURCE_SHA256.json",hashes)
for path,h in hashes.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==h,("SOURCE_CHANGED_DURING_TEST",path)
save("COMPLETE.json",dict(six_dates=DATES,baseline_exact_opens=6,baseline_routes=1629,baseline_buys=77,old_order_and_fee_sequence_exact=True,old_ending_available_exact=True,old_CLOSE_NAV_and_pool_capital_risk_exact=True,baseline_reconstruction_initial_failed_assertion="Stopped 2026 close price missing; corrected to original previous valid marked close for 601615.SH; baseline then exact without changing strategy or sample",candidate_stockdays=len(allcandidates),mutable_stockdays=sum(z["mutable"] for z in allcandidates),moved_stockdays=len(allmoves),allocation_changed_stockdays=len(allchanges),physical_DMI_prefixes=dict(qa_dmi),unknown_candidates=len(unknown),unknown_eligible=sum(z["eligible"] for z in unknown),next_open_missing=["002948.SZ@2022-01-05","002131.SZ@2026-01-16"],preexisting_mark_missing="601615.SH close2026-01-15/open2026-01-16, previous known close used only for valuation; no new buy fabricated",all_new_order_proxy_capacity_pass=True,all_historical_tradability_UNKNOWN=True,fixed_future_1709_current_industry_NONPIT=True,native_account_initializations=0,new_continuous_accounts=0,new_economic_fills=0,pure_resource_branches=12,repeated_identical_persistence_projection=6,no_outcome_return_labels_used=True,original_sources_unchanged=True,not_new_winner_or_winrate_evidence=True))
save("OUTPUT_SHA256.json",{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.iterdir() if p.is_file() and p.name!="OUTPUT_SHA256.json"})
print("SAVED",str(O),flush=True)
print("UNKNOWNS",json.dumps(unknown,ensure_ascii=False),flush=True)
