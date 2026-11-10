from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
R=Path(".");O=R/"causal_entry_start_structure_v1";U=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031");H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
assert (O/"FEATURE_SEAL.json").exists()
with np.load(H,allow_pickle=False) as h:cal=pd.DatetimeIndex(h["dates"])
cal=cal[cal<="2026-06-30"];m=pd.read_parquet(O/"MEMBER_FEATURES_PRELABEL.parquet");days=pd.DatetimeIndex(sorted(m.day.unique()));parts=[]
cm=R/"momentum_persistence_breadth_v1/canonical_mu3_comparison_v2";mk=pd.read_parquet(cm/"KNOWN3.parquet");mr=pd.read_parquet(cm/"RIGHT3.parquet")
for j,s in enumerate(json.loads((U/"STOCK_MANIFEST.json").read_text())):
 sid=s["symbol"];f=pd.read_parquet(s["refs"]["facts"],columns=["i_target","segment_id"]).reindex(cal);raw=pd.read_parquet(next(p for p in s["source_sha256"] if p.endswith("/signal.parquet")),columns=["source_kind","source_path","segment_id"]).reindex(cal)
 adj=pd.Series(True,index=cal)
 for col in raw:adj&=raw[col].notna()&raw[col].shift().notna()&raw[col].eq(raw[col].shift()).fillna(False)
 cur=pd.to_numeric(f.i_target,errors="coerce");prev=cur.shift().where(adj);q=pd.DataFrame({"sid":sid,"prior_I":prev,"I_continuing":cur.eq(1)&prev.eq(1),"I_new_today":cur.eq(1)&prev.eq(0),"I_prior_unknown":cur.eq(1)&~prev.isin([0,1]),"M3_prev_known":mk[sid].reindex(cal).shift().fillna(False),"M3_prev":mr[sid].reindex(cal).shift()},index=cal)
 parts.append(q.loc[days].reset_index(names="day"))
 if (j+1)%500==0:print("I decomposition",j+1,flush=True)
prev=pd.concat(parts,ignore_index=True);a=m.merge(prev,on=["sid","day"],validate="one_to_one");assert (a.I.eq(1).astype(int)==a[["I_continuing","I_new_today","I_prior_unknown"]].sum(axis=1)).all()
a.to_parquet(O/"MEMBER_I_DECOMPOSITION_PRELABEL.parquet",index=False)
s=a.groupby(["sector","day"]).agg(N=("sid","size"),I_on=("I",lambda x:x.eq(1).sum()),I_continuing=("I_continuing","sum"),I_new_today=("I_new_today","sum"),I_prior_unknown=("I_prior_unknown","sum"),prior_I_known=("prior_I",lambda x:x.isin([0,1]).sum())).reset_index()
s["I_continuing_fixed_fraction"]=s.I_continuing/s.N;s["I_new_fixed_fraction"]=s.I_new_today/s.N;s["I_prior_unknown_fixed_fraction"]=s.I_prior_unknown/s.N
s.to_csv(O/"SECTOR_I_DECOMPOSITION_PRELABEL.csv",index=False)
d=s.groupby("day")[["I_continuing_fixed_fraction","I_new_fixed_fraction","I_prior_unknown_fixed_fraction"]].median();d.to_csv(O/"DAILY_I_DECOMPOSITION_PRELABEL.csv")
(O/"I_DECOMPOSITION_SEAL.json").write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.glob("*DECOMPOSITION_PRELABEL*")},indent=2))
print(d.loc[[pd.Timestamp(t) for t in ["2022-02-08","2022-03-17","2022-04-29","2022-11-01","2024-09-12","2024-09-23","2024-09-24","2026-01-05"]]].to_string())
