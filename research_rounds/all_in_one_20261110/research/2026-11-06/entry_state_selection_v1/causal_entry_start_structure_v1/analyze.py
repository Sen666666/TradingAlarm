from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,time
R=Path(".");O=R/"causal_entry_start_structure_v1";U=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031");H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
S={}
def src(p):p=Path(p);S[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return p
with np.load(src(H),allow_pickle=False) as h:cal=pd.DatetimeIndex(h["dates"])
cal=cal[cal<="2026-06-30"];di={d:i for i,d in enumerate(cal)}
market=pd.read_csv(src(R/"causal_trend_segment_attribution_v1/MARKET_DAILY_CAUSAL.csv"),parse_dates=["day"])
target=market[(market.day.dt.year.eq(2022)&market.market_state.eq("UP_MAJORITY")&market.market_age.le(2))|market.day.between("2024-09-02","2024-09-30")|market.day.between("2026-01-05","2026-01-07")].copy()
days=pd.DatetimeIndex(target.day)
meta=pd.read_csv(src(R/"pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv")).set_index("sid")
sm=json.loads(src(U/"STOCK_MANIFEST.json").read_text());im=json.loads(src(U/"INDUSTRY_MANIFEST.json").read_text())
cm=R/"momentum_persistence_breadth_v1/canonical_mu3_comparison_v2";mr=pd.read_parquet(src(cm/"RIGHT3.parquet"));mk=pd.read_parquet(src(cm/"KNOWN3.parquet"))
protocol={"scope":"All 2022 UP_MAJORITY first3 known days including short runs; all Sep2024 common dates; Jan5-7 2026. Previously seen development history; not blind/OOS. No account, orders, scores, grid or new economics.","sector_features":"Current E0/state/CP attempt. Last confirmed UP trough and last confirmed DOWN peak, only from event at observation then causal forward fill within segment. No sector I exists in native source; member stock I summarized separately.","member_features":"Unchanged canonical M3; stock E0/I; source-contiguous daily r; amount relative to strictly prior21 median; sector pooled sign/amount counts and positive mass concentration only descriptive; stock position within current E0 floor and prior confirmed peak descriptive.","candidate_limit":"At most one new consumer after fixed case and semantics review. Do not use realized segment duration or return as a decision variable.","unknown":"Fixed current1709 pool/sector map. Unknown members kept in denominator and bounds, known-only medians explicitly labeled. No native full-industry/PIT claim."}
(O/"PROTOCOL.json").write_text(json.dumps(protocol,indent=2))
target.to_csv(O/"FIXED_TARGET_DAYS.csv",index=False)
sr=[]
for m in im:
 sec=m["series"];f=pd.read_parquet(src(m["refs"]["CP1_input"])).reindex(cal);e=pd.read_parquet(src(next(p for p in m["source_sha256"] if p.endswith("/events.parquet")))).reindex(cal);st=pd.read_parquet(src(m["refs"]["state"]));st["day"]=pd.to_datetime(st.day);st=st.set_index("day").reindex(cal)
 seq=pd.Series(np.arange(len(cal)),index=cal);same=f.segment_id.eq(f.segment_id.shift())&f.segment_id.notna();group=(~same).cumsum()
 up=e.event.eq(1);dn=e.event.eq(-1);q=pd.DataFrame(index=cal);q["sector"]=sec;q["close"]=f.close;q["sector_E0"]=f.e0_valid;q["leg"]=e.leg_direction;q["up_event"]=up;q["E0_entered"]=e.entered.eq(1);q["sector_I_available"]=False;q["stage"]=st.stage_name;q["attempt_active"]=st.authorization_usable
 for prefix,mask in [("up",up),("down",dn)]:
  pp=e.confirmed_pivot_price.where(mask).groupby(group).ffill();pdte=pd.to_datetime(e.confirmed_pivot_date).where(mask).groupby(group).ffill();cday=pd.Series(cal,index=cal).where(mask).groupby(group).ffill()
  q[prefix+"_pivot"]=pp;q[prefix+"_pivot_day"]=pdte;q[prefix+"_confirm_day"]=cday;q[prefix+"_pivot_age"]=seq-pdte.map(di);q[prefix+"_confirmation_age"]=seq-cday.map(di)
 q["peak_log_distance"]=np.log(f.close/q.down_pivot);q["trough_log_distance"]=np.log(f.close/q.up_pivot);den=np.log(q.down_pivot/q.up_pivot);q["repair_fraction"]=(np.log(f.close/q.up_pivot)/den).where(den>0);q["sector_r"]=np.log(f.close/f.close.shift()).where(same);q["sector_amount_ratio"]=f.amount/f.amount.shift().rolling(21,min_periods=21).median()
 q=q.loc[days].reset_index(names="day");sr.append(q)
sector=pd.concat(sr,ignore_index=True);sector.to_csv(O/"SECTOR_FEATURES_PRELABEL.csv",index=False)
rows=[]
cols=["close","amount","source_kind","source_path","segment_id","price_eligible","volume_eligible","source_invalid","observed_bar","is_observed_bar","synthetic_event_bar","raw_volume"]
t0=time.monotonic()
for j,m in enumerate(sm):
 sid=m["symbol"];sec=meta.loc[sid,"sector_id"];raw=pd.read_parquet(src(next(p for p in m["source_sha256"] if p.endswith("/signal.parquet"))),columns=cols).reindex(cal);f=pd.read_parquet(src(m["refs"]["facts"])).reindex(cal).apply(pd.to_numeric,errors="coerce").astype(float)
 ident=raw.source_kind.astype("string")+"|"+raw.source_path.astype("string")+"|"+raw.segment_id.astype("string");pv=raw.close.gt(0)&np.isfinite(raw.close)&raw.price_eligible.fillna(False)&raw.observed_bar.fillna(False)&raw.is_observed_bar.fillna(False)&~raw.synthetic_event_bar.fillna(True)&~raw.source_invalid.fillna(True)&raw.raw_volume.gt(0)
 same=ident.notna()&ident.eq(ident.shift()).fillna(False);r=np.log(raw.close/raw.close.shift()).where(pv&pv.shift(fill_value=False)&same);av=pv&raw.volume_eligible.fillna(False)&raw.amount.gt(0)&np.isfinite(raw.amount);valseg=(~(av&av.shift(fill_value=False)&same)).astype("int64").cumsum();prior21=raw.amount.where(av).groupby(valseg).transform(lambda a:a.shift().rolling(21,min_periods=21).median());ratio=raw.amount/prior21
 g=pd.DataFrame(dict(sid=sid,sector=sec,close=f.close,r=r,amount=raw.amount,amount_ratio=ratio.where(av),E0=f.e0_target,I=f.i_target,i_buy=f.i_buy,G=f.g_grade,I_floor=f.i_floor,E0_floor=f.e0_floor),index=cal)
 g["M3_known"]=mk[sid].reindex(cal).fillna(False);g["M3_right"]=mr[sid].reindex(cal).where(g.M3_known);g["I_distance_log"]=np.log(g.close/g.I_floor).where(g.I.eq(1));g["E0_distance_log"]=np.log(g.close/g.E0_floor).where(g.E0.eq(1))
 g=g.loc[days].reset_index(names="day");rows.append(g)
 if (j+1)%300==0:print("members",j+1,round(time.monotonic()-t0,1),flush=True)
members=pd.concat(rows,ignore_index=True);members.to_parquet(O/"MEMBER_FEATURES_PRELABEL.parquet",index=False)
agg=[]
for (sec,d),g in members.groupby(["sector","day"]):
 n=len(g);kr=g.r.notna();ka=g.r.notna()&g.amount_ratio.notna();pos=g.r.gt(0);neg=g.r.lt(0);jp=pos&g.amount_ratio.gt(1);jn=neg&g.amount_ratio.gt(1);m=g.M3_known;ik=g.I.isin([0,1]);ek=g.E0.isin([0,1]);pp=g.loc[kr&pos,"r"];aa=g.loc[ka&jp,"amount"];new=g.I.eq(1)&g.M3_right.eq(False)&m
 row=dict(sector=sec,day=d,N=n,price_K=int(kr.sum()),amount_K=int(ka.sum()),I_K=int(ik.sum()),I_on=int(g.I.eq(1).sum()),E0_K=int(ek.sum()),E0_on=int(g.E0.eq(1).sum()),M3_K=int(m.sum()),M3_on=int(g.M3_right.eq(True).sum()),I_on_M3_off=int(new.sum()),i_buy=int(g.i_buy.eq(1).sum()),positive_n=int((pos&kr).sum()),negative_n=int((neg&kr).sum()),joint_positive_n=int((jp&ka).sum()),joint_negative_n=int((jn&ka).sum()),median_r_known=g.loc[kr,"r"].median(),median_amount_ratio_known=g.loc[ka,"amount_ratio"].median(),positive_price_HHI=float(((pp/pp.sum())**2).sum()) if len(pp) else None,positive_amount_HHI=float(((aa/aa.sum())**2).sum()) if len(aa) else None,I_distance_log_median_known=g.I_distance_log.median())
 for name,num,known in [("M3",row["M3_on"],row["M3_K"]),("I",row["I_on"],row["I_K"]),("price_positive",row["positive_n"],row["price_K"]),("joint_positive",row["joint_positive_n"],row["amount_K"])]:
  row[name+"_fixed_lower"]=num/n;row[name+"_fixed_upper"]=(num+n-known)/n;row[name+"_known_fraction"]=num/known if known else None
 agg.append(row)
a=pd.DataFrame(agg).merge(sector,on=["sector","day"],validate="one_to_one").merge(target,on="day",validate="many_to_one")
a.to_csv(O/"SECTOR_MEMBER_STRUCTURE_PRELABEL.csv",index=False)
daily=[]
for d,g in a.groupby("day"):
 v=dict(day=d,market_run=g.market_run.iloc[0],market_state=g.market_state.iloc[0],market_age=g.market_age.iloc[0],sector_count=len(g),native_E0_on=int(g.sector_E0.eq(True).sum()),native_leg_up=int(g.leg.eq(1).sum()),native_CP_active=int(g.attempt_active.eq(True).sum()))
 for col in ["up_pivot_age","up_confirmation_age","down_pivot_age","down_confirmation_age","peak_log_distance","repair_fraction","M3_known_fraction","I_known_fraction","I_on_M3_off","price_positive_known_fraction","joint_positive_known_fraction","median_amount_ratio_known","positive_price_HHI","positive_amount_HHI","I_distance_log_median_known"]:
  v[col+"_sector_median"]=g[col].median()
 daily.append(v)
pd.DataFrame(daily).to_csv(O/"DAILY_STRUCTURE_PRELABEL.csv",index=False)
(O/"FEATURE_SOURCE_HASHES.json").write_text(json.dumps(S,indent=2))
(O/"FEATURE_SEAL.json").write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.glob("*PRELABEL*")},indent=2))
print("DONE",len(days),len(members),len(a),round(time.monotonic()-t0,1),flush=True)
