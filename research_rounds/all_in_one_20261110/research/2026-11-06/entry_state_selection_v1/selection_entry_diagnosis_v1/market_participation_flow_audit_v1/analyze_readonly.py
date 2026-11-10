import pandas as pd,numpy as np,json
from pathlib import Path
B=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1")
P=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared")
h=np.load(P/"h1.npz",allow_pickle=False); dates=pd.DatetimeIndex(h["dates"]);syms=list(h["symbols"]);ids=[s for s in syms if not s.startswith("URFI")]
C=pd.DataFrame(h["close"],index=dates,columns=syms)[ids];C=C.where(np.isfinite(C)&C.gt(0));G=pd.DataFrame(h["segment"],index=dates,columns=syms)[ids]
A=C.gt(C.rolling(20,min_periods=20).mean());K=C.notna().rolling(25,min_periods=25).sum().eq(25)&G.eq(G.shift(24))
old=A.shift(5,fill_value=False);GG=np.log(C/C.shift(5)).clip(lower=0)
def features(mem):
 k=K[mem];a=A[mem];o=old[mem];n=k.sum(axis=1).replace(0,np.nan)
 born=((~o)&a&k).sum(axis=1)/n;gone=(o&(~a)&k).sum(axis=1)/n;both=(o&a&k).sum(axis=1);prior=(o&k).sum(axis=1)
 gg=GG[mem].where(k);s=gg.sum(axis=1,min_count=1)
 out=pd.DataFrame({"N":n,"B":(a&k).sum(axis=1)/n,"E":born,"X":gone,"D":born-gone,"J":born+gone,"S":both/prior.replace(0,np.nan),"effective":s*s/(n*gg.pow(2).sum(axis=1).replace(0,np.nan))})
 top=[]
 for row,nn,sm in zip(gg.to_numpy(),n,s):
  vals=row[np.isfinite(row)];top.append(np.sort(vals)[-max(1,int(np.ceil(.1*nn))):].sum()/sm if len(vals) and sm>0 else np.nan)
 out["top10"]=top;out["state"]=np.where(out.D.isna()|out.S.isna(),"UNKNOWN",np.where(out.D>0,"EXP","CON")+"_"+np.where(out.S>.5,"RETAIN","REPLACE"))
 return out
m=features(ids);m.index=m.index.strftime("%Y-%m-%d")
f=pd.read_csv(B/"ALL_FIRST_ENTRIES.csv");f=f[f.account.eq("PVR")].copy();assert not f.duplicated(["sid","entry_day"]).any()
f=f.join(m.add_prefix("m_"),on="signal_day");f["win"]=f.round_pnl.gt(0).astype(float).where(f.closed);f["round_ret"]=f.round_return_on_cumulative_cost.where(f.closed)
def metric(z):
 d=z.groupby("signal_day")[["ret5_forward","ret20_forward","win","round_ret","m_S","m_D","m_effective","m_top10"]].mean()
 return {"n":len(z),"dates":len(d),"closed":int(z.closed.sum()),"win_event":z.win.mean(),"win_date":d.win.mean(),"ret5_date":d.ret5_forward.mean(),"ret20_date":d.ret20_forward.mean(),"round_ret_date":d.round_ret.mean(),"big60":int(z.big60_posthoc.sum()),"complete60":int(z.complete60.sum()),"S":d.m_S.mean(),"D":d.m_D.mean(),"effective":d.m_effective.mean(),"top10":d.m_top10.mean()}
print("YEAR_BASE"); print(pd.DataFrame([dict(year=y,**metric(z)) for y,z in f.groupby("year")]).round(5).to_string(index=False))
print("STATE_YEAR");print(pd.DataFrame([dict(year=y,state=s,**metric(z)) for (y,s),z in f.groupby(["year","m_state"])]).round(5).to_string(index=False))
print("YEAR_HIGH_PVR");print(pd.DataFrame([dict(year=y,high=v,**metric(z)) for (y,v),z in f.groupby(["year","PVR_gt85"])]).round(5).to_string(index=False))
same=[]
for (y,day),z in f.groupby(["year","signal_day"]):
 hi=z[z.PVR_gt85];lo=z[~z.PVR_gt85]
 if len(hi) and len(lo):
  r=dict(year=y,day=day,state=z.m_state.iloc[0],S=z.m_S.iloc[0],D=z.m_D.iloc[0],effective=z.m_effective.iloc[0],top10=z.m_top10.iloc[0],nh=len(hi),nl=len(lo))
  for x in ["ret5_forward","ret20_forward","win","round_ret"]:r[x]=hi[x].mean()-lo[x].mean()
  same.append(r)
same=pd.DataFrame(same)
print("SAME_DAY_HIGH_MINUS_LOW");print(same.groupby("year").agg(dates=("day","size"),d5=("ret5_forward","mean"),d20=("ret20_forward","mean"),dwin=("win","mean"),dround=("round_ret","mean")).round(5).to_string())
print("SAME_DAY_STATE_HIGH_MINUS_LOW");print(same.groupby(["year","state"]).agg(dates=("day","size"),d5=("ret5_forward","mean"),d20=("ret20_forward","mean"),dwin=("win","mean")).round(5).to_string())
print("YEAR_ALL_MARKET_DAYS");mm=m.loc["2022-01-01":"2026-05-15"];print(mm.groupby(mm.index.str[:4])[["N","B","E","X","S","J","effective","top10"]].mean().round(5).to_string())
print("KEY_MARKET_DAYS");print(m.reindex(["2022-01-11","2022-03-03","2022-07-25","2022-10-14","2024-09-18","2024-09-19","2024-09-20","2024-09-23","2024-09-24","2024-09-25","2024-09-26","2024-09-27","2024-09-30","2025-12-23","2026-01-05","2026-01-15"]).round(5).to_string())
meta=json.loads(Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json").read_text())
secrows=[]
for sec in sorted(set(f.sector)):
 mem=[i for i in ids if meta[i]["sector_id"]==sec];q=features(mem);q.index=q.index.strftime("%Y-%m-%d");v=f[f.sector.eq(sec)].join(q.add_prefix("s_"),on="signal_day");secrows.append(v)
sf=pd.concat(secrows)
print("SECTOR_STATE_YEAR");print(pd.DataFrame([dict(year=y,state=s,**metric(z)) for(y,s),z in sf.groupby(["year","s_state"])]).round(5).to_string(index=False))
print("SAME_DAY_INDUSTRY_PAIR_HIGH_MINUS_LOW")
pp=[]
for (y,day,sec),z in sf.groupby(["year","signal_day","sector"]):
 hi=z[z.PVR_gt85];lo=z[~z.PVR_gt85]
 if len(hi) and len(lo): pp.append(dict(year=y,day=day,sector=sec,n=len(z),d5=hi.ret5_forward.mean()-lo.ret5_forward.mean(),d20=hi.ret20_forward.mean()-lo.ret20_forward.mean(),dwin=hi.win.mean()-lo.win.mean()))
pp=pd.DataFrame(pp); print(pp.groupby(["year","day"])[["d5","d20","dwin"]].mean().groupby("year").agg(["mean","count"]).round(5).to_string())
print("FROZEN_CASE_SECTOR_MARKET")
for sid,d in [("000620.SZ","2022-01-11"),("002911.SZ","2022-07-25"),("600056.SH","2022-03-03"),("002317.SZ","2022-10-14"),("300085.SZ","2024-09-19"),("300666.SZ","2026-01-05"),("300666.SZ","2026-01-15"),("603061.SH","2026-01-05"),("603061.SH","2026-01-15")]:
 mem=[i for i in ids if meta[i]["sector_id"]==meta[sid]["sector_id"] and i!=sid]; q=features(mem)
 print(sid,d,meta[sid]["industry"],q.loc[pd.Timestamp(d)].round(5).to_dict() if False else q.loc[pd.Timestamp(d)].to_dict())


same=[]
for (y,day),z in f.groupby(["year","signal_day"]):
 hi=z[z.PVR_gt85];lo=z[~z.PVR_gt85]
 if len(hi) and len(lo):same.append(dict(year=y,day=day,state=z.m_state.iloc[0],d5=hi.ret5_forward.mean()-lo.ret5_forward.mean(),d20=hi.ret20_forward.mean()-lo.ret20_forward.mean(),dwin=hi.win.mean()-lo.win.mean()))
same=pd.DataFrame(same);same["month"]=same.day.str[:7]
print("DATE_BLOCK_ROBUSTNESS")
for y,z in same.groupby("year"):
 leave=[z[z.month.ne(mo)].d20.mean() for mo in z.month.unique()]
 mon=z.groupby("month").d20.mean()
 print(y,dict(days=len(z),months=len(mon),median_d20=z.d20.median(),positive_days=z.d20.gt(0).mean(),mean_month_d20=mon.mean(),positive_months=int(mon.gt(0).sum()),leave_month_min=min(leave),leave_month_max=max(leave)))
print("NONOVERLAPPING20_SAME_DAY")
dayindex={d:i for i,d in enumerate(m.index)};kept=[]
for sid,z in f.sort_values("signal_day").groupby("sid"):
 last=-100000
 for ix,r in z.iterrows():
  t=dayindex[r.signal_day]
  if t-last>=20: kept.append(ix);last=t
nf=f.loc[kept]; ss=[]
for (y,d),z in nf.groupby(["year","signal_day"]):
 hi=z[z.PVR_gt85];lo=z[~z.PVR_gt85]
 if len(hi) and len(lo):ss.append(dict(year=y,day=d,d5=hi.ret5_forward.mean()-lo.ret5_forward.mean(),d20=hi.ret20_forward.mean()-lo.ret20_forward.mean(),dwin=hi.win.mean()-lo.win.mean()))
print(pd.DataFrame(ss).groupby("year").agg(days=("day","size"),d5=("d5","mean"),d20=("d20","mean"),dwin=("dwin","mean")).round(6).to_string());print("kept",len(nf),"of",len(f))
meta=json.loads(Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json").read_text())
print("FIRST_CHRONOLOGICAL_SAME_SECTOR_DATE_BOTH_PVR_GROUPS")
for y,z in f.groupby("year"):
 pairs=[]
 for (d,s),zz in z.groupby(["signal_day","sector"],sort=True):
  if zz.PVR_gt85.any() and (~zz.PVR_gt85).any():
   pairs.append(zz);break
 if pairs:
  zz=pairs[0].copy();zz["name"]=zz.sid.map(lambda s:meta[s]["name"])
  print(zz[["year","signal_day","sid","name","PVR_decision","ret5_forward","ret20_forward","round_pnl","round_return_on_cumulative_cost","market_breadth20","market_delta5"]].round(5).to_string(index=False))
print("FROZEN_LEGAL_SEMICONDUCTOR_COMPETITORS")
q=pd.read_csv(B/"sector_cp1_diffusion_audit_v1/FIXED_DATE_CANDIDATE_RANKS.csv")
q=q[q.industry.eq("半导体")&q.day.isin(["2026-01-05","2026-01-15","2024-09-24"])].sort_values(["day","original_PVR"],ascending=[True,False])
print(q[["day","sid","name","original_PVR","PVR_same_mother_rank","Zrel20","B20_peer","dB5_peer","amountshare_ratio"]].round(5).to_string(index=False))
print("ROUND_PERIOD_COMPATIBILITY")
print(pd.DataFrame([dict(year=y,closed=int(z.closed.sum()),closed_in_entry_year=int(z.closed_in_entry_year.sum()),censored=int((~z.closed).sum()),win_allclosed=z.win.mean(),win_closed_in_year=z.loc[z.closed_in_entry_year,"win"].mean())for y,z in f.groupby("year")]).round(6).to_string(index=False))

print("FINAL_NOTE: Retention is five-day endpoint retention, not uninterrupted survival. All history is consumed development data. Fixed future1709 universe and fixed non-PIT sectors. No account runs, forecasts, fitted weights or deployable filter.")
